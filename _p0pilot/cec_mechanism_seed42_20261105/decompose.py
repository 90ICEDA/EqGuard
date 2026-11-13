"""Algebraic loss decomposition and analytic z-gradients; no autograd or training."""
from pathlib import Path
import collections,csv,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def main():
 assert not (O/'DECOMPOSITION.json').exists();plan=read(O/'PREPARED.json');schedule=read(PRE/'schedule.json');inventory={p['pair_id']:p for p in read(PRE/'function_inventory.json')};index={c:i for i,c in enumerate(plan['train_cones'])};heads={a:dict(np.load(O/f'head_{a}.npz')) for a in ['initial','Z','R','P']};summary=[];details=[]
 def decode(u,arm):p=heads[arm];return np.maximum(u@p['0.weight'].T+p['0.bias'],0)@p['2.weight'].T+p['2.bias']
 for stage in ['initial','Z_pre','R_pre','P_pre','Z_best','R_best','P_best']:
  u=np.load(O/'embeddings'/stage/'train_eval_running.npy');label='initial' if stage=='initial' else stage[0];z=decode(u,label)
  for cohort in ['main','strict']:
   rr=[r for r in schedule if r['mode']==cohort and r['seed']==42]
   for space,x in [('concat128',u),('projection32',z)]:
    bysource=collections.defaultdict(list)
    for row in rr:
     a,b=inventory[row['pair_a']],inventory[row['pair_b']];al,ar,bl,br=[x[index[c]].astype(float) for c in [a['left_cone'],a['right_cone'],b['left_cone'],b['right_cone']]];ml,mr=(al+bl)/2,(ar+br)/2;dl,dr=(al-bl)/2,(ar-br)/2;mse=lambda a,b:float(np.mean((a-b)**2));common=mse(ml,mr);sr=mse(dl,dr);sp=mse(dl,-dr);real=(mse(al,ar)+mse(bl,br))/2;perm=(mse(al,br)+mse(bl,ar))/2;assert np.isclose(real,common+sr) and np.isclose(perm,common+sp)
     gr=np.stack([al-ar,ar-al,bl-br,br-bl]);gp=np.stack([al-br,ar-bl,bl-ar,br-al]);cos=float(np.sum(gr*gp)/max(np.sqrt(np.sum(gr*gr)*np.sum(gp*gp)),1e-24));record=dict(stage=stage,cohort=cohort,space=space,source=row['source'],block_id=row['block_id'],common_centroid=common,real_function_residual=sr,permuted_function_residual=sp,real_mse=real,permuted_mse=perm,positive_gradient_cosine=cos);bysource[row['source']].append(record);details.append(record)
    per=[{k:float(np.mean([r[k] for r in rows])) for k in ['common_centroid','real_function_residual','permuted_function_residual','real_mse','permuted_mse','positive_gradient_cosine']} for rows in bysource.values()];agg={k:float(np.mean([p[k] for p in per])) for k in per[0]};summary.append(dict(stage=stage,cohort=cohort,space=space,**agg,common_share_real=agg['common_centroid']/max(agg['real_mse'],1e-24),common_share_permuted=agg['common_centroid']/max(agg['permuted_mse'],1e-24)))
 loss=[]
 for arm in ['Z','R','P']:
  h=read(PRE/'runs/main/seed42'/arm/'pretrain/history.json');eq=[r['eq_real'] if arm=='R' else r['eq_permuted'] if arm=='P' else 0 for r in h];different=[r['different'] for r in h];var=[.1*r['variance'] for r in h];loss.append(dict(arm=arm,mean_applied_positive=float(np.mean(eq)),mean_different=float(np.mean(different)),mean_variance=float(np.mean(var)),positive_share_of_mean_total=float(np.mean(eq)/np.mean(np.array(eq)+different+np.array(var)))))
 with (O/'loss_decomposition.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
 (O/'DECOMPOSITION.json').write_text(json.dumps(dict(training_updates=0,backward_calls=0,new_SAT_queries=0,loss_summary=loss,decomposition=summary,identity='average true pair squared distance=common centroid shift+relative-function difference;swapped loss has same centroid shift+relative-function sum',gradient='analytic representation-level positive-term cosine;not full encoder/total-loss gradient attribution'),ensure_ascii=False,indent=2),encoding='utf-8')
 for r in summary:
  if r['cohort']=='main' and r['space']=='projection32':print(r['stage'],'common share',round(r['common_share_real'],4),round(r['common_share_permuted'],4),'gradient cosine',round(r['positive_gradient_cosine'],4))
 print(loss)
if __name__=='__main__':main()
