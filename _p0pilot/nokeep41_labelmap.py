import json,csv,sys
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/seed42_supervised_prep_20261109'))
import Signed_common as S
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8')); base=R/'generate_trans/nokeep41_20261111/jobs'
rows=[]
for v in m['views']:
 orig=R/'generate_trans/folds/hosts_bt31/trans'/f"{v['view']}.v" if (R/'generate_trans/folds/hosts_bt31/trans'/f"{v['view']}.v").exists() else None
 tgt=base/v['base']/'conv'/v['host']/f"{v['base']}__keepnone__ys_{v['recipe']}.v"
 if not orig or not tgt.exists(): rows.append(dict(view=v['view'],orig_exists=bool(orig),target_exists=tgt.exists(),mapped=0,orig_cells=0,target_cells=0)); continue
 go=S.raw_network(orig,S.lib_pins); gt=S.raw_network(tgt,S.lib_pins)
 oc=set(go['pins']); tc=set(gt['pins']); inter=oc&tc
 rows.append(dict(view=v['view'],orig_exists=True,target_exists=True,orig_cells=len(oc),target_cells=len(tc),mapped=len(inter),dff_orig=sum('DFF' in go['pins'][c][0].upper() for c in oc),dff_mapped=sum('DFF' in go['pins'][c][0].upper() for c in inter)))
with open(R/'_p0pilot/nokeep41_20261111/LABEL_MAP_COVERAGE.csv','w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print('done',len(rows),'mean_cell_cov',sum(r['mapped']/max(1,r['orig_cells']) for r in rows)/len(rows))
