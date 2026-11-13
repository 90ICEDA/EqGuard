"""Recipe-specific threshold calibration for ctrlstrat on train controls; evaluate test FPR/recall."""
import os, sys, json, collections
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
B=R/'_p0pilot/control_boundary_v3_20261104'; OUT=R/'_p0pilot/lcone_trainctl_20261110'
sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104'))
from evaluate import Model
c=json.loads((B/'input_contract.json').read_text(encoding='utf-8'))
# train graph/scores
g=np.load(FG/'group_B.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
xt=torch.as_tensor(norm(g['x']),device='cuda'); et=torch.as_tensor(g['edge'],device='cuda')
ck=torch.load(OUT/'run_ctrlstrat_s1_lam0.1/best_resume.pt',map_location='cuda',weights_only=False); m=Model().cuda(); m.load_state_dict(ck['model']); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
 s_tr=(m(xt,et).float()[:,1]-m(xt,et).float()[:,0]).cpu().numpy()
# test scores
z=np.load(OUT/'run_ctrlstrat_s1_lam0.1/best_testpred.npz'); s_te=z['scores']; yte=z['y']; trte=z['trusted']; phte=z['physical']; rowte=z['rows']; loc_te={r:i for i,r in enumerate(rowte.tolist())}
# train ctl/local recipe
tr_mask=np.zeros(len(g['y']),bool); tr_rec=np.empty(len(g['y']),object); tr_rec[:]=''
for v in c['shared_inputs']['trans_train']['views']:
 if 'ctl' not in v['view']: continue
 a,b=v['start'],v['stop']; ids=g['rows'][(g['rows']>=a)&(g['rows']<b)]; idx=np.array([np.where(g['rows']==x)[0][0] for x in ids]) if False else None
 # use loc map
 loc={r:i for i,r in enumerate(g['rows'].tolist())}; ii=np.array([loc[int(x)] for x in ids]); rec=v['view'].split('__')[-1]
 tr_mask[ii]=True; tr_rec[ii]=rec
# test masks
te_mask=np.zeros(len(yte),bool); te_rec=np.empty(len(yte),object); te_rec[:]=''; pos_mask=np.zeros(len(yte),bool); pos_rec=np.empty(len(yte),object); pos_rec[:]=''
for v in c['shared_inputs']['trans_test']['views']:
 a,b=v['start'],v['stop']; rec=v['view'].split('__')[-1]; idx=np.array([loc_te[int(x)] for x in rowte if a<=x<b])
 if 'ctl' in v['view']: te_mask[idx]=True; te_rec[idx]=rec
 if 'ctl' not in v['view']:
  pos_mask[idx]=(yte[idx]==1)&trte[idx]&phte[idx]; pos_rec[idx]=rec
out={}
for target in (0.05,0.10,0.20):
 glob=float(np.quantile(s_tr[tr_mask],1-target))
 rows={}
 for rec in sorted(set(tr_rec[tr_mask])):
  rm=tr_mask&(tr_rec==rec); rows[rec]=float(np.quantile(s_tr[rm],1-target))
 # global
 gm=te_mask
 g_fpr=float((s_te[gm]>=glob).mean())
 g_rec=float(np.sum((s_te>=glob)&pos_mask)/pos_mask.sum()) if pos_mask.sum() else None
 # recipe
 recs={}
 for rec in sorted(set(te_rec[te_mask])):
  tm=te_mask&(te_rec==rec); recs[rec]=dict(threshold=rows.get(rec),fpr=float((s_te[tm]>=rows[rec]).mean()) if rec in rows else None,pos_recall=None)
 # positive recall per recipe at its threshold
 for rec in sorted(set(pos_rec[pos_mask])):
  pm=pos_mask&(pos_rec==rec); recs[rec]['pos_recall']=float((s_te[pm]>=rows[rec]).sum()/pm.sum()) if rec in rows and pm.sum() else None
 out[str(target)]=dict(global_threshold=glob,global_fpr=round(g_fpr,4),global_pos_recall=round(g_rec,4) if g_rec is not None else None,recipe=recs,
                       overall_recipe_fpr=float(np.mean([x['fpr'] for x in recs.values() if x['fpr'] is not None])),
                       overall_recipe_pos_recall=float(np.mean([x['pos_recall'] for x in recs.values() if x['pos_recall'] is not None])))
(OUT/'RECIPE_THRESHOLD.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False)[:2000])
