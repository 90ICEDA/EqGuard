import json, subprocess, sys
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8'))
base=R/'generate_trans/nokeep41_20261111/jobs'; base.mkdir(parents=True,exist_ok=True)
py=str(R/'ginvenv/Scripts/python.exe'); script=str(R/'phase2/ys/keep_ablation.py')
for i,j in enumerate(m['jobs']):
 out=base/j['base']
 cmd=[py,'-B','-X','utf8',script,'--hosts-root',str(R/f"generate_trans/{j['root']}"),'--host',j['host'],'--views',j['base'],'--recipes',','.join(j['recipes']),'--schemes','none','--out',str(out),'--timeout','900']
 print('JOB',i+1,len(m['jobs']),j['host'],j['base'],j['recipes'],flush=True)
 rc=subprocess.run(cmd).returncode
 print('RC',rc,flush=True)
 if rc!=0:
  print('FAILED',j,flush=True)
