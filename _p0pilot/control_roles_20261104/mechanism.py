"""Descriptive cross-role inversion, independent reach checks, and offline curves."""
from pathlib import Path
import csv,json,collections
import numpy as np
from sklearn.metrics import roc_auc_score
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;B=R/'_p0pilot/control_fair200_20261104';P=R/'_p0pilot/round32_20261029'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 rr=[x for x in rows(O/'role_view_seed.csv') if x['operation']=='historical_fpr5'];groups=collections.defaultdict(list)
 for r in rr:groups[(r['seed'],r['domain'],r['split'],r['source'],r['view'])].append(r)
 cross=[]
 for (seed,dm,sp,source,view),aa in groups.items():
  normal=[x for x in aa if x['role_class']=='payload']
  if not normal:continue
  for tc in ['trigger','payload_select','payload']:
   trojan=[x for x in aa if x['role_class']==tc]
   if not trojan:continue
   for arm in ['H','C']:
    n=np.array([float(x['normal_'+arm]) for x in normal]);t=np.array([float(x['trojan_'+arm]) for x in trojan]);order=float(((t[:,None]>n[None,:])+.5*(t[:,None]==n[None,:])).mean())
    cross.append(dict(seed=seed,domain=dm,split=sp,source=source,view=view,arm=arm,normal_role='payload',trojan_role=tc,correct_cross_role_order=order,normal_payload_mean=float(n.mean()),trojan_role_mean=float(t.mean()),normal_roles=len(n),trojan_roles=len(t)))
 dump('cross_role_view.csv',cross)
 sg=collections.defaultdict(list)
 for x in cross:sg[tuple(x[k] for k in ['seed','domain','split','source','arm','trojan_role'])].append(x)
 cs=[]
 for k,aa in sg.items():cs.append(dict(zip(['seed','domain','split','source','arm','trojan_role'],k),correct_cross_role_order=float(np.mean([x['correct_cross_role_order'] for x in aa])),views=len(aa)))
 dump('cross_role_source.csv',cs)
 # Independently certify negative distance using directed reachability, not names/mapping guesses.
 c=read(P/'input_contract.json');spec=rows(O/'coordinate_manifest.csv');reach=[];strata=[]
 for key in ['orig_train','trans_train','trans_val','trans_test']:
  d=R/c['shared_inputs'][key]['folder'];x=np.load(d/'x39.npy',mmap_mode='r');edge=np.load(d/'edge_index.npy',mmap_mode='r');y=np.load(d/'y.npy');tr=np.load(d/'trusted.npy');ph=np.load(d/'physical.npy');n=len(x)
  # Add a super-source with edges to every PO-touching node, then follow reversed edges.
  seeds=np.flatnonzero(x[:,28]>0);src=np.r_[np.asarray(edge[1]),np.full(len(seeds),n)];dst=np.r_[np.asarray(edge[0]),seeds];g=csr_matrix((np.ones(len(src),np.int8),(src,dst)),shape=(n+1,n+1));visited=breadth_first_order(g,n,directed=True,return_predecessors=False);reachable=np.zeros(n+1,bool);reachable[visited]=True;assert np.array_equal(reachable[:n],x[:,30]>=0)
  selected=[r for r in spec if r['domain']+'_'+r['split']==key];posids=sorted({int(i) for r in selected for i in r['trojan_ids'].split('|')});negids=sorted({int(i) for r in selected for i in r['normal_ids'].split('|')})
  reach.append(dict(key=key,all_distance_reach_flags_verified=True,graph_nodes=n,all_trusted_positive=int((tr&ph&(y==1)).sum()),all_trusted_positive_PO_unreachable=int((tr&ph&(y==1)&~reachable[:n]).sum()),paired_unique_T_nodes=len(posids),paired_T_unreachable=int((~reachable[posids]).sum()),paired_unique_N_nodes=len(negids),paired_N_reachable=int(reachable[negids].sum())))
  for seed in [42,1,2]:
   for arm in ['H','C']:
    p=np.load(B/f'seed{seed}'/arm/(key+'_scores.npy'));ev=read(B/f'seed{seed}'/arm/'EVALUATED.json')
    for v in c['shared_inputs'][key]['views']:
     vi=np.arange(v['start'],v['stop']);vi=vi[tr[vi]&ph[vi]&(y[vi]==1)]
     if not len(vi):continue
     for flag in [False,True]:
      ids=vi[reachable[vi]==flag]
      if not len(ids):continue
      for op,th in ev['thresholds'].items():strata.append(dict(seed=seed,arm=arm,key=key,view=v['view'],PO_reachable=flag,operation=op,nodes=len(ids),mean_score=float(p[ids].mean()),recall=float((p[ids]>=th).mean())))
 dump('reach_audit.csv',reach);dump('positive_reach_strata.csv',strata)
 # Two fixed validation-calibrated curve panels; no fitting or test threshold optimization.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 a=rows(O/'validation_calibrated_curve.csv');fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
 for ax,sp in zip(axes,['val','test']):
  for arm,col in [('H','#3973ac'),('C','#d96b27')]:
   gg=collections.defaultdict(list)
   for r in a:
    if r['split']==sp and r['arm']==arm:gg[float(r['validation_target_pooled_recall'])].append(r)
   xx=[100*np.mean([float(r['trojan_macro_recall']) for r in gg[k]]) for k in sorted(gg)];yy=[100*np.mean([float(r['normal_source_fpr']) for r in gg[k]]) for k in sorted(gg)]
   ax.plot(xx,yy,'o-',label=arm,color=col)
  ax.set(xlabel='Actual Trojan macro recall (%)',ylabel='Normal region source-mean FPR (%)',title='Validation' if sp=='val' else 'Test (exploratory)');ax.grid(alpha=.2);ax.legend()
 fig.savefig(O/'recall_fpr_curve.png',dpi=180);plt.close(fig)
 (O/'mechanism.json').write_text(json.dumps(dict(training=0,SAT=0,forward=0,reach_verified=True,curves='thresholds calibrated on validation pooled positive recall; actual macro recall displayed; no test tuning',cross_role='same manufacturing source and implementation; mean descendant scores; not independent gate-level functional proof'),ensure_ascii=False,indent=2),encoding='utf-8')
 print('reach',reach)
 for sp in ['train','val','test']:
  for arm in ['H','C']:
   for cl in ['trigger','payload_select','payload']:
    aa=[x for x in cs if x['domain']=='trans' and x['split']==sp and x['arm']==arm and x['trojan_role']==cl]
    if aa:print(sp,arm,'T'+cl+'>Npayload',np.mean([x['correct_cross_role_order'] for x in aa]))
if __name__=='__main__':main()
