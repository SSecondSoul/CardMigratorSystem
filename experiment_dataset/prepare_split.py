"""Plan or verify a frozen 70/20/10 component split; never overwrite source files.

--plan-json emits metadata plus byte-preserving copy operations for the caller.
--check verifies the frozen folder alone; --check-sources also checks the original
repository. No model, migration, training, database or automatic file write.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
LEVELS=('simple','medium','complex')
FOLDERS={'simple':'01_simple','medium':'02_medium','complex':'03_complex'}
SUBSETS=('experiment','validation','test')
WEIGHTS=(7,2,1)
SEED='20261118'
HISTORY=(
    'data/datasets/splits/pilot_9_v6_development_and_formal_30_v1.json',
    'data/datasets/splits/formal_30_v3_untouched_holdout.json',
    'data/datasets/splits/formal_30_v5_candidate_20261030.json',
)


def digest(data):return sha256(data).hexdigest()
def encode(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def rank(sample):return digest(f"experiment-dataset-v1:{SEED}:{sample['complexity']}:{sample['id']}".encode())


def quotas(counts):
    """Integer row and column totals, largest feasible fractional remainder first."""
    total=sum(counts.values())
    targets=[total*w//10 for w in WEIGHTS]
    for i in sorted(range(3),key=lambda i:(-(total*WEIGHTS[i]%10),i))[:total-sum(targets)]:targets[i]+=1
    matrix={level:[counts[level]*w//10 for w in WEIGHTS] for level in LEVELS}
    rows={level:counts[level]-sum(matrix[level]) for level in LEVELS}
    cols=[targets[i]-sum(matrix[level][i] for level in LEVELS) for i in range(3)]
    cells=sorted(((level,i) for level in LEVELS for i in range(3)),key=lambda cell:(-(counts[cell[0]]*WEIGHTS[cell[1]]%10),LEVELS.index(cell[0]),cell[1]))
    for level,i in cells:
        if rows[level] and cols[i]:matrix[level][i]+=1;rows[level]-=1;cols[i]-=1
    if any(rows.values()) or any(cols):raise ValueError('Cannot satisfy stratified quotas; explicit review required')
    return {level:dict(zip(SUBSETS,matrix[level])) for level in LEVELS}


def histories(root):
    result={};sources={}
    for relative in HISTORY:
        raw=(root/relative).read_bytes();sources[relative]=digest(raw);data=json.loads(raw)
        if 'pilot_9_v6_development' in relative:
            groups=[(data['development_pilot'],'pilot_calibration'),(data['independent_test']['samples'],'prior_formal_v1_then_development')]
        elif 'formal_30_v3_' in relative:groups=[(data['samples'],'prior_formal_v3_then_development')]
        else:groups=[(data['samples'],'v5_exploratory_candidate_early_contact_uncertain'),(data['excluded'],'v5_excluded_candidate_prior_contact_unconfirmed')]
        for records,label in groups:
            for sample in records:result.setdefault(sample['id'],[]).append(label)
    return result,sources


def known_development(labels):
    return any(label in ('pilot_calibration','prior_formal_v1_then_development','prior_formal_v3_then_development') for label in labels)


def assign(components,history):
    allocation=quotas(Counter(c['complexity'] for c in components));selected={}
    for level in LEVELS:
        pool=sorted((c for c in components if c['complexity']==level),key=lambda c:(not known_development(history.get(c['id'],[])),rank(c)))
        if sum(known_development(history.get(c['id'],[])) for c in pool)>allocation[level]['experiment']:
            raise ValueError('Known development samples exceed experiment quota; do not silently leak them')
        start=0
        for subset in SUBSETS:
            count=allocation[level][subset]
            for sample in pool[start:start+count]:selected[sample['id']]=subset
            start+=count
    return selected,allocation


def inside(path,root):
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe dataset path')
    return path


def build(root):
    root=Path(root).resolve();source=root/'data/datasets';manifest_path=source/'dataset_manifest.json'
    raw=manifest_path.read_bytes();components=json.loads(raw)['components']
    if len(components)!=100 or len({c['id'] for c in components})!=100:raise ValueError('Expected 100 distinct manifest components; review a new version otherwise')
    if any(c['complexity'] not in LEVELS for c in components):raise ValueError('Unknown complexity')
    history,history_sources=histories(root);chosen,allocation=assign(components,history)
    samples=[];copies=[];vue_groups={};component_dirs=set()
    for item in sorted(components,key=lambda c:(LEVELS.index(c['complexity']),c['id'])):
        component=inside(source/item['path'],source/'components')
        if component in component_dirs:raise ValueError('Component directory repeated')
        component_dirs.add(component)
        subset=chosen[item['id']];target=Path(subset)/FOLDERS[item['complexity']]/component.name
        vue=inside(component/'vue'/item['vue_file'],component);san=inside(component/'san'/item['san_file'],component)
        vue_hash=digest(vue.read_bytes());san_hash=digest(san.read_bytes())
        vue_groups.setdefault(vue_hash,[]).append(subset)
        sample={'id':item['id'],'name':item['name'],'component_name':Path(item['vue_file']).stem,
                'complexity':item['complexity'],'subset':subset,'component_root':target.as_posix(),
                'vue_file':(target/'vue'/item['vue_file']).as_posix(),'reference_san_file':(target/'san'/item['san_file']).as_posix(),
                'vue_sha256':vue_hash,'reference_san_sha256':san_hash,
                'source_component_root':component.relative_to(root).as_posix(),
                'prior_usage':history.get(item['id'],['unknown_prior_contact_not_evidence_of_unseen']),
                'independent_holdout':False}
        samples.append(sample)
        for file in sorted(component.rglob('*')):
            inside(file,component)
            if not file.is_file():continue
            data=file.read_bytes()
            copies.append({'source':file.relative_to(root).as_posix(),'path':(target/file.relative_to(component)).as_posix(),'sha256':digest(data),'bytes':len(data)})
    if any(len(set(groups))>1 for groups in vue_groups.values()):raise ValueError('Exact Vue duplicate crosses subsets; review component grouping')
    files={};subset_specs={}
    for subset in SUBSETS:
        group=[s for s in samples if s['subset']==subset]
        spec={'split_id':'component_100_70_20_10_v1','subset':subset,'count':len(group),
              'independent_holdout':False,'path_base':'experiment_dataset/','samples':group}
        relative=f'{subset}/manifest.json';data=encode(spec);files[relative]=data.decode('utf-8')
        subset_specs[subset]={'count':len(group),'manifest':relative,'manifest_sha256':digest(data),
                             'by_complexity':dict(Counter(s['complexity'] for s in group))}
    record={'split_id':'component_100_70_20_10_v1','created_date':'2026-11-18','ratio':dict(zip(SUBSETS,WEIGHTS)),
            'seed':SEED,'selection':'complexity_stratified_largest_remainder; known prior development first into experiment; SHA256 seeded rank for remaining components',
            'counts':{'total':100,**{s:subset_specs[s]['count'] for s in SUBSETS}},'stratified_counts':allocation,
            'independent_holdout':False,'evidence_class':'post_development_repartition_internal_exploratory',
            'history_audit_scope':'three existing split records only; no absence-of-exposure claim; recent system jobs and all notebooks not exhaustively audited',
            'source_manifest':{'path':manifest_path.relative_to(root).as_posix(),'sha256':digest(raw)},
            'history_sources_sha256':history_sources,'known_prior_development_in_experiment':sum(known_development(s['prior_usage']) for s in samples if s['subset']=='experiment'),
            'subsets':subset_specs,'samples':samples,'payload_files':copies,
            'reference_policy':'reference_san_file is an existing dataset reference, not fresh model output or verified ground truth; validation/test references must not become prompt/few-shot/repair inputs'}
    files['manifest.json']=encode(record).decode('utf-8')
    checks={path:digest(text.encode('utf-8')) for path,text in files.items()}
    checks.update({item['path']:item['sha256'] for item in copies})
    files['SHA256SUMS.txt']=''.join(f'{value}  {path}\n' for path,value in sorted(checks.items()))
    return {'files':files,'copies':copies,'counts':record['counts'],'stratified_counts':allocation}


def check(folder,source_root=None):
    folder=Path(folder).resolve();record=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if record['counts']!={'total':100,'experiment':70,'validation':20,'test':10}:raise ValueError('Split count mismatch')
    samples=record['samples'];ids=[s['id'] for s in samples]
    if len(ids)!=100 or len(set(ids))!=100 or record['independent_holdout'] is not False:raise ValueError('Sample identity/evidence boundary mismatch')
    if Counter(s['subset'] for s in samples)!=Counter({s:record['counts'][s] for s in SUBSETS}):raise ValueError('Actual subset membership differs')
    seen=set()
    for item in record['payload_files']:
        path=inside(folder/item['path'],folder)
        if item['path'] in seen:raise ValueError('Payload repeated')
        seen.add(item['path']);raw=path.read_bytes()
        if len(raw)!=item['bytes'] or digest(raw)!=item['sha256']:raise ValueError('Payload hash mismatch: '+item['path'])
        if source_root is not None:
            source=inside(Path(source_root)/item['source'],Path(source_root)/'data/datasets/components')
            if digest(source.read_bytes())!=item['sha256']:raise ValueError('Original source drift: '+item['source'])
    for subset in SUBSETS:
        spec=record['subsets'][subset];raw=(folder/spec['manifest']).read_bytes()
        if digest(raw)!=spec['manifest_sha256']:raise ValueError('Subset manifest mismatch')
        if json.loads(raw)['samples']!=[s for s in samples if s['subset']==subset]:raise ValueError('Subset sample mismatch')
        for item in samples:
            if item['subset']==subset and known_development(item['prior_usage']) and subset!='experiment':raise ValueError('Known development leakage')
        actual={p.relative_to(folder).as_posix() for p in (folder/subset).rglob('*') if p.is_file() and p.name!='manifest.json'}
        if actual!={p for p in seen if p.startswith(subset+'/')}:raise ValueError('Unexpected or missing component file')
    for line in (folder/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,path=line.split('  ',1)
        if digest(inside(folder/path,folder).read_bytes())!=expected:raise ValueError('Checksum mismatch: '+path)
    if source_root is not None:
        sources={record['source_manifest']['path']:record['source_manifest']['sha256'],**record['history_sources_sha256']}
        for path,expected in sources.items():
            if digest((Path(source_root)/path).read_bytes())!=expected:raise ValueError('Source metadata drift: '+path)
    return {'status':'verified','counts':record['counts'],'stratified_counts':record['stratified_counts'],
            'payload_files':len(seen),'independent_holdout':False,'model_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--plan-json',action='store_true');mode.add_argument('--check',action='store_true');mode.add_argument('--check-sources',action='store_true')
    args=parser.parse_args()
    result=build(HERE.parent) if args.plan_json else check(HERE,HERE.parent if args.check_sources else None)
    # ASCII transport avoids Python/PowerShell code-page disagreement on Windows;
    # manifest files themselves remain canonical UTF-8 via encode().
    print(json.dumps(result,ensure_ascii=True));return 0

if __name__=='__main__':raise SystemExit(main())
