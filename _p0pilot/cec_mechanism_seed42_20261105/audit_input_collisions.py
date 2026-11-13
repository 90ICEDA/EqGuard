"""Conservative 3-message-passing indistinguishability audit on certified negatives."""
from pathlib import Path
import collections,csv,hashlib,json,struct
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def main():
 assert not (O/'INPUT_COLLISIONS.json').exists();plan=read(O/'PREPARED.json');pairs={p['pair_id']:p for p in read(J/'final_pairs.json')};cones={c['cone_id']:c for c in read(J/'final_cones.json')};schedule=read(PRE/'schedule.json');certs=read(O/'validation_negative_certificates.json');comparisons=[]
 for mode in ['main','strict']:
  for row in schedule:
   if row['mode']!=mode or row['seed']!=42:continue
   a,b=pairs[row['pair_a']],pairs[row['pair_b']]
   for side in ['left_cone','right_cone']:comparisons.append(dict(cohort=mode,split='train',source=row['source'],a=a[side],b=b[side]))
 for c in certs:
  comparisons.append(dict(cohort='val_negative',split='val',source=c['source'],a=c['cones'][0],b=c['cones'][2]));comparisons.append(dict(cohort='val_negative',split='val',source=c['source'],a=c['cones'][1],b=c['cones'][3]))
 result=[];summaries=[];norm=np.load(R/'_p0pilot/control_boundary_v3_20261104/normalization.npz');contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')
 for split in ['train','val']:
  rr=[r for r in comparisons if r['split']==split];ids={r[k] for r in rr for k in ['a','b']};folder=R/contract['shared_inputs']['trans_'+split]['folder'];raw=np.load(folder/'x39.npy',mmap_mode='r');edge=np.load(folder/'edge_index.npy',mmap_mode='r');order=np.argsort(edge[1],kind='stable');src=np.asarray(edge[0][order]);counts=np.bincount(edge[1],minlength=len(raw));offset=np.r_[0,np.cumsum(counts)];del order;cache={};signatures={}
  def color(node,depth):
   key=(node,depth)
   if key in cache:return cache[key]
   if depth==0:
    x=np.array(raw[node],dtype=np.float32);x[25:]=np.clip((x[25:]-norm['mean'][25:])/norm['std'][25:],-10,10);payload=b'X39:'+x.tobytes()
   else:
    pred=src[offset[node]:offset[node+1]];children=sorted(color(int(n),depth-1) for n in pred);payload=b'GIN_UPPER_BOUND:'+bytes([depth])+color(node,depth-1)+struct.pack('<I',len(children))+b''.join(children)
   cache[key]=hashlib.sha256(payload).digest();return cache[key]
  for cid in ids:
   c=cones[cid];root=color(c['root_row'],3);bag=sorted(color(i,3) for i in c['graph_rows']);signatures[cid]=(root,hashlib.sha256(b''.join(bag)).digest(),len(bag))
  for r in rr:
   a,b=cones[r['a']],cones[r['b']];same=signatures[r['a']]==signatures[r['b']];result.append(dict(**r,same_root_and_pooled_3WL=same,root_features_equal=bool(np.array_equal(raw[a['root_row']],raw[b['root_row']])),same_member_count=len(a['graph_rows'])==len(b['graph_rows'])))
  print('WL audit',split,'cones',len(ids),'node-depth colors',len(cache),flush=True)
 for cohort in ['main','strict','val_negative']:
  rr=[r for r in result if r['cohort']==cohort];unique={tuple(sorted([r['a'],r['b']])):r for r in rr};summaries.append(dict(cohort=cohort,negative_edge_appearances=len(rr),unique_edges=len(unique),appearance_indistinguishable=sum(r['same_root_and_pooled_3WL'] for r in rr),unique_indistinguishable=sum(r['same_root_and_pooled_3WL'] for r in unique.values()),same_root39_appearances=sum(r['root_features_equal'] for r in rr)))
 with (O/'input_collision_edges.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
 (O/'INPUT_COLLISIONS.json').write_text(json.dumps(dict(training_updates=0,backward_calls=0,SAT=0,summary=summaries,scope='sufficient condition only:equal normalized39 initial colors,3 rounds rooted predecessor multiset colors,and exact cone member color bag imply identical eval root+mean under current2+post1 encoder;no converse claim;ignores pin/leaf names as actual model does',hash_collision_assumption='SHA256 equality treated as identity for audit'),ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summaries),flush=True)
if __name__=='__main__':main()
