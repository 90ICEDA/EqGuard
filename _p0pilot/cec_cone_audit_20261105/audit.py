"""Read-only correspondence/cone audit. No solver, model, labels or training imports."""
from pathlib import Path
import json,csv,re,sys,collections,hashlib,importlib.util
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;T=R/'10.15/06_统一评测协议/N4_三向泛化/tables';F=R/'generate_trans/folds/hosts_bt31';H=R/'_p0pilot/round34_20261029'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ident(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def module(code,name):
 found=re.findall(r'\bmodule\s+'+re.escape(name)+r'\b.*?endmodule',code,re.S);assert len(found)==1;return found[0]
def bitref(b):return f'b{b}' if isinstance(b,int) else "1'b"+b
SCHEMA={'AND2X2':('Q',['IN1','IN2']),'OR2X1':('Q',['IN1','IN2']),'XOR2X1':('Q',['IN1','IN2']),'INVX0':('QN',['IN']),'MX2X1_RS':('Y',['A','B','S0']),'$and':('Y',['A','B']),'$or':('Y',['A','B']),'$xor':('Y',['A','B']),'$not':('Y',['A']),'$mux':('Y',['A','B','S'])}
def cone(m,root,cellmap,rawsha):
 pi={b:('PI',n,i,0) for n,p in m['ports'].items() if p['direction']=='input' for i,b in enumerate(p['bits']) if isinstance(b,int)};drivers=collections.defaultdict(list)
 for name,c in m['cells'].items():
  outs=['Q','QN'] if 'DFF' in c['type'].upper() else [SCHEMA[c['type']][0]] if c['type'] in SCHEMA else [p for p,d in c.get('port_directions',{}).items() if d=='output']
  for p in outs:
   for b in c['connections'].get(p,[]):
    if isinstance(b,int):drivers[b].append((name,p))
 members=set();leaves=set();constants=set();errors=set();visiting=set();seen=set()
 def visit(b):
  if not isinstance(b,int):
   if b in ['0','1']:constants.add(b)
   else:errors.add('undefined_constant:'+str(b))
   return
  if b in visiting:errors.add('combinational_cycle');return
  if b in seen:return
  if b in pi:leaves.add(pi[b]);seen.add(b);return
  ds=drivers.get(b,[])
  if len(ds)!=1:errors.add('driver_count:'+str(b)+':'+str(len(ds)));return
  name,p=ds[0];c=m['cells'][name]
  if 'DFF' in c['type'].upper():leaves.add(('Q',name,0,int(p=='QN')));seen.add(b);return
  if c['type'] not in SCHEMA:errors.add('unsupported:'+c['type']);return
  members.add(name);visiting.add(b)
  for q in SCHEMA[c['type']][1]:
   bs=c['connections'].get(q,[])
   if len(bs)!=1:errors.add('non_scalar:'+name+'.'+q)
   for v in bs:visit(v)
  visiting.remove(b);seen.add(b)
 visit(root);missing=sorted(members-set(cellmap));return dict(cone_id=ident([rawsha,root]),root_bit=root,members=sorted(members),graph_rows=sorted(cellmap[n] for n in members if n in cellmap),leaves=[list(v) for v in sorted(leaves)],constants=sorted(constants),errors=sorted(errors),unmapped_members=missing,nontrivial=bool(members),raw_sha=rawsha)
def main():
 O.mkdir(exist_ok=True);assert not (O/'AUDIT_COMPLETE.json').exists();inputs={};legacy=collections.Counter();legacylogs=set();legacygroups=collections.Counter();csvp=T/'node_pairs_sat_node.csv'
 with csvp.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);legacycolumns=reader.fieldnames
  for r in reader:
   legacy['rows']+=1;legacy[r.get('status','missing')]+=1
   if r.get('status')=='proved':legacy['same_instance_proved' if r.get('inst_a')==r.get('inst_b') else 'cross_instance_proved']+=1
   if r.get('log'):legacylogs.add(r['log'])
   legacygroups[r.get('host',''),r.get('inst_a',''),r.get('inst_b',''),r.get('recipe_a',''),r.get('recipe_b',''),r.get('status','')]+=1
 inputs[str(csvp.relative_to(R))]=sha(csvp);dump('legacy_sweep_inventory.csv',[dict(host=k[0],inst_a=k[1],inst_b=k[2],recipe_a=k[3],recipe_b=k[4],status=k[5],rows=n) for k,n in sorted(legacygroups.items())]);regions=rows(T/'region_pairs_v3.csv');dump('legacy_region_exclusions.csv',[dict(**r,label_free_region_definition=False,cone_input_output_contract=False,usable_for_new_training=False,exclusion='Trojan-prefix-defined, n_boundary_sigs=0, roles assigned by prefix, not cone CEC') for r in regions])
 # Load only pure native emitter, disabling its runner before any work.
 sys.path.insert(0,str(R/'_p0pilot/round10_20261025'));import native as N
 def forbidden(*a,**k):raise RuntimeError('Solver execution prohibited in read-only audit')
 N.P0.run_yosys=forbidden
 for modname in ['subprocess']:
  mod=__import__(modname);mod.run=forbidden;mod.Popen=forbidden;mod.check_output=forbidden
 feature=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');viewmap={v['view']:(key,v) for key,q in feature['shared_inputs'].items() if key.startswith('trans_') for v in q['views']};metadata={v['view']:v for v in rows(F/'views_meta.csv')};pairs=read(T/'sat_pair_round15/validated_pairs_cumulative_round15.json')['pairs'];coords=rows(T/'sat_pair_round15/signal_coordinates.csv');refs=rows(H/'proof_bindings.csv');frozen=read(H/'frozen_pairs.json');qrows=rows(T/'sat_pair_round10/queries_with_repairs.csv')+rows(T/'sat_pair_round11/queries_batch3.csv');qmap={(q['folder'],int(q['query_id'])):q for q in qrows};cmap={(x['relation_id'],int(x['slot']),x['side']):x for x in coords};pairmap={p['relation_id']:p for p in pairs};raws={};maps={};audit=[];conerecords={};accepted={};knownproofs={};names=[n.strip().lstrip('\\') for n in (F/'data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()];allcoordinatechecks=[]
 def bind(co):
  view=co['view'];rawfile=R/co['raw_snapshot']/'raw.json';source=F/'trans'/(view+'.v');assert sha(rawfile)==co['raw_sha'] and sha(source)==co['source_sha'];inputs[str(rawfile.relative_to(R))]=sha(rawfile);inputs[str(source.relative_to(R))]=sha(source)
  if view not in raws:
   raws[view]=next(iter(read(rawfile)['modules'].values()));key,v=viewmap[view];physical=names[v['old_start']:v['old_stop']];maps[view]={n:v['start']+j for j,n in enumerate(physical)};assert len(physical)==v['physical_stop']-v['start']
  m=raws[view];bits=m['netnames'].get(co['net'],m['ports'].get(co['net'],{}))['bits'];assert bits==[int(co['bit'])];cell=co['driver_cell'];pin=co['output_pin']
  if cell:
   assert m['cells'][cell]['connections'][pin]==bits;oldidx=int(float(co['node_index']));assert names[oldidx]==cell and cell in maps[view]
  return m
 for r in frozen:
  if r['cohort']=='privileged_mechanism':
   audit.append(dict(cohort=r['cohort'],relation_id=r['relation_id'],slot=r['slot'],split=r['split'],source_object='',unique_cone_pair='',proof_reused=False,source_comb_cells=0,partner_comb_cells=0,eligible=False,reason='manufacturing-role-selected; excluded from label-independent pool'));continue
  rid=r['relation_id'];slot=r['slot'];pair=pairmap[rid];left=cmap[rid,slot,'source'];right=cmap[rid,slot,'partner'];mods=[bind(left),bind(right)];ref=next(x for x in refs if x['relation_id']==rid and int(x['slot'])==slot);q=qmap[ref['folder'],int(ref['query_id'])];folder=R/ref['folder'];code=(folder/'model.v').read_text(encoding='utf-8');script=(folder/'run.ys').read_text(encoding='utf-8');log=(folder/'run.log').read_text(encoding='utf-8');assert sha(folder/'model.v')==q['model_sha']==ref['model_sha'];assert sha(folder/'run.log')==q['log_sha']==ref['log_sha'];assert hashlib.sha256(script.encode()).hexdigest()==q['script_sha']==ref['script_sha'];assert q['status']=='proved' and str(q['timeout']).lower()=='false' and 'ERROR:' not in log;commands=[x for x in script.splitlines() if x.startswith('sat ')];qid=int(ref['query_id']);assert commands[qid].startswith('sat '+q['args']+' -timeout ');blocks=re.split(r'^Q\d{4}\s*$',log,flags=re.M);block=blocks[qid+1];assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block
  match=re.fullmatch(r'-prove delta\[(\d+)\] 0',q['args'])
  if match:proofslot=int(match[1]);assert 'assign delta=a^b;' in module(code,'check')
  else:
   assert q['args']=='-prove mismatch 0';match=re.search(r'assign mismatch=a\[(\d+)\]\^b\[\1\];',module(code,'check'));assert match;proofslot=int(match[1])
  layouts=[];cc=[]
  for co,m,nets,modname in [(left,mods[0],pair['source_nets'],'left_design'),(right,mods[1],pair['partner_nets'],'right_design')]:
   generated,layout=N.emit(m,modname,nets);actual=module(code,modname);strip=lambda x:re.sub(r'assign sigs=\{.*?\};','assign sigs=BOUND;',x);assert strip(generated)==strip(actual);terms=re.search(r'assign sigs=\{(.*?)\};',actual).group(1).split(',');assert terms[4-proofslot]==bitref(int(co['bit']));layouts.append(layout);cc.append(cone(m,int(co['bit']),maps[co['view']],co['raw_sha']))
  assert layouts[0]['ports']==layouts[1]['ports'] and layouts[0]['states']==layouts[1]['states'];assert metadata[left['view']]['src_view']==metadata[right['view']]['src_view'];sourceobject=metadata[left['view']]['src_view'];key=ident([sourceobject,pair['context_id'],sorted(z['cone_id'] for z in cc)]);proofid=ident([sha(folder/'model.v'),q['args']]);knownproofs[proofid]=dict(folder=str(folder.relative_to(R)),query_id=qid,args=q['args'],model_sha=q['model_sha'],log_sha=q['log_sha'])
  reason=[]
  if any(z['errors'] for z in cc):reason.append('unresolved_or_invalid_logic_boundary')
  if any(not z['nontrivial'] for z in cc):reason.append('PI_or_physical_Q_anchor_not_two_nontrivial_cones')
  if any(z['unmapped_members'] for z in cc):reason.append('internal_logic_not_mapped_to_current_graph')
  ok=not reason
  for co,z in zip([left,right],cc):
   z=dict(z,view=co['view'],split=co['split'],source_object=sourceobject,output_pin=co['output_pin'],output_cell=co['driver_cell'],output_net=co['net']);conerecords[z['cone_id']]=z
  audit.append(dict(cohort=r['cohort'],relation_id=rid,slot=slot,split=r['split'],source_object=sourceobject,unique_cone_pair=key,proof_reused=True,source_comb_cells=len(cc[0]['members']),partner_comb_cells=len(cc[1]['members']),eligible=ok,reason=';'.join(reason)))
  if ok:
   record=accepted.setdefault(key,dict(pair_id=key,source_object=sourceobject,split=r['split'],context_id=pair['context_id'],left_cone=cc[0]['cone_id'],right_cone=cc[1]['cone_id'],proof_ids=[],references=[],functional_evidence_ready=True,detection_risk_consistency_allowed=False,current_training_loader_ready=False,labels_used_for_acceptance=False,boundary='maximal combinational cone at named PI/unrestricted physical Q;QN complemented',whole_design_equivalence_required=False,independent_cut4_CEC_claimed=False));record['proof_ids']=sorted(set(record['proof_ids']+[proofid]));record['references'].append(dict(relation_id=rid,slot=slot))
  for p in [folder/'model.v',folder/'run.ys',folder/'run.log']:inputs[str(p.relative_to(R))]=sha(p)
 # Cone equivalence components count logical objects without expanding all-pairs.
 parent={}
 def find(x):
  parent.setdefault(x,x)
  if parent[x]!=x:parent[x]=find(parent[x])
  return parent[x]
 for p in accepted.values():
  a,b=find(p['left_cone']),find(p['right_cone']);parent[max(a,b)]=min(a,b)
 components=collections.defaultdict(list)
 for p in accepted.values():components[p['source_object'],p['split'],find(p['left_cone'])].append(p['pair_id'])
 dump('candidate_reference_audit.csv',audit);dump('cone_components.csv',[dict(source_object=k[0],split=k[1],component_id=k[2],observed_unique_pairs=len(v)) for k,v in sorted(components.items())]);(O/'functional_cone_pairs.json').write_text(json.dumps(list(accepted.values()),ensure_ascii=False,indent=2),encoding='utf-8');(O/'cones.json').write_text(json.dumps(list(conerecords.values()),ensure_ascii=False,indent=2),encoding='utf-8');(O/'reused_queries.json').write_text(json.dumps(knownproofs,ensure_ascii=False,indent=2),encoding='utf-8')
 # Inventory all40 frozen candidates; do not promote29 unresolved relations.
 coverage=rows(T/'sat_pair_round15/pair_coverage_40_round15.csv');dump('relation40_status.csv',coverage)
 eligibility_signature=sorted(accepted);stripped=json.loads(json.dumps(frozen))
 for r in stripped:
  for side in ['source','partner']:
   r[side].pop('label',None);r[side].pop('trusted',None)
 # Only cohort+bit/coordinate/proof fields were consumed above. Publish explicit audit boundary.
 summary=dict(training=0,model_forward=0,new_SAT_queries=0,legacy_sweep=dict(legacy),legacy_sweep_logs=len(legacylogs),legacy_sweep_schema=legacycolumns,legacy_sweep_not_promoted='no per-row source/model/context hash binding; mixed anchors/old proof context; not imported as native-Q cone proof',legacy_region_rows=len(regions),legacy_region_all_Trojan_prefix=all(r['region'].startswith('Trojan') for r in regions),legacy_region_zero_boundary_sigs=all(float(r['n_boundary_sigs'])==0 for r in regions),legacy_region_label_independent_eligible=0,blind_relations=len(pairs),blind_reference_pairs=sum(r['cohort']!='privileged_mechanism' for r in audit),privileged_excluded=sum(r['cohort']=='privileged_mechanism' for r in audit),unique_reused_blind_queries=len(knownproofs),functional_cone_pairs=len(accepted),functional_pair_splits=dict(collections.Counter(p['split'] for p in accepted.values())),independent_source_objects=len({p['source_object'] for p in accepted.values()}),independent_source_objects_by_split={sp:len({p['source_object'] for p in accepted.values() if p['split']==sp}) for sp in ['train','val','test']},logical_cone_components=len(components),cone_components_by_split=dict(collections.Counter(k[1] for k in components)),excluded_reference_reasons=dict(collections.Counter(r['reason'] for r in audit if not r['eligible'])),current_detection_probability_or_whole_node_embedding_ready=0,current_functional_cone_loader_ready=0,label_free_scope='no node y/trusted/safety-role acceptance filter; r5/r6 view strata were manually selected, not claimed population-unbiased; r7 frozen hash selection; legacy prefix and privileged cohorts excluded',proof_scope='unconditional equality in explicit shared named PI/physical-Q context; maximal cones only, not arbitrary internal-cut equivalence or sequential/reset reachability',eligibility_pair_ids=eligibility_signature)
 for p in [H/'frozen_pairs.json',H/'proof_bindings.csv',T/'sat_pair_round15/signal_coordinates.csv',T/'sat_pair_round15/validated_pairs_cumulative_round15.json',T/'region_pairs_v3.csv',R/'_p0pilot/build_region_pairs_v3.py',R/'_p0pilot/round10_20261025/native.py',Path(__file__),R/'_p0pilot/control_boundary_v3_20261104/input_contract.json'] :inputs[str(p.relative_to(R))]=sha(p)
 summary['inputs']=inputs;(O/'AUDIT_COMPLETE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:summary[k] for k in ['legacy_sweep','legacy_region_rows','blind_reference_pairs','unique_reused_blind_queries','functional_cone_pairs','functional_pair_splits','independent_source_objects','logical_cone_components','excluded_reference_reasons']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
