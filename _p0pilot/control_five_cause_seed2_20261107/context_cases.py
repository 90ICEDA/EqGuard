"""Current39v3 three-message-layer context check for observed recall-loss cases."""
from pathlib import Path
import collections,csv,functools,hashlib,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/control_five_seed2_20261107';L=R/'_p0pilot/control_loader_po_20261105';C=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 fc=read(C/'input_contract.json');views={(r['key'],r['view']):r for r in rows(L/'view_dictionary.csv')};specs=read(L/'ROLE_PO_PAIRS.json');norm=np.load(C/'normalization.npz');flips=[r for r in rows(O/'role_hit_flips.csv') if r['operation']=='val_recall80' and r['baseline_hit']=='True' and r['new_hit']=='False' and r['key'] in ['trans_test','orig_test']];data={};adj={};cache={};rr=[]
 for r in flips:
  key=r['key'];i=int(r['row']);matches=[s for s in specs if s['key']==key and i in s['trojan_rows']]
  if not matches:continue
  if key not in data:
   folder=R/fc['shared_inputs'][key]['folder'];data[key]=(np.load(folder/'x39.npy',mmap_mode='r'),np.load(folder/'edge_index.npy',mmap_mode='r'))
  x,e=data[key]
  for s in matches:
   for view in [s['normal_view'],s['trojan_view']]:
    if (key,view) in adj:continue
    v=views[key,view];lo,hi=int(v['start']),int(v['stop']);m=(e[1]>=lo)&(e[1]<hi);d=collections.defaultdict(list)
    for src,dst in e[:,m].T:d[int(dst)].append(int(src))
    adj[key,view]=d
   @functools.lru_cache(None)
   def signature(view,n,depth):
    if depth==0:
     v=np.array(x[n],dtype=np.float32,copy=True);v[25:]=np.clip((v[25:]-norm['mean'][25:])/norm['std'][25:],-10,10);v[v==0]=0;return ('features',v.tobytes())
    return (signature(view,n,depth-1),tuple(sorted((signature(view,j,depth-1) for j in adj[key,view].get(n,[])),key=repr)))
   for ni in s['normal_rows']:
    for ti in s['trojan_rows']:
     same=[signature(s['normal_view'],ni,d)==signature(s['trojan_view'],ti,d) for d in range(4)];out=dict(arm=r['arm'],key=key,source=r['source'],role_class=r['role_class'],lost_row=i,normal_source=s['normal_source'],normal_gate=s['normal_source_gate'],normal_row=ni,trojan_row=ti,feature_equal=same[0],incoming1_equal=same[1],incoming2_equal=same[2],incoming3_equal=same[3])
     for arm in ['G0','GM','GBM']:
      p=np.load(OLD/arm/(key+'_scores.npy'),mmap_mode='r');out[arm+'_normal_score']=float(p[ni]);out[arm+'_trojan_score']=float(p[ti]);out[arm+'_score_abs_gap']=float(abs(p[ni]-p[ti]))
     rr.append(out)
 with (O/'recall_loss_context_cases.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 print(json.dumps(rr))
if __name__=='__main__':main()
