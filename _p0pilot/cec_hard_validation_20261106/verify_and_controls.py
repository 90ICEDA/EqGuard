"""Independent CPU metric/provenance checks plus fixed structural controls."""
from pathlib import Path
import collections,csv,hashlib,importlib.util,json,math
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;H=R/'_p0pilot/cec_hard_boundary_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def auc_manual(positive,negative,weights):
 a=sorted([(float(v),1,float(w)) for v,w in zip(positive,weights)]+[(float(v),0,float(w)) for v,w in zip(negative,weights)])
 # Lower distance is a positive prediction, so positives win over larger negatives.
 neg=sum(w for _,y,w in a if not y);pos=sum(w for _,y,w in a if y);below=0.;total=0.;i=0
 while i<len(a):
  j=i+1
  while j<len(a) and a[j][0]==a[i][0]:j+=1
  nw=sum(w for _,y,w in a[i:j] if not y);pw=sum(w for _,y,w in a[i:j] if y)
  total+=pw*(neg-below-.5*nw);below+=nw;i=j
 return total/(pos*neg)
def direct_metrics(units,ids,x):
 ix={c:j for j,c in enumerate(ids)};stats=[];raw=[]
 for u in units:
  v=np.array([x[ix[c]] for c in u['cones']],dtype=np.float64);n=u['functions'];a=[];b=[];wins=[];top=[]
  for fun in range(n):
   for side in range(2):
    anchor=2*fun+side;d=[math.dist(v[anchor],v[2*j+1-side])/math.sqrt(v.shape[1]) for j in range(n)];target=d[fun];best=min(d);top.append((1/sum(z==best for z in d)) if target==best else 0.)
    for j in range(n):
     if j==fun:continue
     a.append(target);b.append(d[j]);wins.append(float(target<d[j])+.5*float(target==d[j]))
  raw.append(dict(unit=u['unit_id'],source=u['source'],win=float(np.mean(wins)),top=float(np.mean(top)),a=a,b=b))
 for source in sorted({r['source'] for r in raw}):
  zz=[r for r in raw if r['source']==source];a=[v for r in zz for v in r['a']];b=[v for r in zz for v in r['b']];w=[1/len(r['a']) for r in zz for _ in r['a']]
  stats.append(dict(source=source,win=float(np.mean([r['win'] for r in zz])),auc=auc_manual(a,b,w),top=float(np.mean([r['top'] for r in zz]))))
 return dict(pairwise_win=float(np.mean([s['win'] for s in stats])),function_auc=float(np.mean([s['auc'] for s in stats])),top1=float(np.mean([s['top'] for s in stats])))
def main():
 assert read(O/'ANALYSIS_COMPLETE.json')['passed'] and read(O/'MODELS_UNCHANGED.json')['passed']
 protected=read(O/'INTERFACE_VERIFIED.json')['protected_files']
 for p,h in protected.items():assert sha(R/p)==h,p
 units=read(H/'hard_panel.json');gg=read(O/'local_graphs.json');graphs=dict(zip(gg['cone_ids'],gg['graphs']));cones={c['cone_id']:c for c in read(R/'_p0pilot/cec_joint_expand_20261105/final_cones.json')}
 # Independently check each selected structure profile; no reliance on baseline constants.
 def profile(cid):
  c=cones[cid];g=graphs[cid];inc=collections.defaultdict(list);hist=collections.Counter(g['op']);leaf={tuple(t[:3]) for t in c['leaves']}
  for a,b,role,phase in g['edge']:inc[b].append((a,phase))
  base=(len(c['members']),max(g['level']),len(leaf))
  ext=base+tuple(hist[i] for i in range(9))+(sum(e[3] for e in g['edge']),sum(len(v)-len(set(v)) for v in inc.values()))
  return base,ext,tuple(sorted(leaf))
 for u in units:
  for side in [0,1]:
   p=[profile(c) for c in u['cones'][side::2]];assert all(z[:2]==p[0][:2] for z in p)
   if u['tier']=='T3_same_boundary':assert all(z[2]==p[0][2] for z in p)
 # Independent metrics on all arms/readouts for the all-pairwise and triple main sets.
 existing=rows(O/'function_metrics.csv');checks=[]
 for split in ['train','val']:
  for arm in ['INIT','Z','A_R','A_P','S_R','S_P']:
   with np.load(O/f'{split}_{arm}.npz') as z:
    ids=z['cone_ids'].tolist();spaces={'root64':z['concat128'][:,:64],'mean64':z['concat128'][:,64:],'concat128':z['concat128'],'projection32':z['projection32']}
   for name,x in spaces.items():
    assert np.isfinite(x).all()
    for group in ['all_pairwise','triples_only','pairs_only']:
     ss=[u for u in units if u['split']==split and (group=='all_pairwise' or (u['functions']==3 if group=='triples_only' else u['functions']==2))]
     if not ss:continue
     actual=direct_metrics(ss,ids,x);prior=next(r for r in existing if r['split']==split and r['arm']==arm and r['space']==name and r['group']==group)
     for k,v in actual.items():assert abs(v-float(prior[k]))<1e-10,(split,arm,name,group,k,v,prior[k])
     checks.append(dict(split=split,arm=arm,space=name,group=group,independent_cpu_passed=True))
 # Extra controls after the primary evaluation: no fitted model/statistical projection.
 contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');norm=np.load(R/'_p0pilot/control_boundary_v3_20261104/normalization.npz');controls=[]
 for split in ['train','val']:
  panel=[u for u in units if u['split']==split];ids=sorted({c for u in panel for c in u['cones']});q=contract['shared_inputs']['trans_'+split];path=R/q['folder']/'x39.npy';assert sha(path)==contract['files'][str(path.relative_to(R))]
  raw=np.load(path,mmap_mode='r');root=[];mean=[]
  for cid in ids:
   c=cones[cid];xx=np.array(raw[c['graph_rows']],np.float64);rr=np.array(raw[c['root_row']],np.float64)
   xx[:,25:]=np.clip((xx[:,25:]-norm['mean'][25:])/norm['std'][25:],-10,10);rr[25:]=np.clip((rr[25:]-norm['mean'][25:])/norm['std'][25:],-10,10)
   root.append(rr);mean.append(xx.mean(0))
  root=np.array(root);mean=np.array(mean)
  vectors=[('root_gate25',root[:,:25]),('root_struct14',root[:,25:]),('mean_gate25',mean[:,:25]),('mean_struct14',mean[:,25:]),('root39',root),('concat_root_mean39',np.c_[root,mean])]
  vectors += [('root_col'+str(j)+'_'+contract['columns39'][j],root[:,j:j+1]) for j in range(25,39)]
  for name,x in vectors:
   for group in ['all_pairwise','triples_only']:
    ss=panel if group=='all_pairwise' else [u for u in panel if u['functions']==3]
    controls.append(dict(split=split,control=name,group=group,units=len(ss),sources=len({u['source'] for u in ss}),**direct_metrics(ss,ids,x)))
 table('independent_metric_checks.csv',checks);table('additional_structure_controls.csv',controls)
 coverage=[]
 for split in ['train','val']:
  ss=[u for u in units if u['split']==split]
  for source in sorted({u['source'] for u in ss}):
   zz=[u for u in ss if u['source']==source];coverage.append(dict(split=split,source=source,units=len(zz),triples=sum(u['functions']==3 for u in zz),pairs_only=sum(u['functions']==2 for u in zz),T3=sum(u['tier']=='T3_same_boundary' for u in zz),MUX=sum(u['has_mux'] for u in zz),shallow_small=sum(u['shallow_small'] for u in zz),prior_pairs_zero=sum(u['prior_supervised_pair_count']==0 for u in zz),prior_observed_signatures_zero=sum(u['prior_observed_signature_count']==0 for u in zz)))
 table('coverage_by_source.csv',coverage)
 for p,h in protected.items():assert sha(R/p)==h,p
 outputs=[p for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.csv','.npz','.json'] and p.name not in ['VERIFIED.json','OUTPUT_MANIFEST.json']]
 manifest={p.name:sha(p) for p in outputs};write('OUTPUT_MANIFEST.json',manifest)
 write('VERIFIED.json',dict(passed=True,independent_metric_tables=len(checks),checks='independent Euclidean math.dist / manually weighted pairwise AUC;actual profiles;frozen hashes;finite arrays',interface_validation_passed=True,model_weights_and_BN_unchanged=True,extra_structure_controls='posthoc diagnostic only,not replacements for primary',optimizer_updates=0,backwards=0,SAT=0,new_real_input_patterns=0,test_reads=0,model_forwards=read(O/'EXTRACTION_COMPLETE.json')['new_model_forwards'],manifest_sha=sha(O/'OUTPUT_MANIFEST.json'),protected_files_checked=len(protected)))
 print('INDEPENDENT_VERIFIED',len(checks),flush=True)
if __name__=='__main__':main()
