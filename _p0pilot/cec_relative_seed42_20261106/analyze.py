"""Cached held-out function ranking; primary criteria fixed before training."""
from pathlib import Path
import collections,csv,json
import numpy as np
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1];C=R/'_p0pilot/cec_relative_contract_20261106'
ARMS=['Z','A_R','A_P','S_R','S_P']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def rows(n):
 with (C/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def stats(rr):
 truth=np.array([v for r in rr for v in r['real']]);wrong=np.array([v for r in rr for v in r['wrong']]);third=np.array([v for r in rr for v in r['third']]);win=(truth<wrong).astype(float)+.5*(truth==wrong);tc=(truth<third).astype(float)+.5*(truth==third)
 three=[]
 for a,b,c in zip(truth,wrong,third):
  mn=min(a,b,c);three.append(float(a==mn)/sum(x==mn for x in [a,b,c]))
 src=[]
 for source in sorted({r['source'] for r in rr}):
  gg=[r for r in rr if r['source']==source];a=np.array([v for r in gg for v in r['real']]);b=np.array([v for r in gg for v in r['wrong']]);src.append((np.mean((a<b)+.5*(a==b)),roc_auc_score([1]*len(a)+[0]*len(b),-np.r_[a,b])))
 return dict(triples=len(rr),sources=len(src),directed_queries=len(truth),anchor_win=float(win.mean()),cross_auc=float(roc_auc_score([1]*len(truth)+[0]*len(wrong),-np.r_[truth,wrong])),source_macro_win=float(np.mean([x[0] for x in src])),source_macro_auc=float(np.mean([x[1] for x in src])),true_vs_third_win=float(tc.mean()),three_way_accuracy=float(np.mean(three)),real_rms=float(truth.mean()),wrong_rms=float(wrong.mean()),third_rms=float(third.mean()))
def rank_info(x):
 sv=np.linalg.svd(x-x.mean(0),compute_uv=False);q=sv**2
 if q.sum()==0:return dict(mean_std=float(x.std(0).mean()),effective_rank=0.)
 p=q/q.sum();return dict(mean_std=float(x.std(0).mean()),effective_rank=float(np.exp(-np.sum(p[p>0]*np.log(p[p>0])))))
def evaluate(arm,condition,cache,certs,primary):
 ix={c:i for i,c in enumerate(cache['cone_ids'].tolist())};xx=cache['concat128'].astype(np.float64);spaces={'root64':xx[:,:64],'mean64':xx[:,64:],'concat128':xx,'projection32':cache['projection32'].astype(np.float64)};blocks=[];summary=[];source_summary=[]
 for space,x in spaces.items():
  rr=[]
  for t in certs:
   a,b,c,d,e,f=[x[ix[k]] for k in t['cones']];ds=lambda u,v:float(np.sqrt(np.mean((u-v)**2)))
   rr.append(dict(triple_id=t['triple_id'],source=t['source'],shallow_small=t['shallow_small'],has_mux=t['has_mux'],recipe=t['left_view'].split('__')[-1]+'|'+t['right_view'].split('__')[-1],real=[ds(a,b),ds(c,d),ds(b,a),ds(d,c)],wrong=[ds(a,d),ds(c,b),ds(b,c),ds(d,a)],third=[ds(a,f),ds(c,f),ds(b,e),ds(d,e)]))
  for r in rr:
   blocks.append(dict(arm=arm,condition=condition,space=space,**{k:v for k,v in r.items() if k not in ['real','wrong','third']},**{f'{key}{j}':v for key in ['real','wrong','third'] for j,v in enumerate(r[key])}))
  scopes={'all_descriptive':rr,'primary_two_sources':[r for r in rr if r['source'] in primary],'shallow_primary':[r for r in rr if r['source'] in primary and r['shallow_small']],'deep_primary':[r for r in rr if r['source'] in primary and not r['shallow_small']],'has_mux_primary':[r for r in rr if r['source'] in primary and r['has_mux']],'no_mux_primary':[r for r in rr if r['source'] in primary and not r['has_mux']]}
  for scope,gg in scopes.items():
   if gg:summary.append(dict(arm=arm,condition=condition,space=space,scope=scope,**stats(gg),**rank_info(x)))
  for source in sorted({r['source'] for r in rr}):
   gg=[r for r in rr if r['source']==source];source_summary.append(dict(arm=arm,condition=condition,space=space,source=source,primary=source in primary,**stats(gg)))
 return blocks,summary,source_summary
def main():
 assert read(O/'COMPLETE.json')['all_five_complete'];certs=read(C/'evaluation_panel.json');primary=sorted({r['source'] for r in rows('evaluation_support.csv') if r['primary_source']=='True'});assert len(primary)==2
 blocks=[];summary=[];by_source=[]
 for arm in ARMS:
  with np.load(O/f'val_{arm}_remap9000.npz') as cache:
   b,s,ss=evaluate(arm,'correct',cache,certs,primary);blocks+=b;summary+=s;by_source+=ss
 sensitivities=[]
 with np.load(O/'val_S_R_remap9000.npz') as c:reference=c['concat128'].astype(np.float64);reference_ids=c['cone_ids'].tolist()
 for condition in ['wrong_roles','pin_disabled_boundary_retained']:
  with np.load(O/f'sensitivity_S_R_{condition}.npz') as cache:
   assert cache['cone_ids'].tolist()==reference_ids;b,s,ss=evaluate('S_R',condition,cache,certs,primary);blocks+=b;summary+=s;by_source+=ss;root=cache['concat128'][:,:64].astype(np.float64);ref=reference[:,:64];delta=root-ref
   primary_stat=next(r for r in s if r['space']=='root64' and r['scope']=='primary_two_sources')
   sensitivities.append(dict(condition=condition,root_RMS_change=float(np.sqrt(np.mean(delta**2))),relative_to_root_std=float(np.sqrt(np.mean(delta**2))/(ref.std()+1e-30)),**{k:primary_stat[k] for k in ['source_macro_win','source_macro_auc']}))
 table('evaluation_blocks.csv',blocks);table('evaluation_summary.csv',summary);table('evaluation_by_source.csv',by_source);table('semantic_sensitivity.csv',sensitivities)
 get=lambda arm:next(r for r in summary if r['arm']==arm and r['condition']=='correct' and r['space']=='root64' and r['scope']=='primary_two_sources')
 sr,sp,z,ar,ap=[get(a) for a in ['S_R','S_P','Z','A_R','A_P']];contrasts={metric:dict(S_R_minus_S_P=sr[metric]-sp[metric],S_R_minus_Z=sr[metric]-z[metric],A_R_minus_A_P=ar[metric]-ap[metric],difference_of_differences=(sr[metric]-sp[metric])-(ar[metric]-ap[metric])) for metric in ['source_macro_win','source_macro_auc','cross_auc']}
 per_source=[]
 for source in primary:
  g=lambda arm:next(r for r in by_source if r['arm']==arm and r['condition']=='correct' and r['space']=='root64' and r['source']==source)
  per_source.append(dict(source=source,win_S_R_minus_S_P=g('S_R')['anchor_win']-g('S_P')['anchor_win'],win_S_R_minus_Z=g('S_R')['anchor_win']-g('Z')['anchor_win']))
 win_gate=contrasts['source_macro_win']['S_R_minus_S_P']>=.02 and contrasts['source_macro_win']['S_R_minus_Z']>=.02;source_gate=all(r['win_S_R_minus_S_P']>=0 and r['win_S_R_minus_Z']>=0 for r in per_source);auc_agrees=contrasts['source_macro_auc']['S_R_minus_S_P']>0 and contrasts['source_macro_auc']['S_R_minus_Z']>0
 write('PRIMARY_RESULT.json',dict(primary_sources=primary,metric_scope='root64 source-balanced same-anchor true-v-swapped,not detectionAP',root64={a:get(a) for a in ARMS},contrasts=contrasts,per_source=per_source,predeclared_win_gate=win_gate,predeclared_source_direction_gate=source_gate,source_macro_AUC_direction_agrees=auc_agrees,functional_performance_gate=win_gate and source_gate and auc_agrees,semantic_sensitivity='diagnostic only;no new posthoc numerical threshold',single_seed=True,host_count=1,no_detection_AP=True))
 print(json.dumps(dict(results={a:{k:get(a)[k] for k in ['source_macro_win','source_macro_auc','cross_auc']} for a in ARMS},contrasts=contrasts,performance_gate=win_gate and source_gate and auc_agrees),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
