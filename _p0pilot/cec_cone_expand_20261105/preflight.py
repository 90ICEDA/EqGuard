"""Data adapter and scalar replay of four rejected current-context candidates."""
from pathlib import Path
import sys,json,csv,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path.append(str(R/'_p0pilot/cec_cone_audit_20261105'));from audit import read,rows,SCHEMA,cone,sha
from pair_adapter import CECConePairs
def main():
 assert not (O/'ADAPTER_VERIFIED.json').exists();c=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');ledger=[]
 for split in ['train','val','test']:
  ds=CECConePairs(split);q=c['shared_inputs']['trans_'+split];d=R/q['folder'];x=np.load(d/'x39.npy',mmap_mode='r');physical=np.load(d/'physical.npy',mmap_mode='r');vm={v['view']:v for v in q['views']}
  for p in ds:
   for side in ['left','right']:
    z=p[side];v=vm[z['view']];ii=z['members'];assert len(ii)>0 and len(np.unique(ii))==len(ii);assert ((ii>=v['start'])&(ii<v['physical_stop'])).all() and physical[ii].all();assert int(z['root_row']) in ii and np.isfinite(x[ii]).all()
   ledger.append(dict(pair_id=p['pair_id'],split=split,source=p['source_object'],left_members=len(p['left']['members']),right_members=len(p['right']['members']),observed_bit_pins_retained=True))
 try:CECConePairs('all')
 except ValueError:pass
 else:raise AssertionError('No mixed split allowed')
 cc=read(O/'cones.json');byview={z['view']:z for z in cc};replayed=[]
 for q in rows(O/'rejected_candidates.csv'):
  if q['reason']!='native_PI_Q_enumeration_refutes_candidate':continue
  nets=q['observation'].removeprefix('legacy_candidate:').split('|');mm=[];con=[];roots=[]
  for view,net in zip([q['view_a'],q['view_b']],nets):
   m=next(iter(read(R/byview[view]['raw_path'])['modules'].values()));b=m['netnames'][net]['bits'][0];mm.append(m);roots.append(b);con.append(cone(m,b,{n:j for j,n in enumerate(m['cells'])},byview[view]['raw_sha']))
  tokens=sorted({tuple(l[:3]) for z in con for l in z['leaves']});assert len(tokens)<=12;found=None
  for pattern in range(1<<len(tokens)):
   env={t:(pattern>>j)&1 for j,t in enumerate(tokens)};outputs=[]
   for m,z,root in zip(mm,con,roots):
    val={};drivers={}
    for n,p in m['ports'].items():
     if p['direction']=='input':
      for j,b in enumerate(p['bits']):
       if ('PI',n,j) in env:val[b]=env['PI',n,j]
    for n,g in m['cells'].items():
     if ('Q',n,0) in env:
      for pin in ['Q','QN']:
       for b in g['connections'].get(pin,[]):val[b]=env['Q',n,0] ^ int(pin=='QN')
     if n in z['members']:drivers[g['connections'][SCHEMA[g['type']][0]][0]]=g
    def evaluate(b):
     if not isinstance(b,int):return int(b)
     if b in val:return val[b]
     g=drivers[b];typ=g['type'];v=[evaluate(g['connections'][p][0]) for p in SCHEMA[typ][1]]
     if typ in ['AND2X2','$and']:a=v[0]&v[1]
     elif typ in ['OR2X1','$or']:a=v[0]|v[1]
     elif typ in ['XOR2X1','$xor']:a=v[0]^v[1]
     elif typ in ['INVX0','$not']:a=1^v[0]
     else:a=v[1] if v[2] else v[0]
     val[b]=a;return a
    outputs.append(evaluate(root))
   if outputs[0]!=outputs[1]:found=dict(source=q['source'],view_a=q['view_a'],view_b=q['view_b'],net_a=nets[0],net_b=nets[1],semantic_inputs=[list(t) for t in tokens],input_values=[env[t] for t in tokens],output_a=outputs[0],output_b=outputs[1],scope='current independent named PI/physicalQ; not changing old historical status');break
  assert found;replayed.append(found)
 with (O/'adapter_preflight.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
 (O/'rejected_candidate_witnesses.json').write_text(json.dumps(replayed,ensure_ascii=False,indent=2),encoding='utf-8');(O/'ADAPTER_VERIFIED.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,primary_loaded=len(ledger),loaded_by_split=dict(collections.Counter(x['split'] for x in ledger)),split_mixing_rejected=True,bit_pin_preserved=True,current_v3_graph_members_verified=True,independent_scalar_refutations=len(replayed),adapter_sha=sha(O/'pair_adapter.py')),ensure_ascii=False,indent=2),encoding='utf-8');print('Loaded',len(ledger),'pairs; scalar replay refuted',len(replayed),flush=True)
if __name__=='__main__':main()
