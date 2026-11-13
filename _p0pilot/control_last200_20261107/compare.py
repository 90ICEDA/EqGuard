"""Read-only checkpoint comparison; no torch/optimizer/SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
SEEDS=[42,1,2];ARMS=['G0','GB','GM','GBM','GAll'];KEYS=[d+'_'+s for d in ['orig','trans'] for s in ['train','val','test']]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def folder(protocol,seed):return R/f'_p0pilot/control_five_seed{seed}_20261107' if protocol=='selected' else O/f'seed{seed}'
def num(v):return float(v) if v not in ['',None] else None
def summarize(rr,keys,cols):
 g=collections.defaultdict(list)
 for r in rr:g[tuple(r[k] for k in keys)].append(r)
 out=[]
 for k,v in sorted(g.items()):
  assert len(v)==3 and {r['seed'] for r in v}==set(SEEDS)
  q=dict(zip(keys,k),seeds=3)
  for c in cols:
   a=[r[c] for r in v if r[c] is not None];assert len(a) in [0,3];q[c+'_mean']=float(np.mean(a)) if a else None;q[c+'_sampleSD']=float(np.std(a,ddof=1)) if a else None;q[c+'_positive_seeds']=sum(x>1e-12 for x in a);q[c+'_negative_seeds']=sum(x< -1e-12 for x in a)
  out.append(q)
 return out
def ap_parts(y,p):
 order=np.argsort(-p,kind='stable');s=p[order];t=np.cumsum(y[order]==1);end=np.r_[np.flatnonzero(s[:-1]!=s[1:]),len(s)-1];group=np.searchsorted(end,np.arange(len(s)));precision=t[end[group]]/(end[group]+1);parts=np.zeros(len(y));parts[order]=precision*(y[order]==1)/sum(y==1);return parts
def main():
 assert read(O/'INFERENCE_COMPLETE.json')['passed'];views=rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv');fc=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');data={k:{n:np.load(R/q['folder']/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']} for k,q in fc['shared_inputs'].items()};lineage=rows(O/'ALPHA_POSITIVE_LINEAGE.csv');lm={int(r['row']):r for r in lineage};ap=[];source=[];keyrows=[];alpha=[];thresholds=[];checks=0
 for protocol in ['selected','last200']:
  for seed in SEEDS:
   f=folder(protocol,seed);macro=rows(f/'source_macro_metrics.csv');ps=rows(f/'per_source_scope_PO.csv');roles=rows(f/'role_source_macro.csv');whole=rows(f/'whole_normal_macro.csv');viewrefs={(r['arm'],r['key'],r['view']):r for r in rows(f/'per_view_scope_PO.csv') if r['operation']=='val_recall80' and r['scope']=='trusted_all' and r['PO_bin']=='all'}
   assert sha(f/'frozen_role_assignments.csv')==sha(folder('selected',42)/'frozen_role_assignments.csv')
   for arm in ARMS:
    ev=read(f/arm/'EVALUATED.json');tv=np.load(f/arm/'trans_val_scores.npy',mmap_mode='r');a=data['trans_val'];pos=tv[a['trusted']&(a['y']==1)];neg=tv[a['trusted']&(a['y']==0)];expected=dict(historical_fpr5=float(np.nextafter(np.quantile(neg,.95),np.inf)),val_recall80=float(np.quantile(pos,.2,method='lower')),val_recall90=float(np.quantile(pos,.1,method='lower')))
    for op,t in expected.items():assert t==ev['thresholds'][op];thresholds.append(dict(protocol=protocol,seed=seed,arm=arm,operation=op,threshold=t,checkpoint_update=ev['selected']['epoch']))
    for key in KEYS:
     p=np.load(f/arm/(key+'_scores.npy'),mmap_mode='r');a=data[key];assert sha(f/arm/(key+'_scores.npy'))==ev['prediction_sha'][key]
     vv=[v for v in views if v['key']==key and v['kind']=='trojan'];sv=collections.defaultdict(list)
     for v in vv:
      lo,hi=int(v['start']),int(v['physical_stop']);ids=np.arange(lo,hi);ids=ids[a['trusted'][ids]&a['physical'][ids]];y=a['y'][ids];scores=p[ids];parts=ap_parts(y,scores);value=float(parts.sum());reference=viewrefs[arm,key,v['view']];assert abs(value-float(reference['AP']))<1e-12;checks+=1;sv[v['source']].append(value)
      if key=='trans_test' and '__injalpha_' in v['view'] and arm in ['G0','GM','GBM']:
       for i,part in zip(ids[y==1],parts[y==1]):
        assert int(i) in lm;lr=lm[int(i)];alpha.append(dict(protocol=protocol,seed=seed,arm=arm,view=v['view'],source=v['source'],row=int(i),node_name=lr['node_name'],parents=lr['parents'],manufacturing_role=lr['manufacturing_role'],nature=lr['nature'],score=float(p[i]),negative_above=int(np.sum((y==0)&(scores>=p[i]))),AP_contribution=float(part)))
     for src,values in sv.items():
      value=float(np.mean(values));ref=next(x for x in ps if x['arm']==arm and x['key']==key and x['operation']=='val_recall80' and x['scope']=='trusted_all' and x['PO_bin']=='all' and x['kind']=='trojan' and x['source']==src);assert abs(value-float(ref['AP']))<1e-12;source.append(dict(protocol=protocol,seed=seed,arm=arm,key=key,source=src,AP=value))
     value=float(np.mean([np.mean(v) for v in sv.values()]));ref=next(x for x in macro if x['arm']==arm and x['key']==key and x['operation']=='val_recall80' and x['scope']=='trusted_all' and x['PO_bin']=='all' and x['kind']=='trojan');assert abs(value-float(ref['AP']))<1e-12;ap.append(dict(protocol=protocol,seed=seed,arm=arm,key=key,AP=value))
     if key.endswith('train'):continue
     for op in expected:
      base=[r for r in macro if r['arm']==arm and r['key']==key and r['operation']==op and r['PO_bin']=='all']
      def m(scope,col,kind=None):
       rr=[r for r in base if r['scope']==scope and (kind is None or r['kind']==kind)];assert len(rr)==1;return num(rr[0][col])
      role={r['role_class']:num(r['recall']) for r in roles if r['arm']==arm and r['key']==key and r['operation']==op};w=next(r for r in whole if r['arm']==arm and r['key']==key and r['operation']==op)
      keyrows.append(dict(protocol=protocol,seed=seed,arm=arm,key=key,operation=op,node_AP=value,normal_added_FPR=m('normal_primary_added','FPR'),normal_all_FPR=m('normal_all','FPR'),all_positive_recall=m('trojan_positive','recall','trojan'),trigger_recall=role.get('trigger'),payload_recall=role.get('payload'),payload_select_recall=role.get('payload_select'),whole_normal_view_alarm=num(w['alarm']),whole_normal_source_alarm=num(w['source_any_alarm'])))
 table('AP_all.csv',ap);table('AP_meanSD.csv',summarize(ap,['protocol','arm','key'],['AP']));table('AP_source_all.csv',source);table('THRESHOLDS.csv',thresholds);table('ALPHA_NODE_RANKING.csv',alpha);table('KEY_RESULTS_all.csv',keyrows);metrics=[k for k in keyrows[0] if k not in ['protocol','seed','arm','key','operation']];table('KEY_RESULTS_meanSD.csv',summarize(keyrows,['protocol','arm','key','operation'],metrics))
 alook={(r['protocol'],r['seed'],r['arm'],r['row']):r for r in alpha};node_delta=[]
 for r in alpha:
  if r['arm']=='G0':continue
  b=alook[r['protocol'],r['seed'],'G0',r['row']];node_delta.append(dict(**{k:r[k] for k in ['protocol','seed','view','row','node_name','parents','manufacturing_role','nature']},comparison=r['arm']+'-G0',score_delta=r['score']-b['score'],negative_above_delta=r['negative_above']-b['negative_above'],view_AP_contribution_delta=r['AP_contribution']-b['AP_contribution'],source_AP_contribution_delta=(r['AP_contribution']-b['AP_contribution'])/5))
 table('ALPHA_NODE_DELTAS.csv',node_delta)
 grouped=collections.defaultdict(list)
 for r in node_delta:grouped[tuple(r[k] for k in ['protocol','seed','comparison','manufacturing_role'])].append(r)
 ar=[dict(zip(['protocol','seed','comparison','manufacturing_role'],k),nodes=len(v),source_AP_contribution_delta=sum(x['source_AP_contribution_delta'] for x in v)) for k,v in sorted(grouped.items())];table('ALPHA_SUPPLEMENTAL_ROLE_AP.csv',ar)
 def deltas(rr,cols,extra):
  lookup={(r['protocol'],r['seed'],r['arm'],r['key'],*[r[k] for k in extra]):r for r in rr};out=[]
  for r in rr:
   if r['arm']=='G0':continue
   b=lookup[r['protocol'],r['seed'],'G0',r['key'],*[r[k] for k in extra]];out.append(dict(protocol=r['protocol'],seed=r['seed'],comparison=r['arm']+'-G0',key=r['key'],**{k:r[k] for k in extra},**{c:None if r[c] is None or b[c] is None else r[c]-b[c] for c in cols}))
  return out
 ad=deltas(ap,['AP'],[]);sd=deltas(source,['AP'],['source']);kd=deltas(keyrows,metrics,['operation']);table('PAIRED_AP_all.csv',ad);table('PAIRED_AP_meanSD.csv',summarize(ad,['protocol','comparison','key'],['AP']));table('PAIRED_SOURCE_AP_all.csv',sd);table('PAIRED_SOURCE_AP_meanSD.csv',summarize(sd,['protocol','comparison','key','source'],['AP']));table('PAIRED_KEY_all.csv',kd);table('PAIRED_KEY_meanSD.csv',summarize(kd,['protocol','comparison','key','operation'],metrics))
 # How the fixed-round choice changes the treatment-minus-G0 difference.
 lookup={(r['protocol'],r['seed'],r['comparison'],r['key']):r for r in ad};interaction=[]
 for r in ad:
  if r['protocol']!='last200':continue
  b=lookup['selected',r['seed'],r['comparison'],r['key']];interaction.append(dict(seed=r['seed'],comparison=r['comparison'],key=r['key'],selected_delta=b['AP'],last200_delta=r['AP'],selection_interaction=r['AP']-b['AP']))
 table('SELECTION_INTERACTION.csv',interaction);table('SELECTION_INTERACTION_meanSD.csv',summarize(interaction,['comparison','key'],['selected_delta','last200_delta','selection_interaction']))
 for p,h in read(O/'PROTECTED_INPUTS.json').items():assert sha(R/p)==h,p
 for p,h in read(O/'LINEAGE_VERIFIED.json')['protected_inputs'].items():assert sha(R/p)==h,p
 write=dict(passed=True,independent_AP_view_checks=checks,source_macro_AP_verified=True,all_prediction_hashes_verified=True,validation_only_thresholds_verified=True,frozen_roles_unchanged=True,old_inputs_unchanged=True,model_updates=0,SAT=0,labels_changed=False,numerical_control='9 repeats;GPU BF16 scatter is not bitwise deterministic;details in NUMERICAL_REPRODUCTION.json',selection_test='fixed200 sensitivity audit;does not replace original frozen selection rule or tune on test')
 (O/'VERIFIED.json').write_text(json.dumps(write,indent=2),encoding='utf-8');print(write)
if __name__=='__main__':main()
