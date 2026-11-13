from pathlib import Path
import json,csv,collections,sys
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31'
sys.path.insert(0,str(O.parent/'control_retention_20261104'));from audit import cells,norm,sha
def read(p):return p.read_text(encoding='utf-8-sig')
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
c=json.loads(read(R/'_p0pilot/round32_20261029/input_contract.json'));views={};splits={}
for sp in ['train','val','test']:
 for v in c['shared_inputs']['trans_'+sp]['views']:views[v['view']]=(sp,v)
 for v in c['shared_inputs']['orig_'+sp]['views']:splits[v['view']]=sp
pr=collections.defaultdict(list)
for p in (R/'generate_trans').glob('hosts*/*/provenance.json'):
 try:
  a=json.loads(read(p))
  if isinstance(a,list):
   for d in a:
    if d.get('view'):pr[d['view']].append((p,d))
 except (ValueError,OSError):pass
def record(src):
 sc,_=cells(F/'orig'/(src+'.v'));a=[(p,d) for p,d in pr[src] if d.get('new_gates') and all(norm(x) in sc for x in d['new_gates'])]
 assert a,src
 return sc,a[0][0],a[0][1]
fammap=dict(zip(['ctlmatch'+x for x in 'abcdef'],['injalpha','injbeta','injgamma','injdelta','injepsilon','injzeta']))
source=[];node=[];trans=[];bind={};tc_cache={}
for src,sp in splits.items():
 f=src.split('__')[1]
 if not(f.startswith('ctl') or f.startswith('a4ctl')):continue
 sc,pp,pd=record(src);prefix=pd['prefix'];base=f.split('_d1')[0];pairedfam=fammap.get(base)
 if base.startswith('a4ctl'):pairedfam=base.replace('a4ctldead','a4trojan').replace('a4ctlequiv','a4trojan')
 partner=src.replace(base,pairedfam,1) if pairedfam else ''
 valid=partner in splits
 ts=tp=td=None
 if valid:ts,tp,td=record(partner);assert splits[partner]==sp
 nmatch=0;nexact=0
 for g0 in pd['new_gates']:
  g=norm(g0);suffix=g[len(prefix):] if g.startswith(prefix) else None
  t=td['prefix']+suffix if valid and suffix is not None else ''
  match=t in ts and t in td['new_gates'] if valid else False
  typed=match and sc[g][0]==ts[t][0]
  def canonical(con,pref):return {k:('OBJ'+v[len(pref):] if v.startswith(pref) else v) for k,v in con.items()}
  exact=typed and canonical(sc[g][1],prefix)==canonical(ts[t][1],td['prefix'])
  nmatch+=int(typed);nexact+=int(exact)
  reason='same_role_same_type_same_normalized_connections' if exact else 'same_role_type_but_changed_connections' if typed else 'role_name_found_type_differs' if match else 'partner_source_excluded_or_absent' if pairedfam and not valid else 'no_preset_trojan_partner' if not pairedfam else 'terminal_or_role_has_no_counterpart'
  node.append(dict(split=sp,control_source=src,control_instance=g,control_type=sc[g][0],prefix=prefix,role_suffix=suffix or '',trojan_source=partner,trojan_instance=t if match else '',trojan_type=ts[t][0] if match else '',role_pair=typed,normalized_connections_equal=exact,status=reason,functional_sat_proof=False))
  if typed:
   for view,(vsp,v) in views.items():
    if not view.startswith(src+'__'):continue
    tv=view.replace(src,partner,1)
    if tv not in views:continue
    mp=F/'mappings'/(view+'.json');tm=F/'mappings'/(tv+'.json')
    for key in [view,tv]:
     if key not in tc_cache:
      cp=F/'mappings'/(key+'.json');md=json.loads(read(cp));cs,_=cells(F/'trans'/(key+'.v'));rev=collections.defaultdict(set)
      for orig,targets in md['node_alignment'].items():
       for q in targets:rev[norm(q)].add(norm(orig))
      tc_cache[key]=(md,cs,rev)
    ma,ca,ra=tc_cache[view];mb,cb,rb=tc_cache[tv]
    assert ma['src_view']==src and mb['src_view']==partner
    aa={norm(x) for x in ma['node_alignment'].get(g,[]) if norm(x) in ca};bb={norm(x) for x in mb['node_alignment'].get(t,[]) if norm(x) in cb}
    if g in ca:aa.add(g)
    if t in cb:bb.add(t)
    ashared=any(ra[x]-set(pd['new_gates']) for x in aa);bshared=any(rb[x]-set(td['new_gates']) for x in bb)
    trans.append(dict(split=sp,control_source=src,control_view=view,control_source_gate=g,trojan_source=partner,trojan_view=tv,trojan_source_gate=t,control_targets='|'.join(sorted(aa)),trojan_targets='|'.join(sorted(bb)),control_target_count=len(aa),trojan_target_count=len(bb),both_have_targets=bool(aa and bb),shared_with_host=bool(ashared or bshared),source_connections_equal=exact,target_pair_semantics='sets_of_role_descendants_not_cartesian_node_pairs',functional_sat_proof=False))
 source.append(dict(split=sp,control_source=src,added_nodes=len(pd['new_gates']),trojan_source=partner,partner_in_current_orig=valid,role_type_pairs=nmatch,normalized_connection_pairs=nexact,unpaired_nodes=len(pd['new_gates'])-nmatch))
 for p in [F/'orig'/(src+'.v'),pp]+([F/'orig'/(partner+'.v'),tp] if valid else []):bind[str(p.relative_to(R))]=sha(p)
dump('source_node_pairs.csv',node);dump('source_pair_summary.csv',source);dump('trans_role_descendant_pairs.csv',trans)
summary=[]
for sp in ['train','val','test']:
 a=[x for x in source if x['split']==sp];b=[x for x in trans if x['split']==sp and x['both_have_targets'] and not x['shared_with_host']]
 summary.append(dict(split=sp,normal_sources=len(a),added_source_nodes=sum(x['added_nodes'] for x in a),partner_sources=sum(x['partner_in_current_orig'] for x in a),role_type_source_pairs=sum(x['role_type_pairs'] for x in a),exact_normalized_source_pairs=sum(x['normalized_connection_pairs'] for x in a),trans_role_occurrences=len(b),trans_control_target_occurrences=sum(x['control_target_count'] for x in b),unique_trans_control_nodes=len({(x['control_view'],n) for x in b for n in x['control_targets'].split('|')})))
dump('source_pair_counts.csv',summary)
(O/'source_pair_audit.json').write_text(json.dumps(dict(summary=summary,input_hashes=bind,training=0,SAT=0,definition='source role/type and normalized connection correspondence, not functional equality or safety-role transfer'),ensure_ascii=False,indent=2),encoding='utf-8')
for x in summary:print(x)
