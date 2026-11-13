"""Frozen INIT/final32 function-ranking metrics;no model execution or training."""
from pathlib import Path
import collections,csv,json,math
import numpy as np
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def unit_records(uu,ids,x):
 ix={c:j for j,c in enumerate(ids)};result=[]
 for u in uu:
  n=u['functions'];v=x[[ix[c] for c in u['cones']]].astype(np.float64);true=[];wrong=[];wins=[];top=[];CE=[];margin=[];ties=[]
  for f in range(n):
   for side in [0,1]:
    a=2*f+side;candidates=[2*j+1-side for j in range(n)];d=np.sqrt(np.mean((v[a]-v[candidates])**2,1)+1e-12);dt=float(d[f]);minimum=float(d.min());top.append(float(dt==minimum)/int(np.sum(d==minimum)));logits=-d;CE.append(float(np.log(np.exp(logits-logits.max()).sum())+logits.max()-logits[f]))
    for j in range(n):
     if j==f:continue
     dw=float(d[j]);true.append(dt);wrong.append(dw);wins.append(float(dt<dw)+.5*float(dt==dw));margin.append(dw-dt);ties.append(float(abs(dw-dt)<=1e-6))
  result.append(dict(unit_id=u['unit_id'],source=u['source'],context_id=u['context_id'],functions=n,tier=u.get('tier','frozen_train_pool'),has_mux=u.get('has_mux',False),win=float(np.mean(wins)),top1=float(np.mean(top)),CE_true=float(np.mean(CE)),margin=float(np.mean(margin)),near_tie_rate=float(np.mean(ties)),real_distances=true,wrong_distances=wrong))
 return result
def stats(rr):
 def aggregate(key):
  result=[]
  for k in sorted({r[key] for r in rr}):
   zz=[r for r in rr if r[key]==k];a=[v for r in zz for v in r['real_distances']];b=[v for r in zz for v in r['wrong_distances']];w=[1/len(r['real_distances']) for r in zz for _ in r['real_distances']];auc=roc_auc_score([1]*len(a)+[0]*len(b),-np.r_[a,b],sample_weight=np.r_[w,w])
   result.append(dict(key=k,units=len(zz),win=float(np.mean([r['win'] for r in zz])),function_auc=float(auc),top1=float(np.mean([r['top1'] for r in zz])) if len({r['functions'] for r in zz})==1 else None,CE_true=float(np.mean([r['CE_true'] for r in zz])),mean_margin=float(np.mean([r['margin'] for r in zz])),near_tie_rate=float(np.mean([r['near_tie_rate'] for r in zz]))))
  return result
 family=aggregate('context_id');source=aggregate('source')
 average=lambda rows,key:float(np.mean([r[key] for r in rows]))
 summary=dict(units=len(rr),sources=len(source),families=len(family),two_function_units=sum(r['functions']==2 for r in rr),three_function_units=sum(r['functions']==3 for r in rr),family_macro_win=average(family,'win'),source_macro_win=average(source,'win'),family_macro_auc=average(family,'function_auc'),source_macro_auc=average(source,'function_auc'),family_macro_top1=average(family,'top1') if all(r['top1'] is not None for r in family) else None,mean_true_CE=average(family,'CE_true'),mean_margin=average(family,'mean_margin'),near_tie_rate=average(family,'near_tie_rate'))
 return summary,family,source
def geometry(x):
 x=x.astype(np.float64);x-=x.mean(0);s=np.linalg.svd(x,compute_uv=False);energy=s*s;pp=energy/energy.sum() if energy.sum() else energy;rank=float(np.exp(-sum(p*np.log(p) for p in pp if p>0))) if energy.sum() else 0
 return dict(mean_std=float(x.std(0).mean()),effective_rank=rank,PC1_energy=float(pp[0]) if len(pp) else None,observations=len(x),dimensions=x.shape[1])
def main():
 assert read(O/'COMPLETE.json')['actual_optimizer_updates']==96
 pp=read(O/'EVALUATION_PANELS.json');mainval=pp['val_boundary_all'];maintrain=pp['train_frozen_pool'];groups=dict(pp)
 groups.update(val_H3_primary=[u for u in mainval if u['tier']=='H3'],val_H3_two=[u for u in mainval if u['tier']=='H3' and u['functions']==2],val_H3_three=[u for u in mainval if u['tier']=='H3' and u['functions']==3],val_H3_MUX=[u for u in mainval if u['tier']=='H3' and u['has_mux']],val_H3_nonMUX=[u for u in mainval if u['tier']=='H3' and not u['has_mux']],val_H2=[u for u in mainval if u['tier']=='H2'],val_H1=[u for u in mainval if u['tier']=='H1'],train_H3=[u for u in maintrain if u['tier']=='H3'])
 assert len(groups['val_H3_primary'])==73
 metricrows=[];familyrows=[];sourcerows=[];georows=[];unitrows=[]
 for tag in [9000,9001]:
  for arm in ['INIT','Z','R','P']:
   for domain in ['train','val']:
    with np.load(O/f'{domain}_{arm}_tag{tag}.npz') as z:ids=z['cone_ids'].tolist();data={k:z[k].copy() for k in ['root64','mean64','concat128']}
    for group,uu in groups.items():
     if not group.startswith(domain+'_') or not uu:continue
     for space,x in data.items():
      rr=unit_records(uu,ids,x);summary,ff,ss=stats(rr);metricrows.append(dict(tag=tag,arm=arm,group=group,space=space,**summary));familyrows.extend(dict(tag=tag,arm=arm,group=group,space=space,**r) for r in ff);sourcerows.extend(dict(tag=tag,arm=arm,group=group,space=space,**r) for r in ss)
      if space=='root64':unitrows.extend(dict(tag=tag,arm=arm,group=group,unit_id=r['unit_id'],source=r['source'],context_id=r['context_id'],functions=r['functions'],win=r['win'],top1=r['top1'],CE_true=r['CE_true'],margin=r['margin'],near_tie_rate=r['near_tie_rate']) for r in rr)
      if group in ['train_frozen_pool','val_H3_primary']:
       ix={c:j for j,c in enumerate(ids)};sub=sorted({c for u in uu for c in u['cones']});georows.append(dict(tag=tag,arm=arm,group=group,space=space,**geometry(x[[ix[c] for c in sub]])))
 table('evaluation_metrics.csv',metricrows);table('evaluation_by_family.csv',familyrows);table('evaluation_by_source.csv',sourcerows);table('unit_metrics.csv',unitrows);table('representation_geometry.csv',georows)
 primary=[r for r in metricrows if r['space']=='root64' and r['group']=='val_H3_primary'];table('PRIMARY_METRICS.csv',primary);differences=[];sources=sorted({r['key'] for r in sourcerows if r['space']=='root64' and r['group']=='val_H3_primary'})
 for tag in [9000,9001]:
  rows={r['arm']:r for r in primary if r['tag']==tag};real=rows['R']
  for other in ['INIT','Z','P']:
   differences.append(dict(tag=tag,comparison='R-'+other,win_difference=real['family_macro_win']-rows[other]['family_macro_win'],source_macro_win_difference=real['source_macro_win']-rows[other]['source_macro_win'],AUC_difference=real['family_macro_auc']-rows[other]['family_macro_auc']))
 table('PRIMARY_DIFFERENCES.csv',differences)
 srcdiff=[]
 for tag in [9000,9001]:
  for source in sources:
   rr={r['arm']:r for r in sourcerows if r['tag']==tag and r['space']=='root64' and r['group']=='val_H3_primary' and r['key']==source}
   for other in ['INIT','Z','P']:srcdiff.append(dict(tag=tag,source=source,comparison='R-'+other,units=rr['R']['units'],win_difference=rr['R']['win']-rr[other]['win'],AUC_difference=rr['R']['function_auc']-rr[other]['function_auc']))
 table('PRIMARY_SOURCE_DIFFERENCES.csv',srcdiff)
 lookup={(r['tag'],r['comparison']):r for r in differences}
 write('PRIMARY_RESULT.json',dict(primary='73H3 root64 familymacro pairwise win,9000 main',primary_rows=primary,differences=differences,source_differences=srcdiff,R_above_P_main=lookup[9000,'R-P']['win_difference']>0,R_above_Z_main=lookup[9000,'R-Z']['win_difference']>0,R_above_INIT_main=lookup[9000,'R-INIT']['win_difference']>0,R_above_P_and_Z_tag9001=all(lookup[9001,'R-'+k]['win_difference']>0 for k in ['P','Z']),both_sources_nonnegative_main=all(r['win_difference']>=0 for r in srcdiff if r['tag']==9000 and r['comparison'] in ['R-P','R-Z']),caution='single seed,two manufactured sources,one nativecontext/host;no significance or detectiongain claim;no numeric minimumeffect gate preregistered',PO='old4 andnew7 remain separate diagnostic groups',optimizer_updates=96,finetune=0,SAT=0,test_reads=0))
 print('PRIMARY_RESULT',json.dumps(primary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
