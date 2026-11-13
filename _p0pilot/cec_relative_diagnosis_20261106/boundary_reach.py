"""Read-only full-graph3hop versus free-Q cone boundary audit."""
from pathlib import Path
import collections,csv,json
import numpy as np
from scipy.sparse import csr_matrix
O=Path(__file__).resolve().parent;R=O.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
 panels=read(O/'panels.json');primary=read(R/'_p0pilot/cec_relative_seed42_20261106/PRIMARY_RESULT.json')['primary_sources'];panels['val_primary']=[t for t in panels['val'] if t['source'] in primary];cones={c['cone_id']:c for c in read(R/'_p0pilot/cec_joint_expand_20261105/final_cones.json')};contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')
 selected={c for name in ['train_used','train_unused_same_source','val_primary'] for t in panels[name] for c in t['cones']};byview=collections.defaultdict(set)
 for cid in selected:
  c=cones[cid];byview[c['view']].update(t[1].strip().lstrip('\\') for t in c['leaves'] if t[0]=='Q')
 # Reuse the same global index-name mapping as the verified loader, without labels.
 names=(R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines();qrows={}
 for domain in ['train','val']:
  for v in contract['shared_inputs']['trans_'+domain]['views']:
   if v['view'] not in byview:continue
   wanted=byview[v['view']];rm={n.strip().lstrip('\\'):v['start']+j for j,n in enumerate(names[v['old_start']:v['old_stop']]) if n.strip().lstrip('\\') in wanted};assert set(rm)==wanted;qrows[v['view']]=rm
 del names
 data=[]
 for domain in ['train','val']:
  conf=contract['shared_inputs']['trans_'+domain];edges=np.load(R/conf['folder']/'edge_index.npy',mmap_mode='r');n=conf['nodes'];reverse=csr_matrix((np.ones(edges.shape[1],dtype=np.int8),(edges[1],edges[0])),shape=(n,n));reverse.sum_duplicates()
  def parents(node):return reverse.indices[reverse.indptr[node]:reverse.indptr[node+1]]
  for cid in sorted(selected):
   c=cones[cid]
   if c['split']!=domain:continue
   boundary={qrows[c['view']][t[1].strip().lstrip('\\')] for t in c['leaves'] if t[0]=='Q'};members=set(c['graph_rows']);root=c['root_row'];front={(root,False)};seen=set(front);beyond=set();reach={root};reachedQ=set()
   for depth in range(3):
    nxt=set()
    for node,crossed in front:
     passed=crossed or node in boundary
     if node in boundary:reachedQ.add(node)
     for p in parents(node):
      p=int(p);reach.add(p)
      if passed:beyond.add(p)
      state=(p,passed)
      if state not in seen:nxt.add(state);seen.add(state)
    front=nxt
   data.append(dict(cone_id=cid,split=domain,members=len(members),freeQ_boundaries=len(boundary),Q_boundaries_inside_threehop=len(boundary&reach),has_messages_beyond_freeQ=bool(beyond),nodes_beyond_freeQ=len(beyond),full_graph_3hop_nodes=len(reach),cone_members_missing_from_full3hop=len(members-reach)))
  del reverse,edges
 with (O/'boundary_reach_cones.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 lookup={r['cone_id']:r for r in data};summary=[]
 for name in ['train_used','train_unused_same_source','val_primary']:
  tt=panels[name];sources=sorted({t['source'] for t in tt});vals=[]
  for source in sources:
   ids={c for t in tt if t['source']==source for c in t['cones']};rr=[lookup[c] for c in ids];vals.append(dict(source=source,cones=len(rr),beyond_freeQ_fraction=np.mean([r['has_messages_beyond_freeQ'] for r in rr]),incomplete_internal_fraction=np.mean([r['cone_members_missing_from_full3hop']>0 for r in rr])))
  summary.append(dict(panel=name,cones=len({c for t in tt for c in t['cones']}),sources=len(sources),source_macro_beyond_freeQ_fraction=float(np.mean([r['beyond_freeQ_fraction'] for r in vals])),source_macro_incomplete_internal_fraction=float(np.mean([r['incomplete_internal_fraction'] for r in vals])),per_source=vals))
 (O/'BOUNDARY_REACH.json').write_text(json.dumps(dict(summary=summary,model_forwards=0,optimizer_updates=0,SAT=0,meaning='topological possible paths,not measured message importance;original graph retains DFF incoming edges while functional certificates treat physicalQ as free boundary;even cone-member x39 may include global context'),ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
