"""Internal source bundle integrity, not a new migration rule or evaluator."""
from hashlib import sha256
import json
from pathlib import Path


def verify_engine(root):
    root=Path(root).resolve()
    manifest=json.loads((root/'MANIFEST.json').read_bytes())
    if manifest.get('schema_version')!=1 or not manifest.get('files'):
        raise ValueError('internal_engine_manifest_invalid')
    for relative,item in manifest['files'].items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or sha256(path.read_bytes()).hexdigest()!=item['bundled_sha256']:
            raise ValueError('internal_engine_source_drift')
    return {'scope':'internal_validated_source_bundle','files':len(manifest['files']),
            'manifest_sha256':sha256((root/'MANIFEST.json').read_bytes()).hexdigest(),
            'external_repository_required':False}
