"""Maintenance-only source transplant. Never called by API, worker or startup.

Copies the existing analysis/rule implementation without changing its bodies.
Requires an explicit source repository; runtime never searches a parent checkout.
"""
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-repository',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    source=args.source_repository.resolve();destination=args.destination.resolve()
    project=Path(__file__).resolve().parents[1]
    if destination!=project/'engine' or destination.exists():raise ValueError('Require new project/engine destination')
    names={'migration_pipeline/config.py','migration_pipeline/repair_client.py',
           'migration_pipeline/stages/validate.py','migration_pipeline/stages/repair.py','migration_pipeline/stages/visual_eval.py',
           'package.json','package-lock.json'}
    for directory in ('SSM','migration_pipeline/utils','migration_pipeline/contracts'):
        names.update(p.relative_to(source).as_posix() for p in (source/directory).rglob('*')
                     if p.is_file() and p.suffix in ('.py','.cjs','.js'))
    payload={name:(source/name).read_bytes() for name in sorted(names)}
    destination.mkdir()
    manifest={}
    for name,content in payload.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        manifest[name]={'source_path':name,'source_sha256':sha256(content).hexdigest(),
                        'bundled_sha256':sha256(content).hexdigest(),'transformation':'none'}
    # Do not import the old orchestrator/clients through its package facade.
    facade=b'"""Internal validated analysis engine; no external orchestrator is imported."""\n'
    (destination/'migration_pipeline/__init__.py').write_bytes(facade)
    manifest['migration_pipeline/__init__.py']={'source_path':'migration_pipeline/__init__.py',
        'source_sha256':sha256((source/'migration_pipeline/__init__.py').read_bytes()).hexdigest(),
        'bundled_sha256':sha256(facade).hexdigest(),'transformation':'inert_package_facade_no_algorithm_change'}
    # Extract only the previously pinned pure builder; never ship/import Flask routes.
    route=(source/'local_server/api/evaluation_routes.py').read_text(encoding='utf-8')
    tree=ast.parse(route)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_build_generation_prompt')
    contract=(source/'migration_pipeline/utils/class_binding_contract.py').read_text(encoding='utf-8')
    rule=next(n for n in ast.parse(contract).body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='CLASS_BINDING_RULE' for t in n.targets))
    builder='import json\nfrom typing import Any\n\n'+ast.get_source_segment(contract,rule)+'\n\n'+ast.get_source_segment(route,function)+'\n'
    path=destination/'prompts/generation_builder.py';path.parent.mkdir();path.write_text(builder,encoding='utf-8')
    manifest['prompts/generation_builder.py']={'source_path':'local_server/api/evaluation_routes.py::_build_generation_prompt',
        'source_sha256':sha256(route.replace('\r\n','\n').encode()).hexdigest(),
        'bundled_sha256':sha256(path.read_bytes()).hexdigest(),
        'transformation':'exact_function_and_literal_extraction_no_prompt_content_change'}
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=source,capture_output=True,text=True,check=True).stdout.strip()
    record={'schema_version':1,'purpose':'self_contained_validated_source_reuse_not_new_migration_algorithm',
        'source_commit':head,'source_may_include_recorded_uncommitted_fixes':True,'files':manifest,
        'external_source_required_at_runtime':False}
    (destination/'MANIFEST.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    if any((source/name).read_bytes()!=content for name,content in payload.items()):raise ValueError('Source drift during copy')
    print(json.dumps({'copied_files':len(manifest),'source_unchanged':True,'models_called':0}))


if __name__=='__main__':main()
