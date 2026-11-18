"""Seal this verification once, or verify it read-only; no historical overwrite."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil

PROJECT=Path(__file__).resolve().parents[1]
FOLDER=PROJECT/'docs/verification/2026-11-18_semantic_comparison_v1'
IMPLEMENTATION=[
    'browser/class-projection.mjs','browser/evaluate.mjs','browser/empty-class-policy.mjs',
    'engine/MANIFEST.json','engine/migration_pipeline/stages/validate.py',
    'engine/migration_pipeline/utils/method_interface_semantics.cjs','engine/migration_pipeline/utils/repair_prompt.py',
    'src/card_migration_system/stages/structure.py','src/card_migration_system/stages/dom_comparison.py',
    'src/card_migration_system/stages/evaluation.py','src/card_migration_system/prompts/repair_context.py',
    'src/card_migration_system/contracts/production_scope.py','frontend/src/components/MigrationWorkbench.vue',
    'scripts/replay_semantic_comparison.py','scripts/verify_semantic_comparison.py','scripts/seal_semantic_comparison.py',
    'tests/test_semantic_comparison_v1.py','tests/test_refactor_reuse.py','tests/test_production_scope.py',
    'tests/historical_lineage.py',
]


def digest(path):return sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create',action='store_true')
    args=parser.parse_args();seal=FOLDER/'SHA256SUMS.json'
    if args.create:
        copies=FOLDER/'after/implementation'
        if seal.exists() or copies.exists():raise ValueError('Refuse to overwrite evidence')
        for name in IMPLEMENTATION:
            target=copies/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(PROJECT/name,target)
        files={p.relative_to(FOLDER).as_posix():digest(p) for p in sorted(FOLDER.rglob('*')) if p.is_file()}
        seal.write_text(json.dumps({'schema_version':1,'files':files,
            'live_implementation_sha256':{name:digest(PROJECT/name) for name in IMPLEMENTATION}},
            ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=json.loads(seal.read_bytes())
    actual={p.relative_to(FOLDER).as_posix():digest(p) for p in sorted(FOLDER.rglob('*')) if p.is_file() and p!=seal}
    if actual!=manifest['files']:raise ValueError('Sealed payload mismatch')
    live={name:digest(PROJECT/name) for name in manifest['live_implementation_sha256']}
    if live!=manifest['live_implementation_sha256']:raise ValueError('Live implementation differs from this seal')
    print(json.dumps({'status':'verified','payload_files':len(actual),'implementation_files':len(live)}))


if __name__=='__main__':main()
