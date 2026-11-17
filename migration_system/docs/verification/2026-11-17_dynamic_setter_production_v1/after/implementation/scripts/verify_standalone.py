"""Run the system from an isolated copy outside its checkout. No paid model calls."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PROJECT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(PROJECT/'var') or output.exists():raise ValueError('Choose a new project/var evidence file')
    implementation={p.relative_to(PROJECT).as_posix():sha256(p.read_bytes()).hexdigest()
                    for folder in ('src','engine','browser','runtime/san_business_v1','frontend/src','frontend/dist','scripts')
                    for p in (PROJECT/folder).rglob('*')
                    if p.is_file() and p.suffix in ('.py','.cjs','.mjs','.vue','.ts','.js','.css','.html','.json')
                    and 'node_modules' not in p.parts and '__pycache__' not in p.parts}
    with tempfile.TemporaryDirectory(prefix='cardmig-standalone-') as temporary:
        isolated=Path(temporary)/'migration_system';isolated.mkdir()
        for name in ('src','engine','browser','runtime/san_business_v1','configs','migrations','frontend/dist'):
            shutil.copytree(PROJECT/name,isolated/name,ignore=shutil.ignore_patterns('node_modules','__pycache__','*.pyc'))
        for name in ('engine/node_modules','browser/node_modules','frontend/node_modules/vue',
                     'frontend/node_modules/@vue/reactivity','frontend/node_modules/@vue/shared'):
            shutil.copytree(PROJECT/name,isolated/name)
        (isolated/'scripts').mkdir()
        for name in ('run_system.py','standalone_probe.py'):
            shutil.copyfile(PROJECT/'scripts'/name,isolated/'scripts'/name)
        (isolated/'tests/fixtures').mkdir(parents=True)
        shutil.copyfile(PROJECT/'tests/fixtures/CapacityPlanningBoard.vue',isolated/'tests/fixtures/CapacityPlanningBoard.vue')
        shutil.copyfile(PROJECT/'requirements.lock',isolated/'requirements.lock')
        # All of these changes affect ONLY the disposable copy, never user config.
        config=isolated/'configs/system.toml'
        config.write_text(config.read_text(encoding='utf-8').replace('network_enabled = true','network_enabled = false')
                          .replace('few_shot_count = 1','few_shot_count = 0'),encoding='utf-8')
        allowed={'SYSTEMROOT','WINDIR','PATH','PATHEXT','COMSPEC','TEMP','TMP','PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'}
        environment={k:v for k,v in os.environ.items() if k.upper() in allowed}
        environment.update(PYTHONIOENCODING='utf-8',PYTHONHASHSEED='0')
        process=subprocess.run([sys.executable,'-I',str(isolated/'scripts/standalone_probe.py'),
            '--forbidden-checkout',str(PROJECT.parent)],cwd=isolated,env=environment,capture_output=True,timeout=300)
        if process.returncode:
            raise RuntimeError('Isolated verification failed: '+process.stderr.decode('utf-8',errors='replace')[-3500:])
        result=json.loads(process.stdout)
        result.update(implementation_sha256=implementation,isolated_outside_checkout=not isolated.is_relative_to(PROJECT.parent),
                      dependencies='installed_runtime_packages_copied_no_links_no_parent_NODE_PATH',real_model_calls=0)
    for name,expected in implementation.items():
        if sha256((PROJECT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Implementation changed during verification')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='implementation_sha256'},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
