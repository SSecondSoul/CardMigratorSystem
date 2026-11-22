from hashlib import sha256
import json
from pathlib import Path
from ..adapters.ssm import SSMExtractor
from ..application.service import ServiceError
from ..application.storage import Storage
from ..reporting.identity import digest


def build_dataset(settings,manifest_path,output):
    """Explicit user-selected pairs only. Never crawl the held-out dataset for answers."""
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if manifest.get('schema_version')!=1:raise ServiceError('invalid_training_manifest')
    root=Path(manifest_path).resolve().parent;groups={};sources=set();targets=set();records=[]
    for item in manifest['pairs']:
        group=item['group'];split=item['split']
        if split not in ('train','validation','test') or not isinstance(group,str):raise ServiceError('invalid_training_split')
        if group in groups and groups[group]!=split:raise ServiceError('training_group_leakage')
        groups[group]=split
        source_path=(root/item['vue']).resolve();san_path=(root/item['san']).resolve()
        source=source_path.read_bytes();san=san_path.read_text(encoding='utf-8')
        fingerprint=sha256(source).hexdigest();target_hash=sha256(san.encode()).hexdigest()
        if fingerprint in sources or target_hash in targets:raise ServiceError('training_duplicate_pair')
        sources.add(fingerprint);targets.add(target_hash)
        ssm=SSMExtractor(settings.repository_root).extract(source,source_path.name,fingerprint)['ssm']
        records.append({'id':item['id'],'group':group,'split':split,'source_sha256':fingerprint,'ssm':ssm,
            'ssm_sha256':digest(ssm),'san':san,'san_sha256':target_hash,
            'instruction':'将以下 SSM 迁移为完整 San 单文件组件，仅输出代码。'})
    if len({r['id'] for r in records})!=len(records):raise ServiceError('training_duplicate_id')
    destination=Path(output).resolve()
    if not destination.is_relative_to((settings.project_root/'var/training').resolve()):raise ServiceError('training_output_outside_runtime')
    storage=Storage(destination)
    for split in ('train','validation','test'):
        data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records if r['split']==split).encode()
        storage.put(split+'.jsonl',data)
    storage.put('few-shot.json',json.dumps({'schema_version':1,'examples':records},ensure_ascii=False,indent=2).encode())
    receipt={'manifest_sha256':sha256(Path(manifest_path).read_bytes()).hexdigest(),'groups':groups,
        'records_sha256':digest(records),'counts':{s:sum(r['split']==s for r in records) for s in ('train','validation','test')},
        'exposure':'caller_declared_group_split_not_independent_test_attestation','duplicate_check':'exact_bytes_only'}
    storage.put('dataset.json',json.dumps(receipt,sort_keys=True,indent=2).encode());return receipt
