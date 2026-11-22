"""Read-only diagnosis; outputs only selected template tails, not secrets/config."""
import json,subprocess
from analyze_coverage import RUNS,read
ROOT=RUNS.parent
row=next(p['new'] for p in read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json') if p['component']=='MonitoringDashboard')
folder=(RUNS/row['report']).parent;source=next((RUNS/row['batch']/'inputs'/folder.name).glob('*.vue'))
request={'repository':str(ROOT/'migration_system/engine'),'source':source.read_bytes().decode('utf-8'),
 'code':(RUNS/'composed_v9_scope_reassessment_20261120/MonitoringDashboard/effective.san').read_bytes().decode('utf-8')}
p=subprocess.run(['node',str(__import__('pathlib').Path(__file__).with_suffix('.mjs'))],input=json.dumps(request).encode(),capture_output=True,check=True)
result=json.loads(p.stdout)
for side in ('source','target'):
 print(json.dumps({'side':side,'templates':[r for r in result[side] if r['scope'] in ('RequestChart','AlertList','LogList','ServiceGrid')]},ensure_ascii=True))
