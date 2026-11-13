"""Read-only native-port reconstruction of normal-region reach and manufacture boundary."""
from pathlib import Path
import sys,csv,json,collections
import numpy as np
from supervision_loader import FiveGroupLoader,sha,read,archive
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31';V=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R));sys.path.insert(0,str(V))
from independent_net import raw_network
from phase2 import netlist_lib as NL
def rr(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 assert not (O/'REACH_AUDIT.json').exists();l=FiveGroupLoader();vs=rr(O/'view_dictionary.csv');lib=NL.load_library(F/'verilog_lib.v');names={};provenance={};bindings={};summary=[];targets=[];source_rows=[];witness=[];mis=[]
 for dm,path in [('orig',R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt'),('trans',F/'data/processed/node_names_trans.txt')]:names[dm]=[n.strip().lstrip('\\') for n in path.read_text(encoding='utf-8').splitlines()];bindings[str(path.relative_to(R))]=sha(path)
 for host in ['s38417t100','s38584t100']:
  p=R/'generate_trans/hosts'/host/'provenance.json';provenance.update({v['view']:(p,v) for v in read(p) if v.get('kind')=='control'});bindings[str(p.relative_to(R))]=sha(p)
 # Add active equivalent controls as positive reach checks, using historical cohort provenance.
 for v in rr(R/'_p0pilot/control_retention_20261104/cohort_candidates.csv'):
  if v['split']=='train' and 'a4ctlequiv' in v['source_view']:
   p=R/v['provenance'];bindings[str(p.relative_to(R))]=sha(p)
   provenance.update({q['view']:(p,q) for q in read(p) if q.get('view')==v['source_view']})
 jobs=[]
 for v in vs:
  if v['kind']!='control':continue
  dm,sp=v['key'].split('_');a=l.arrays(dm,sp);mem=archive(O/('PO_membership_'+v['key']+'.npz'));lo,hi=int(v['start']),int(v['physical_stop']);roi=mem['normal_primary_added'][lo:hi];M=mem['normal_M'][lo:hi]
  if (dm=='orig' and sp in ['val','test']) or (dm=='trans' and sp in ['val','test'] and (roi.any() or M.any())) or (dm=='orig' and sp=='train' and 'a4ctlequiv' in v['view']):jobs.append(v)
 for number,v in enumerate(jobs):
  key=v['key'];dm,sp=key.split('_');a=l.arrays(dm,sp);mem=archive(O/('PO_membership_'+key+'.npz'));lo,hi,stop=int(v['start']),int(v['physical_stop']),int(v['stop']);ns=names[dm][int(v['old_start']):int(v['old_stop'])];path=F/dm/(v['view']+'.v') if dm=='orig' else F/'trans'/(v['view']+'.v');native=raw_network(path,lib);bindings[str(path.relative_to(R))]=sha(path);allnames=ns+native['virtual_names'];assert len(allnames)==stop-lo and set(allnames)==set(native['cells']);lookup={n:i for i,n in enumerate(allnames)}
  dist={n:0 for n in native['pocells']};nextnode={};queue=collections.deque(sorted(native['pocells']))
  while queue:
   t=queue.popleft()
   for s in sorted(native['pred'][t]):
    if s not in dist:dist[s]=dist[t]+1;nextnode[s]=t;queue.append(s)
  expected=np.array([dist.get(n,-1) for n in allnames]);saved=a['x39'][lo:stop,30];bad=np.flatnonzero(expected!=saved)
  for j in bad:mis.append(dict(key=key,view=v['view'],row=lo+int(j),name=allnames[j],saved=float(saved[j]),native=int(expected[j])))
  # Graph direction/alias construction is checked from native cell pins as well.
  native_edges={(lookup[s],lookup[t]) for s,tt in native['succ'].items() for t in tt};e=a['edge_index'];mask=(e[0]>=lo)&(e[0]<stop);se=e[:,mask]-lo;saved_edges=set(zip(map(int,se[0]),map(int,se[1])));assert native_edges==saved_edges,(key,v['view'],'native/saved directed edges differ')
  M=mem['normal_M'][lo:hi];roi=mem['normal_primary_added'][lo:hi];select=M|roi
  for j in np.flatnonzero(select):
   n=ns[j];targets.append(dict(key=key,view=v['view'],source=v['source'],row=lo+int(j),name=n,is_M=bool(M[j]),is_primary_added=bool(roi[j]),saved_PO_distance=int(saved[j]),native_PO_distance=int(expected[j]),trusted=bool(a['trusted'][lo+j]),label=int(a['y'][lo+j])))
   if n in dist:
    trace=[n]
    while trace[-1] in nextnode:trace.append(nextnode[trace[-1]])
    witness.append(dict(key=key,view=v['view'],source=v['source'],row=lo+int(j),name=n,distance=int(dist[n]),PO_driver=trace[-1],path=' -> '.join(trace),driver_pin_nets='|'.join(p+'='+net for p,net in native['pins'][trace[-1]][1] if net in native['po'])))
  if dm=='orig' and v['source'] in provenance:
   pp,pd=provenance[v['source']];new={n.strip().lstrip('\\') for n in pd['new_gates']};assert new<=set(native['cells']);cross=[(s,t) for s in new for t in native['succ'][s] if t not in new];terminal=[]
   for n in new:
    typ,conn=native['pins'][n]
    for p,net in conn:
     if p in lib[typ]['outputs'] and not native['cons'].get(net):terminal.append(n+'.'+p+'='+net+(' [PO]' if net in native['po'] else ' [no consumers/non-PO]'))
   source_rows.append(dict(key=key,source=v['source'],ctl_type=pd.get('ctl_type'),payload_target=pd.get('payload_target',''),payload_wire=pd.get('payload_wire',''),new_nodes=len(new),native_reachable_new=sum(n in native['reachable'] for n in new),new_to_host_edges=len(cross),new_PO_drivers=len(new&native['pocells']),terminal_output_pins='|'.join(sorted(terminal)),provenance=str(pp.relative_to(R))))
  summary.append(dict(key=key,view=v['view'],source=v['source'],physical=hi-lo,native_PO_drivers=len(native['pocells']),native_reachable_physical=sum(n in dist for n in ns),M_nodes=int(M.sum()),M_native_reachable=int((expected[:hi-lo][M]>=0).sum()),primary_nodes=int(roi.sum()),primary_native_reachable=int((expected[:hi-lo][roi]>=0).sum()),distance_mismatches=len(bad),directed_edges_match=True))
  if (number+1)%10==0:print('native reach audited',number+1,'/',len(jobs),flush=True)
 for n,a in [('native_reach_per_view.csv',summary),('native_reach_targets.csv',targets),('manufactured_normal_boundaries.csv',source_rows),('reachable_normal_witnesses.csv',witness),('PO_distance_mismatches.csv',mis)]:dump(n,a)
 for p in [F/'verilog_lib.v',V/'independent_net.py',R/'phase2/inject_trojan.py',Path(__file__)]:bindings[str(p.relative_to(R))]=sha(p)
 result=dict(training=0,model_forward=0,SAT=0,native_views=len(jobs),independent_port_and_bit_alias_graphs=True,all_directed_edges_match=True,all_distances_match=not mis,targets=len(targets),target_membership='union M/primary, duplicates removed within view',reachable_target_witnesses=len(witness),source_boundaries=len(source_rows),inputs=bindings)
 (O/'REACH_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:result[k] for k in ['native_views','all_distances_match','targets','reachable_target_witnesses']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
