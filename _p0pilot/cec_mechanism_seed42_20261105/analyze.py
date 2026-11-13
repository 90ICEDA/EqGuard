"""Scale-aware checkpoint diagnostics. CPU arrays only; no optimization."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,json
import numpy as np
from sklearn.metrics import roc_auc_score
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def table(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert not (O/'DIAGNOSIS_COMPLETE.json').exists();plan=read(O/'PREPARED.json');done=read(O/'EMBEDDINGS_COMPLETE.json');pairs=read(J/'final_pairs.json');byid={p['pair_id']:p for p in pairs};cones={c['cone_id']:c for c in read(J/'final_cones.json')};schedule=read(PRE/'schedule.json');valcert=read(O/'validation_negative_certificates.json');weights={r['pair_id']:float(r['weight']) for r in csv.DictReader((J/'weights.csv').open(encoding='utf-8-sig'))};data={};head={label:dict(np.load(O/f'head_{label}.npz')) for label in ['initial','Z','R','P']};orders={s:plan[s+'_cones'] for s in ['train','val']};indices={s:{cid:i for i,cid in enumerate(v)} for s,v in orders.items()};sources={p[k]:p['source_object'] for p in pairs for k in ['left_cone','right_cone']}
 def load(stage,split,mode='eval_running'):
  key=stage,split,mode
  if key not in data:data[key]=np.load(O/'embeddings'/stage/f'{split}_{mode}.npy')
  return data[key]
 def decode(u,label):
  p=head[label];hidden=np.maximum(u@p['0.weight'].T+p['0.bias'],0);return hidden,hidden@p['2.weight'].T+p['2.bias']
 def wts(split):
  ss=[sources[c] for c in orders[split]];count=collections.Counter(ss);return np.asarray([1/len(count)/count[s] for s in ss]),ss
 def spectrum(x,split):
  x=x.astype(np.float64);w,ss=wts(split);mu=w@x;center=x-mu;cov=center.T@(w[:,None]*center);values=np.maximum(np.linalg.eigvalsh(cov),0);total=values.sum();prob=values/total if total>0 else values;er=float(np.exp(-np.sum(prob[prob>0]*np.log(prob[prob>0])))) if total>0 else 0
  within=x.copy()
  for src in sorted(set(ss)):
   ii=np.array([s==src for s in ss]);within[ii]-=x[ii].mean(0)
  wcov=within.T@(w[:,None]*within);wv=np.maximum(np.linalg.eigvalsh(wcov),0);wp=wv/wv.sum() if wv.sum()>0 else wv;wer=float(np.exp(-np.sum(wp[wp>0]*np.log(wp[wp>0])))) if wv.sum()>0 else 0
  return dict(dim=x.shape[1],source_balanced_std=float(np.sqrt(total/x.shape[1])),effective_rank=er,top1_energy=float(values[-1]/total) if total else 0,within_source_effective_rank=wer,within_source_top1=float(wv[-1]/wv.sum()) if wv.sum()>0 else 0)
 cohorts={}
 for mode in ['main','strict']:
  cohorts[mode]=[dict(source=r['source'],cones=[byid[r['pair_a']]['left_cone'],byid[r['pair_a']]['right_cone'],byid[r['pair_b']]['left_cone'],byid[r['pair_b']]['right_cone']]) for r in schedule if r['mode']==mode and r['seed']==42]
 cohorts['val_negative']=[dict(source=c['source'],cones=c['cones']) for c in valcert]
 def blockmetrics(x,split,cohort):
  ix=indices[split];records=[]
  for row in cohorts[cohort]:
   a,ar,b,br=[x[ix[c]] for c in row['cones']];rms=lambda u,v:float(np.sqrt(np.mean((u.astype(np.float64)-v)**2)))
   records.append(dict(source=row['source'],real=[rms(a,ar),rms(b,br)],fake=[rms(a,br),rms(b,ar)],negative=[rms(a,b),rms(ar,br)]))
  stats=[]
  for source in sorted({r['source'] for r in records}):
   rr=[r for r in records if r['source']==source];real=np.asarray([v for r in rr for v in r['real']]);fake=np.asarray([v for r in rr for v in r['fake']]);neg=np.asarray([v for r in rr for v in r['negative']]);n=len(real);d=dict(source=source,real_rms=float(real.mean()),permuted_rms=float(fake.mean()),negative_rms=float(neg.mean()),real_over_negative=float(real.mean()/max(neg.mean(),1e-12)),same_vs_fake_AUC=float(roc_auc_score([1]*n+[0]*n,-np.r_[real,fake])),same_vs_negative_AUC=float(roc_auc_score([1]*n+[0]*n,-np.r_[real,neg])),block_real_closer=float(np.mean([1 if np.mean(r['real'])<np.mean(r['fake']) else .5 if np.mean(r['real'])==np.mean(r['fake']) else 0 for r in rr])));stats.append(d)
  return {k:float(np.mean([r[k] for r in stats])) for k in stats[0] if k!='source'}|dict(sources=len(stats),blocks=len(records))
 def allval(x):
  ix=indices['val'];values=[]
  for src in sorted({p['source_object'] for p in pairs if p['split']=='val'}):
   pp=[p for p in pairs if p['split']=='val' and p['source_object']==src];ww=np.asarray([weights[p['pair_id']] for p in pp]);ww/=ww.sum();dd=[float(np.sqrt(np.mean((x[ix[p['left_cone']]].astype(float)-x[ix[p['right_cone']]])**2))) for p in pp];values.append(float(np.dot(ww,dd)))
  return float(np.mean(values))
 spectrum_rows=[];metric_rows=[];array_cache={}
 for stage in done['stages']:
  labels=['initial'] if stage=='initial' else ['initial',stage.split('_')[0]]
  if stage=='initial':labels+=['Z','R','P']
  for split in ['train','val']:
   u=load(stage,split);spaces={'root64':u[:,:64],'mean64':u[:,64:],'concat128':u}
   for label in labels:
    hidden,z=decode(u,label);spaces['relu64_'+label]=hidden;spaces['projection32_'+label]=z;array_cache[stage,split,label]=z
   for layer,x in spaces.items():
    row=dict(stage=stage,split=split,layer=layer,**spectrum(x,split));spectrum_rows.append(row)
    for cohort in (['main','strict'] if split=='train' else ['val_negative']):metric_rows.append(dict(stage=stage,split=split,layer=layer,cohort=cohort,all_val_equiv_rms=allval(x) if split=='val' else -1,**blockmetrics(x,split,cohort)))
 # Quantify same fixed encoder under initial/trained heads, and encoder drift.
 drift=[]
 def cka(a,b,split):
  w,ss=wts(split);a=a.astype(float);b=b.astype(float)
  for src in set(ss):
   ii=np.array([s==src for s in ss]);a[ii]-=a[ii].mean(0);b[ii]-=b[ii].mean(0)
  a*=np.sqrt(w[:,None]);b*=np.sqrt(w[:,None]);cross=a.T@b;aa=a.T@a;bb=b.T@b;return float((cross**2).sum()/max(np.sqrt((aa**2).sum()*(bb**2).sum()),1e-20))
 for arm in ['Z','R','P']:
  for split in ['train','val']:
   pre=load(arm+'_pre',split);w,ss=wts(split)
   for suffix in ['best','last','preW_fineBN','fineW_preBN']:
    x=load(arm+'_'+suffix,split);delta=np.sqrt(np.sum(w[:,None]*(x-pre).astype(float)**2)/pre.shape[1]);base=np.sqrt(np.sum(w[:,None]*pre.astype(float)**2)/pre.shape[1]);drift.append(dict(arm=arm,split=split,comparison=suffix+'_vs_pre',concat_relative_drift=float(delta/max(base,1e-12)),within_source_CKA=cka(pre,x,split)))
 noise=[];noise_self=[]
 for arm in ['Z','R','P']:
  for mode in ['eval_running','dropout_running101','dropout_running202','clean_batchBN','dropout_batchBN101','dropout_batchBN202']:
   u=load(arm+'_pre','train',mode);hidden,z=decode(u,arm)
   for label,x in [('concat128',u),('projection32',z)]:noise.append(dict(arm=arm,mode=mode,layer=label,**blockmetrics(x,'train','main'),**spectrum(x,'train')))
  for batch,label in [(False,'runningBN'),(True,'batchBN')]:
   base='dropout_batchBN' if batch else 'dropout_running';ua,ub=[load(arm+'_pre','train',base+str(seed)) for seed in [101,202]]
   for layer,a,b in [('concat128',ua,ub),('projection32',decode(ua,arm)[1],decode(ub,arm)[1])]:
    w,ss=wts('train');rms=np.sqrt(((a.astype(float)-b)**2).mean(1));noise_self.append(dict(arm=arm,BN=label,layer=layer,same_cone_dropout_RMS=float(np.dot(w,rms))))
 table('spectra.csv',spectrum_rows);table('function_distances.csv',metric_rows);table('encoder_drift.csv',drift);table('dropout_BN_modes.csv',noise);table('dropout_same_cone_noise.csv',noise_self)
 results=dict(training_updates=0,optimizer_steps=0,backward_calls=0,new_SAT_queries=0,posthoc=True,no_test_forward=True,spectra=spectrum_rows,function_metrics=metric_rows,drift=drift,noise=noise,noise_self=noise_self,validation_negative_certificates=plan['validation_negative_certificates'],new_forward_evaluations=done['new_model_forwards'],model_states_unchanged=True)
 (O/'DIAGNOSIS_COMPLETE.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 for arm in ['Z','R','P']:
  for stage in [arm+'_pre',arm+'_best',arm+'_preW_fineBN',arm+'_fineW_preBN']:
   vals=[r for r in metric_rows if r['stage']==stage and r['split']=='val' and r['layer'] in ['concat128','projection32_'+arm]]
   print(arm,stage,[(r['layer'],round(r['real_rms'],4),round(r['negative_rms'],4),round(r['same_vs_fake_AUC'],4)) for r in vals],flush=True)
if __name__=='__main__':main()
