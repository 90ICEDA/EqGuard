"""Reuse proved pairs and saved 128-pattern inputs; no new SAT or random trials."""
from pathlib import Path
import collections,csv,gzip,hashlib,importlib.util,json,sys
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
J=R/'_p0pilot/cec_joint_expand_20261105';I=R/'_p0pilot/cec_interface_minimal_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,x):
 if not x:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def main():
 assert not (O/'PANEL_COMPLETE.json').exists()
 # Bind the reused equivalence evidence to its previously published manifest.
 pub=read(J/'PUBLISHED.json');frozen={}
 for p,h in pub['files'].items():assert sha(R/p)==h,p;frozen[p]=h
 paths=[I/'boundary_maps_audit_only.json',I/'cone_pin_incidence.jsonl.gz',R/'_p0pilot/cec_pretrain_ready_20261105/witness_contexts.json',R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json']
 frozen.update({str(p.relative_to(R)):sha(p) for p in paths})
 contexts=read(paths[2])
 for k,v in read(paths[3]).items():
  if k in contexts:assert contexts[k]==v
  contexts[k]=v
 maps={x['context_key']:x for x in read(paths[0])}
 envs={k:{tuple(t['token']):int(t['mask_hex'],16) for t in v['input_masks']} for k,v in contexts.items()}
 cones={x['cone_id']:x for x in read(J/'final_cones.json')};pairs=read(J/'final_pairs.json');MASK=(1<<128)-1
 signatures={};depths={};mux={};replayed=0
 with gzip.open(paths[1],'rt',encoding='utf-8') as f:
  for line in f:
   p=json.loads(line);src,ctx=json.loads(p['context_lookup']);tokens=maps[p['context_lookup']]['tokens'];env={t['slot']:envs[ctx][t['kind'],t['audit_name'],t['bit']] for t in tokens}
   incoming=collections.defaultdict(list)
   for kind,s,phase,d,role in p['edge']:incoming[d].append((kind,s,phase,role))
   cache={};dep={}
   def ev(n):
    if n in cache:return cache[n]
    vv=[];ds=[]
    for kind,s,phase,role in incoming[n]:
     v=ev(s) if kind==0 else env[s] if kind==1 else MASK if s else 0
     vv.append((role,v^(MASK if phase else 0)));ds.append(dep[s] if kind==0 else 0)
    a=[v for _,v in vv];op=p['op'][n]
    if op=='AND':v=a[0]&a[1]
    elif op=='OR':v=a[0]|a[1]
    elif op=='XOR':v=a[0]^a[1]
    elif op=='NOT':v=MASK^a[0]
    else:
     assert op=='MUX';d=dict(vv);v=(d[4]&d[3])|((MASK^d[4])&d[2])
    dep[n]=1+max(ds);cache[n]=v;return v
   signatures[p['cone_id']]=ev(p['root']);depths[p['cone_id']]=dep[p['root']];mux[p['cone_id']]=p['op'].count('MUX');replayed+=1
 assert replayed==len(cones)
 # root three hops include the root itself plus three internal predecessors.
 # A boundary-to-root gate depth <=4 therefore fits the previous 3-hop inventory.
 selected=[];coverage=[];all_candidates=[]
 for tier,limit,shallow in [('shallow_small',16,True),('small_depth_control',16,False)]:
  buckets=collections.defaultdict(list)
  for p in pairs:
   a,b=[p[k] for k in ['left_cone','right_cone']]
   assert signatures[a]==signatures[b]
   assert p['functional_auxiliary_data_eligible']
   assert p['proof_ids'] or (p.get('enum',{}).get('equal') and p['enum']['method']=='complete_two_valued_enumeration')
   if max(len(cones[k]['members']) for k in [a,b])>limit:continue
   within=max(depths[a],depths[b])<=4
   if within!=shallow:continue
   key=(p['split'],p['source_object'],p['context_id'],cones[a]['view'],cones[b]['view'])
   buckets[key].append(p)
  bysource=collections.defaultdict(list)
  for key,rr in sorted(buckets.items()):
   # Merge equal observed signatures conservatively, never infer equivalence from them.
   funcs={}
   for p in sorted(rr,key=lambda x:x['pair_id']):funcs.setdefault(signatures[p['left_cone']],p)
   vv=list(funcs.items())
   for j,(am,a) in enumerate(vv):
    for bm,b in vv[j+1:]:
     cid=hashlib.sha256(json.dumps([tier,key,sorted([a['pair_id'],b['pair_id']])],sort_keys=True).encode()).hexdigest()
     cc=[a['left_cone'],a['right_cone'],b['left_cone'],b['right_cone']];bit=((am^bm)&-(am^bm)).bit_length()-1
     candidate=dict(certificate_id=cid,tier=tier,split=key[0],source=key[1],context_id=key[2],pair_a=a['pair_id'],pair_b=b['pair_id'],cones=cc,pattern=bit,expected_outputs=[(am>>bit)&1]*2+[(bm>>bit)&1]*2,max_gate_depth=max(depths[k] for k in cc),max_members=max(len(cones[k]['members']) for k in cc),has_mux=any(mux[k] for k in cc),proof_ids=sorted(set(a['proof_ids']+b['proof_ids'])),enumeration_proofs=[p['enum'] for p in [a,b] if not p['proof_ids']],signature_ids=[hex(am),hex(bm)],recipe_direction=key[3].split('__')[-1]+'|'+key[4].split('__')[-1])
     bysource[key[:2]].append(candidate)
  for (split,source),rr in sorted(bysource.items()):
   # Fixed hash order, maximum16/source/tier, endpoint/pair exposure <=2.
   counts=collections.Counter();chosen=[]
   for c in sorted(rr,key=lambda x:x['certificate_id']):
    if len(chosen)>=16:break
    if max(counts[k] for k in c['cones'])>=2:continue
    chosen.append(c);counts.update(c['cones'])
   selected+=chosen
   coverage.append(dict(tier=tier,split=split,source=source,candidate_blocks=len(rr),selected_blocks=len(chosen),selected_mux=sum(c['has_mux'] for c in chosen),distinct_pair_ids=len({c[k] for c in chosen for k in ['pair_a','pair_b']}),max_endpoint_exposure=max(counts.values(),default=0)))
   all_candidates.extend({k:v for k,v in c.items() if k not in ['signature_ids']} for c in rr)
 write('panel_certificates.json',selected);table('panel_source_coverage.csv',coverage)
 # Independent scalar replay against raw netlists, not the exported incidence evaluator.
 spec=importlib.util.spec_from_file_location('old_scalar_replay',R/'_p0pilot/cec_cert_expand_20261105/expand_certs.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 class Raw:
  def __init__(self):self.cache={}
  def raw(self,view):
   if view not in self.cache:
    c=next(x for x in cones.values() if x['view']==view);p=R/c['raw_path'];assert sha(p)==c['raw_sha'];frozen[str(p.relative_to(R))]=sha(p);self.cache[view]=next(iter(read(p)['modules'].values()))
   return self.cache[view]
 raw=Raw()
 for c in selected:
  out=v.verify(raw,cones,c,contexts[c['context_id']]);assert out==c['expected_outputs'] and out[0]==out[1] and out[2]==out[3] and out[0]!=out[2]
 # A short maximum dependency path implies 3-hop membership. The converse need
 # not hold: reconvergent shortcuts shorten graph distance but not logic depth.
 with (R/'_p0pilot/cec_fair_audit_20261105/boundary_cone_inventory.csv').open(encoding='utf-8-sig') as f:
  for x in csv.DictReader(f):assert depths[x['cone_id']]>4 or int(x['members_outside_3hop'])==0
 write('panel_cone_depths.json',{k:dict(gate_depth=depths[k],mux=mux[k]) for k in sorted(cones)})
 for p,h in frozen.items():assert sha(R/p)==h,p
 write('PANEL_COMPLETE.json',dict(selected=len(selected),coverage=coverage,exported_cones_replayed=replayed,scalar_replayed_certificates=len(selected),training_updates=0,SAT=0,new_input_patterns=0,test_reads=0,old_files_unchanged=True,frozen_files=frozen,scope='existing CEC equality plus saved-input scalar inequality;equal 128-bit signatures conservatively merged, not treated as proofs;train diagnostic is in-sample;val is same-host exploratory',selection='source/context/view-direction matched;<=16members;shallow gate-depth<=4 corresponds root3hop;complement small-depth>4;fixed hash,16blocks/source/tier,2exposures/endpoint within tier'))
 print(json.dumps(dict(selected=len(selected),coverage=coverage),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
