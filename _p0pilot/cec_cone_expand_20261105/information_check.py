"""Find two explicit outputs for large cones; sampling is not an equivalence proof."""
from pathlib import Path
import sys,json,csv
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'));from audit import read,SCHEMA
def main():
 assert not (O/'INFORMATION_CHECK.json').exists();pairs=read(O/'pairs.json');cones={z['cone_id']:z for z in read(O/'cones.json')};out=[];witness=[];rng=np.random.default_rng(20261105)
 for p in pairs:
  if not p['proof_ids']:continue
  if p['enum']['method']=='complete_two_valued_enumeration':assert p['enum']['nonconstant'];out.append(dict(pair_id=p['pair_id'],split=p['split'],method='complete_enumeration',nonconstant_verified=True,patterns=p['enum']['patterns']));continue
  cc=[cones[p['left_cone']],cones[p['right_cone']]];tokens=sorted({tuple(l[:3]) for z in cc for l in z['leaves']});w=len(tokens);eye=np.eye(w,dtype=bool);matrix=np.r_[np.zeros((1,w),bool),np.ones((1,w),bool),eye,~eye,rng.integers(0,2,size=(128,w),dtype=np.uint8).astype(bool)];env={t:matrix[:,j] for j,t in enumerate(tokens)};outputs=[]
  for z in cc:
   m=next(iter(read(R/z['raw_path'])['modules'].values()));values={};drivers={}
   for name,port in m['ports'].items():
    if port['direction']=='input':
     for j,b in enumerate(port['bits']):
      if ('PI',name,j) in env:values[b]=env['PI',name,j]
   for name,g in m['cells'].items():
    if ('Q',name,0) in env:
     for pin in ['Q','QN']:
      for b in g['connections'].get(pin,[]):values[b]=~env['Q',name,0] if pin=='QN' else env['Q',name,0]
    if name in z['members']:drivers[g['connections'][SCHEMA[g['type']][0]][0]]=g
   def ev(b):
    if not isinstance(b,int):return np.full(len(matrix),b=='1',bool)
    if b in values:return values[b]
    g=drivers[b];v=[ev(g['connections'][n][0]) for n in SCHEMA[g['type']][1]];t=g['type']
    result=v[0]&v[1] if t in ['AND2X2','$and'] else v[0]|v[1] if t in ['OR2X1','$or'] else v[0]^v[1] if t in ['XOR2X1','$xor'] else ~v[0] if t in ['INVX0','$not'] else np.where(v[2],v[1],v[0]);values[b]=result;return result
   outputs.append(ev(z['root_bit']))
  assert np.array_equal(*outputs);nonconstant=bool(outputs[0].any() and (~outputs[0]).any());out.append(dict(pair_id=p['pair_id'],split=p['split'],method='two_witness_existence_not_equivalence_proof',nonconstant_verified=nonconstant,patterns=len(matrix)))
  if nonconstant:witness.append(dict(pair_id=p['pair_id'],semantic_inputs=[list(t) for t in tokens],input_for0=matrix[np.flatnonzero(~outputs[0])[0]].astype(int).tolist(),input_for1=matrix[np.flatnonzero(outputs[0])[0]].astype(int).tolist(),both_sides_output0=0,both_sides_output1=1,equivalence_evidence='original source-bound CEC proof; these witnesses only prove nonconstancy'))
 with (O/'functional_information.csv').open('w',encoding='utf-8-sig',newline='') as f:ww=csv.DictWriter(f,fieldnames=list(out[0]));ww.writeheader();ww.writerows(out)
 (O/'large_nonconstant_witnesses.json').write_text(json.dumps(witness,ensure_ascii=False,indent=2),encoding='utf-8');report=dict(training=0,model_forward=0,SAT=0,primary_pairs=len(out),nonconstant_verified=sum(r['nonconstant_verified'] for r in out),nonconstancy_unresolved=sum(not r['nonconstant_verified'] for r in out),large_explicit_two_witness_pairs=len(witness),sampling_not_used_as_equivalence_proof=True);(O/'INFORMATION_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report,flush=True)
if __name__=='__main__':main()
