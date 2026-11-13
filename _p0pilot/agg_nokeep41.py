import json,csv,hashlib
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); base=R/'generate_trans/nokeep41_20261111/jobs'
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8'))
rows=[]
for v in m['views']:
    out=base/v['base']/'conv'/v['host']/f"{v['base']}__keepnone__ys_{v['recipe']}.v"
    cec=base/v['base']/'logs'/f"cecconv_{v['base']}__keepnone__ys_{v['recipe']}.txt"
    txt=cec.read_text(encoding='utf-8',errors='ignore') if cec.exists() else ''
    status='PASS' if ' PASS' in txt else ('FAIL' if 'FAIL' in txt else 'UNKNOWN')
    sha=hashlib.sha256(out.read_bytes()).hexdigest() if out.exists() else ''
    rows.append(dict(view=v['view'],base=v['base'],host=v['host'],recipe=v['recipe'],output=str(out),exists=out.exists(),bytes=out.stat().st_size if out.exists() else 0,sha256=sha,cec=status,cec_log=str(cec)))
with open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
summ=dict(total=len(rows),exists=sum(r['exists'] for r in rows),cec_pass=sum(r['cec']=='PASS' for r in rows),cec_fail=[r['view'] for r in rows if r['cec']!='PASS'],bytes=sum(r['bytes'] for r in rows))
json.dump(summ,open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_CEC.json','w'),indent=2)
print(summ)
