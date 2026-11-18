"""Create the new verification seal once; verify without requiring old code live."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil

PROJECT=Path(__file__).resolve().parents[1]
FOLDER=PROJECT/'docs/verification/2026-11-18_closed_loop_v2'
IMPLEMENTATION=[
    'engine/MANIFEST.json','engine/migration_pipeline/stages/validate.py',
    'engine/migration_pipeline/stages/repair.py','engine/migration_pipeline/utils/bounded_semantics.cjs',
    'engine/migration_pipeline/utils/method_interface_semantics.cjs',
    'engine/migration_pipeline/utils/repair_prompt.py','engine/migration_pipeline/utils/repair_scheduler.py',
    'src/card_migration_system/stages/dom_comparison.py','src/card_migration_system/stages/evaluation.py',
    'src/card_migration_system/prompts/repair_context.py','tests/test_closed_loop_v2.py',
    'tests/test_refactor_reuse.py','tests/historical_lineage.py',
    'scripts/freeze_closed_loop_v2.py','scripts/replay_closed_loop_v2.py',
    'scripts/verify_semantic_comparison.py','scripts/seal_closed_loop_v2.py',
]


def digest(path):return sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--create',action='store_true')
    parser.add_argument('--require-live-match',action='store_true')
    args=parser.parse_args();seal=FOLDER/'SHA256SUMS.json'
    if args.create:
        if seal.exists() or (FOLDER/'after').exists():raise ValueError('Refuse to overwrite sealed evidence')
        tests=json.loads((PROJECT/'var/closed-loop-v2-tests-02.json').read_bytes())
        standalone=json.loads((PROJECT/'var/closed-loop-v2-standalone-02.json').read_bytes())
        if not tests['passed'] or tests['skipped'] or standalone['status']!='standalone_verified':
            raise ValueError('Require passing complete regressions and isolated verification')
        frozen=json.loads((FOLDER/'FREEZE.json').read_bytes())
        for name,expected in frozen['files'].items():
            if digest(FOLDER/name)!=expected:raise ValueError('Original freeze mismatch: '+name)
        shutil.copytree(PROJECT/'var/closed-loop-v2-replay-01',FOLDER/'after/replay')
        for source,name in [('closed-loop-v2-tests-01.json','tests-initial-old-prompt-expectation-failure.json'),
                            ('closed-loop-v2-tests-02.json','tests.json'),('closed-loop-v2-standalone-02.json','standalone.json')]:
            shutil.copyfile(PROJECT/'var'/source,FOLDER/'after'/name)
        for name in IMPLEMENTATION:
            target=FOLDER/'after/implementation'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(PROJECT/name,target)
        files={p.relative_to(FOLDER).as_posix():digest(p) for p in sorted(FOLDER.rglob('*')) if p.is_file()}
        seal.write_text(json.dumps({'schema_version':1,'files':files,
            'implementation_sha256':{name:digest(PROJECT/name) for name in IMPLEMENTATION}},ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=json.loads(seal.read_bytes())
    actual={p.relative_to(FOLDER).as_posix():digest(p) for p in sorted(FOLDER.rglob('*')) if p.is_file() and p!=seal}
    if actual!=manifest['files']:raise ValueError('Sealed payload mismatch')
    live={name:digest(PROJECT/name) for name in manifest['implementation_sha256']}
    match=live==manifest['implementation_sha256']
    if args.require_live_match and not match:raise ValueError('Live implementation differs; sealed evidence remains historical')
    print(json.dumps({'status':'verified','payload_files':len(actual),'implementation_files':len(live),
        'live_matches_sealed_version':match}))


if __name__=='__main__':main()
