"""Train/validation boundary qualification. Independent pin graph, no solver or model."""
from pathlib import Path
import sys,json,csv,collections,hashlib
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/round32_20261029';F=R/'generate_trans/folds/hosts_bt31';B=R/'_p0pilot/control_fair200_20261104'
sys.path.insert(0,str(R));from phase2 import netlist_lib as NL
from independent_net import raw_network,norm
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 O.mkdir(exist_ok=True);c=read(P/'input_contract.json');spec=[x for x in rows(R/'_p0pilot/control_roles_20261104/coordinate_manifest.csv') if x['split'] in ['train','val']];sources=rows(R/'_p0pilot/control_risk_20261104/source_node_pairs.csv');eligible_val={x['source'] for x in spec if x['split']=='val'}
 allnames={dm:(F/'data/processed/node_names_trans.txt' if dm=='trans' else P/'orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines() for dm in ['orig','trans']}
 ctx={};views={}
 for key,q in c['shared_inputs'].items():
  if key.endswith('_test'):continue
  ctx[key]={n:np.load(R/q['folder']/(n+'.npy'),mmap_mode='r') for n in ['x39','edge_index','y','trusted']}
  for v in q['views']:views[(key,v['view'])]=v
 for x in sources:
  if x['split']!='val' or x['role_pair']!='True' or x['control_source'] not in eligible_val:continue
  def coordinate(view,node):
   v=views[('orig_val',view)];nn=[norm(n) for n in allnames['orig'][v['old_start']:v['old_stop']]];return v['start']+nn.index(node)
  suffix=x['role_suffix'];cl='trigger' if suffix.startswith('T') else 'payload' if suffix.startswith('P') and suffix[1:].isdigit() else 'output_hijack' if suffix=='HJ' else 'payload_select' if suffix.startswith('S') else 'other'
  spec.append(dict(domain='orig',split='val',source=x['control_source'],trojan_source=x['trojan_source'],view=x['control_source'],trojan_view=x['trojan_source'],role=suffix,role_class=cl,normal_ids=str(coordinate(x['control_source'],x['control_instance'])),trojan_ids=str(coordinate(x['trojan_source'],x['trojan_instance']))))
 pairs=rows(B/'train_pairs.csv');pool={(x['domain'],int(x['C'])):x for x in pairs};lib=NL.load_library(F/'verilog_lib.v');groups=collections.defaultdict(list)
 for x in spec:groups[(x['domain'],x['split'],x['view'],x['trojan_view'])].append(x)
 checked=[];results=[];targets=[];sourcegraphs={};bindings={}
 for (dm,sp,nv,tv),ss in sorted(groups.items()):
  key=dm+'_'+sp;a=ctx[key];data={}
  for side,view in [('normal',nv),('trojan',tv)]:
   folder='orig' if dm=='orig' else 'trans';path=F/folder/(view+'.v');g=raw_network(path,lib);v=views[(key,view)];nn=[norm(n) for n in allnames[dm][v['old_start']:v['old_stop']]]+g['virtual_names'];assert set(nn)==set(g['cells']);index={n:i for i,n in enumerate(nn)}
   edge=a['edge_index'];mask=(edge[0]>=v['start'])&(edge[0]<v['stop']);ee=set(map(tuple,(edge[:,mask]-v['start']).T));raw={(index[u],index[t]) for u,tt in g['succ'].items() for t in tt};assert ee==raw,(view,len(ee),len(raw))
   mp=read(F/'mappings'/(view+'.json')) if dm=='trans' else None;reverse=collections.defaultdict(set)
   if mp:
    assert mp['src_view']==(ss[0]['source'] if side=='normal' else ss[0]['trojan_source']) and mp['rw_view']==view
    for parent,tt in mp['node_alignment'].items():
     for target in tt:reverse[norm(target)].add(norm(parent))
   data[side]=(g,v,nn,reverse);checked.append(dict(domain=dm,split=sp,view=view,nodes=len(nn),independent_edges_match=True,true_output_drivers=len(g['pocells'])));bindings[str(path.relative_to(R))]=sha(path)
   if dm=='trans':bindings[str((F/'mappings'/(view+'.json')).relative_to(R))]=sha(F/'mappings'/(view+'.json'))
  for x in ss:
   row={k:x[k] for k in ['domain','split','source','trojan_source','view','trojan_view','role','role_class']};ni=np.array([int(i) for i in x['normal_ids'].split('|')]);ti=np.array([int(i) for i in x['trojan_ids'].split('|')]);assert (a['y'][ni]==0).all() and (a['y'][ti]==1).all() and a['trusted'][ni].all() and a['trusted'][ti].all()
   for side,ids in [('normal',ni),('trojan',ti)]:
    g,v,nn,reverse=data[side];ns=[nn[int(i)-v['start']] for i in ids];src=x['source'] if side=='normal' else x['trojan_source'];srcfile=F/'orig'/(src+'.v')
    if src not in sourcegraphs:sourcegraphs[src]=raw_network(srcfile,lib);bindings[str(srcfile.relative_to(R))]=sha(srcfile)
    sg=sourcegraphs[src];parents=set().union(*(reverse[n] for n in ns)) if dm=='trans' else set(ns);assert parents
    # Same-role aliases may be valid lineage but never imply same function at every target.
    row[side+'_targets']=len(ns);row[side+'_live_targets']=sum(n in g['reachable'] for n in ns);row[side+'_source_parents']='|'.join(sorted(parents));row[side+'_source_live']=sum(n in sg['reachable'] for n in parents);row[side+'_mixed_source_parents']=len(parents)>1
    for i,n in zip(ids,ns):targets.append(dict(domain=dm,split=sp,source=src,view=x['view'] if side=='normal' else x['trojan_view'],role=x['role'],role_class=x['role_class'],side=side,row=int(i),instance=n,label=int(a['y'][i]),trusted=True,PO_driver_reachable=n in g['reachable'],current_extra_C_pool=(dm,int(i)) in pool if side=='normal' and sp=='train' else False))
   ttotal=row['trojan_targets'];tlive=row['trojan_live_targets'];ntotal=row['normal_targets'];nlive=row['normal_live_targets'];mixed=row['normal_mixed_source_parents'] or row['trojan_mixed_source_parents']
   status='anchor_only' if tlive==0 else 'mixed_activity_requires_boundary_set' if tlive<ttotal else 'connected_unproved'
   if mixed:status+=';source_alias_set'
   row.update(boundary_status=status,normal_activity='dead' if nlive==0 else 'live' if nlive==ntotal else 'mixed',functionally_verified=False,extra_weight_readiness='hold_dead_T_boundary' if tlive==0 else 'hold_partial_or_alias_boundary' if tlive<ttotal or mixed else 'structural_candidate_function_unproved',current_extra_C_nodes=sum((dm,int(i)) in pool for i in ni) if sp=='train' else 0)
   results.append(row)
  print(dm,sp,nv,'roles',len(ss),flush=True)
 dump('role_boundary_qualification.csv',results);dump('target_activity.csv',targets);dump('view_graph_checks.csv',checked)
 # A node cannot become eligible through another overlapping source role that is held.
 node_roles=collections.defaultdict(list)
 for x in targets:
  if x['side']=='normal':node_roles[(x['domain'],x['split'],x['view'],x['row'])].append(x)
 rolelookup={(x['domain'],x['split'],x['view'],x['role']):x for x in results};node_results=[]
 for key,aa in node_roles.items():
  rr=[rolelookup[(x['domain'],x['split'],x['view'],x['role'])] for x in aa];provisional=all(x['extra_weight_readiness']=='structural_candidate_function_unproved' for x in rr)
  node_results.append(dict(domain=key[0],split=key[1],view=key[2],row=key[3],source_roles='|'.join(sorted({x['role'] for x in aa})),role_classes='|'.join(sorted({x['role_class'] for x in aa})),in_current_C_pool=any(x['current_extra_C_pool'] for x in aa),proposed_status='structurally_supported_unproved' if provisional else 'hold_for_boundary_or_lineage',functional_certificate=False))
 dump('normal_candidate_qualification.csv',node_results)
 summary=[]
 for dm,sp in [('orig','train'),('orig','val'),('trans','train'),('trans','val')]:
  rr=[x for x in results if (x['domain'],x['split'])==(dm,sp)];nn=[x for x in node_results if (x['domain'],x['split'])==(dm,sp)];cp=[x for x in nn if x['in_current_C_pool']]
  summary.append(dict(domain=dm,split=sp,sources=len({x['source'] for x in rr}),role_records=len(rr),normal_unique=len(nn),T_anchor_only_roles=sum(x['trojan_live_targets']==0 for x in rr),T_mixed_roles=sum(0<x['trojan_live_targets']<x['trojan_targets'] for x in rr),T_all_live_roles=sum(x['trojan_live_targets']==x['trojan_targets'] for x in rr),source_alias_roles=sum(x['normal_mixed_source_parents'] or x['trojan_mixed_source_parents'] for x in rr),current_C_unique=len(cp),current_C_structural_support=sum(x['proposed_status']=='structurally_supported_unproved' for x in cp),current_C_hold=sum(x['proposed_status']!='structurally_supported_unproved' for x in cp),validation_structural_support=sum(x['proposed_status']=='structurally_supported_unproved' for x in nn),functional_verified=0))
 dump('qualification_summary.csv',summary);(O/'qualification.json').write_text(json.dumps(dict(training=0,SAT=0,model_forward=0,labels_modified=False,summary=summary,inputs=bindings,method='independent source/target pin graphs; true PO-output drivers; existing trusted labels; source aliases retained; structural support is not SAT/function certification'),ensure_ascii=False,indent=2),encoding='utf-8');print(summary)
if __name__=='__main__':main()
