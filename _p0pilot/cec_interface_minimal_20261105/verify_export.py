"""Replay existing 68 witness assignments through numeric incidence only. No SAT/model."""
from pathlib import Path
import gzip,json,collections
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;C=R/'_p0pilot/cec_cert_expand_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
 maps=read(O/'boundary_maps_audit_only.json');maps={m['context_key']:m['tokens'] for m in maps};cert=read(C/'validation_negative_certificates.json');witness=read(C/'validation_witness_contexts.json');need={c for r in cert for c in r['cones']};cones={}
 with gzip.open(O/'cone_pin_incidence.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   g=json.loads(line)
   if g['cone_id'] in need:cones[g['cone_id']]=g
 checks=0
 for r in cert:
  env={tuple(t['token']):(int(t['mask_hex'],16)>>r['pattern'])&1 for t in witness[r['context_id']]['input_masks']};outputs=[]
  for cid in r['cones']:
   g=cones[cid];lookup=maps[g['context_lookup']];values={t['slot']:env[(t['kind'],t['audit_name'],t['bit'])] for t in lookup};inc=collections.defaultdict(list)
   for kind,src,phase,dst,role in g['edge']:inc[dst].append((kind,src,phase,role))
   cache={}
   def ev(i):
    if i in cache:return cache[i]
    vv=[]
    for kind,src,phase,role in inc[i]:
     a=ev(src) if kind==0 else values[src] if kind==1 else src;vv.append((role,a^phase))
    op=g['op'][i];v=[p[1] for p in vv]
    if op=='NOT':out=1-v[0]
    elif op=='AND':out=v[0]&v[1]
    elif op=='OR':out=v[0]|v[1]
    elif op=='XOR':out=v[0]^v[1]
    else:
     assert op=='MUX';byrole=dict(vv);out=byrole[3] if byrole[4] else byrole[2]
    cache[i]=out;return out
   outputs.append(ev(g['root']));checks+=1
  assert outputs==r['expected_outputs'] and outputs[0]==outputs[1] and outputs[2]==outputs[3] and outputs[0]!=outputs[2]
 result=dict(existing_certificates=68,root_evaluations=checks,pass_all=True,only_numeric_gate_op_incidence_and_boundary_slots_used=True,audit_name_used_only_to_transport_existing_witness_assignment=True,no_model_forward=True,new_SAT=0,training=0,meaning='P1+B1 incidence preserves existing scalar counterexamples;not new global equivalence proof')
 (O/'EXPORTED_WITNESS_REPLAY.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)
if __name__=='__main__':main()
