"""Exact incoming computation-tree fingerprints and feature overlap; CPU only."""
from pathlib import Path
import csv,json,collections,hashlib,functools
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/round32_20261029';B=R/'_p0pilot/control_fair200_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 contract=read(P/'input_contract.json');norm=np.load(P/'normalization.npz');spec=rows(O/'coordinate_manifest.csv');results=[];exposure=[]
 # No extra C supervision for absent roles is distinct from no historical supervision at all.
 pairs=rows(B/'train_pairs.csv');m=read(B/'manifest.json')
 source_lookup={(x['control_source'],x['control_instance']):x['role_suffix'] for x in rows(R/'_p0pilot/control_risk_20261104/source_node_pairs.csv')}
 for dm in ['orig','trans']:
  rolemap=collections.defaultdict(set)
  for x in pairs:
   if x['domain']!=dm:continue
   classes=set()
   for r in x['roles'].split('|'):
    suf=source_lookup[(x['source'],r)]
    if suf.startswith('T'):cl='trigger'
    elif suf=='HJ':cl='output_hijack'
    elif suf.startswith('P') and suf[1:].isdigit():cl='payload'
    elif suf.startswith('S') and suf[1:].isdigit():cl='payload_select'
    else:cl='other'
    classes.add(cl)
   for cl in classes:rolemap[cl].add(int(x['C']))
  slots=np.load(B/f'{dm}_C_slots.npy')
  for cl in ['trigger','payload','payload_select','output_hijack']:
   exposure.append(dict(domain=dm,role_class=cl,unique_C_nodes=len(rolemap[cl]),extra_C_exposures=int(np.isin(slots,list(rolemap[cl])).sum()),all_extra_exposures=int(slots.size),note='extra targeted pool only; does not imply absent historical labels'))
 dump('role_exposure.csv',exposure)
 for key in ['orig_train','trans_train','trans_val','trans_test']:
  d=R/contract['shared_inputs'][key]['folder'];x=np.load(d/'x39.npy',mmap_mode='r');e=np.load(d/'edge_index.npy',mmap_mode='r');n=len(x)
  order=np.argsort(e[1],kind='stable');src=np.asarray(e[0][order]);counts=np.bincount(e[1],minlength=n);ptr=np.r_[0,np.cumsum(counts)]
  @functools.lru_cache(None)
  def label(i):
   a=np.array(x[i],copy=True);a[25:]=np.clip((a[25:]-norm['mean'][25:])/norm['std'][25:],-10,10);return a.astype('<f4').tobytes()
  @functools.lru_cache(None)
  def tree(i,depth):
   b=label(i)
   if depth:
    incoming=sorted(tree(int(j),depth-1) for j in src[ptr[i]:ptr[i+1]])
    b+=tree(i,depth-1)+b''.join(incoming)
   return hashlib.sha256(b).digest()
  pred={(s,a):np.load(B/f'seed{s}'/a/(key+'_scores.npy'),mmap_mode='r') for s in [42,1,2] for a in ['H','C']}
  for r in spec:
   if r['domain']+'_'+r['split']!=key:continue
   ni=np.array([int(v) for v in r['normal_ids'].split('|')]);ti=np.array([int(v) for v in r['trojan_ids'].split('|')]);xn=np.array(x[ni],copy=True);xt=np.array(x[ti],copy=True)
   zn=np.frombuffer(b''.join(label(int(i)) for i in ni),dtype='<f4').reshape(-1,39);zt=np.frombuffer(b''.join(label(int(i)) for i in ti),dtype='<f4').reshape(-1,39)
   dist=np.sqrt(np.mean((zn[:,None,:]-zt[None,:,:])**2,axis=2));same0=np.array([[label(int(i))==label(int(j)) for j in ti] for i in ni]);same3=np.array([[tree(int(i),3)==tree(int(j),3) for j in ti] for i in ni]);deltas=[]
   for i,j in zip(*np.where(same3)):
    for seed in [42,1,2]:
     for arm in ['H','C']:deltas.append(abs(float(pred[(seed,arm)][ni[i]])-float(pred[(seed,arm)][ti[j]])))
   results.append(dict(domain=r['domain'],split=r['split'],source=r['source'],view=r['view'],role=r['role'],role_class=r['role_class'],normal_nodes=len(ni),trojan_nodes=len(ti),min_39d_rms=float(dist.min()),mean_nearest_39d_rms=float(dist.min(axis=1).mean()),exact_feature_any=int(same0.any()),normal_exact_feature_fraction=float(same0.any(axis=1).mean()),exact_incoming3_any=int(same3.any()),normal_incoming3_fraction=float(same3.any(axis=1).mean()),same3_score_max_difference=max(deltas) if deltas else '',normal_PO_distance_mean=float(xn[:,30].mean()),trojan_PO_distance_mean=float(xt[:,30].mean()),normal_PO_unreachable_fraction=float((xn[:,30]<0).mean()),trojan_PO_unreachable_fraction=float((xt[:,30]<0).mean()),normal_PI_distance_mean=float(xn[:,29].mean()),trojan_PI_distance_mean=float(xt[:,29].mean())))
  print(key,'cached trees',tree.cache_info(),flush=True)
 dump('role_context.csv',results)
 groups=collections.defaultdict(list)
 for r in results:groups[(r['domain'],r['split'],r['source'],r['role_class'])].append(r)
 obj=[]
 for (dm,sp,so,cl),a in groups.items():
  obj.append(dict(domain=dm,split=sp,source=so,role_class=cl,role_views=len(a),exact_feature_fraction=float(np.mean([x['normal_exact_feature_fraction'] for x in a])),exact_incoming3_fraction=float(np.mean([x['normal_incoming3_fraction'] for x in a])),mean_nearest_rms=float(np.mean([x['mean_nearest_39d_rms'] for x in a])),normal_PO_distance=float(np.mean([x['normal_PO_distance_mean'] for x in a])),trojan_PO_distance=float(np.mean([x['trojan_PO_distance_mean'] for x in a]))))
 dump('context_source_class.csv',obj)
 # Unique pairs of aliased role descendants: role counts must not be claimed as independent physical nodes.
 unique=[]
 for key in ['orig_train','trans_train','trans_val','trans_test']:
  q=[r for r in spec if r['domain']+'_'+r['split']==key];cn={(r['view'],i) for r in q for i in r['normal_ids'].split('|')};tn={(r['trojan_view'],i) for r in q for i in r['trojan_ids'].split('|')};unique.append(dict(key=key,role_records=len(q),source_objects=len({r['source'] for r in q}),unique_normal_nodes=len(cn),unique_trojan_nodes=len(tn),normal_role_node_occurrences=sum(len(r['normal_ids'].split('|')) for r in q)))
 dump('unique_support.csv',unique)
 (O/'context.json').write_text(json.dumps(dict(training=0,SAT=0,forward=0,depth=3,direction='edge_index[0] -> edge_index[1]; incoming messages; two branch layers + post layer',fingerprint='SHA256 of normalized 39d label plus previous center and sorted incoming multiset recursively; equality sufficient, inequality not evidence of separability; no undirected conversion',support=unique),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
