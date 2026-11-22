import json,subprocess
from pathlib import Path
from analyze_coverage import RUNS,read
row=next(p['new'] for p in read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json') if p['component']=='TopologyEditor')
folder=(RUNS/row['report']).parent;source=next((RUNS/row['batch']/'inputs'/folder.name).glob('*.vue'))
p=subprocess.run(['node',str(Path(__file__).with_suffix('.cjs'))],input=json.dumps({
 'source':source.read_bytes().decode('utf-8'),'code':(RUNS/'composed_v9_scope_reassessment_20261120/topology_editor/effective.san').read_bytes().decode('utf-8')}).encode(),capture_output=True)
print(p.stdout.decode('utf-8'));print(p.stderr.decode('utf-8'));raise SystemExit(p.returncode)
