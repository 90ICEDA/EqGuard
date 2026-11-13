"""Independent proof-design/real-pin bindings and cached metric verification."""
from pathlib import Path
import csv,hashlib,itertools,json,math,re,sys
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];J=R/'_p0pilot/cec_joint_expand_20261105';P=R/'_p0pilot/cec_boundary_panel_expand_20261107';OLD=R/'_p0pilot/cec_dualcode_six_seed42_20261107'
sys.path.insert(0,str(P));from panel_loader import PanelLoader
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert read(O/'COMPLETE.json')['passed'];us=read(O/'SELECTED_UNITS.json');loader=PanelLoader();cones={c['cone_id']:c for c in read(J/'final_cones.json')};proof=read(J/'proofs.json')[rows('PROOF_BINDING_AUDIT.csv')[0]['proof_id']];text=(R/proof['folder']/'model.v').read_text(encoding='utf-8');blocks={n:b for n,b in re.findall(r'module\s+(\w+)\b(.*?)endmodule',text,re.S)};proofassign={name:dict(re.findall(r'assign\s+(b\d+)\s*=\s*([^;]+);',body)) for name,body in blocks.items()};bound=[];formal_inputs={}
 def clean(s):return re.sub(r'[\s()]','',s)
 def bit(b):return 'b'+str(b) if isinstance(b,int) else "1'b"+b
 for u in us:
  for cid in u['cones']:
   c=cones[cid];raw=next(iter(read(R/c['raw_path'])['modules'].values()));tokens=loader.tokens[loader.contexts[cid]];g=loader.graphs[cid];name='left_design' if c['view'].endswith('__ys_aig') else 'right_design';assign=proofassign[name];slot={(t['kind'],t['audit_name'],t['bit']):t['slot'] for t in tokens};leaf={};drivers={}
   for n,p in raw['ports'].items():
    if p['direction']=='input':
     for i,b in enumerate(p['bits']):leaf[b]=(slot['PI',n,i],0)
   for n,cell in raw['cells'].items():
    typ=cell['type'];con=cell['connections']
    if 'DFF' in typ.upper():
     for pin in ['Q','QN']:
      for i,b in enumerate(con.get(pin,[])):leaf[b]=(slot['Q',n,i],int(pin=='QN'))
    elif n in set(c['members']):
     # Separate type table from the local-interface schema under audit.
     schema={'$and':('Y','and',['A','B']),'$or':('Y','or',['A','B']),'$xor':('Y','xor',['A','B']),'$not':('Y','not',['A']),'$mux':('Y','mux',['A','B','S']),'AND2X2':('Q','and',['IN1','IN2']),'OR2X1':('Q','or',['IN1','IN2']),'XOR2X1':('Q','xor',['IN1','IN2']),'INVX0':('QN','not',['IN']),'MX2X1_RS':('Y','mux',['A','B','S0'])}
     out,op,pins=schema[typ];vv=[bit(con[p][0]) for p in pins];expr=('~'+vv[0] if op=='not' else vv[2]+'?'+vv[1]+':'+vv[0] if op=='mux' else vv[0]+{'and':'&','or':'|','xor':'^'}[op]+vv[1]);b=con[out][0];assert clean(assign['b'+str(b)])==clean(expr),(cid,n,assign.get('b'+str(b)),expr)
   used={s for s in g['slot'] if s>=0};count=0
   for b,(s,phase) in leaf.items():
    if s not in used:continue
    assert clean(assign['b'+str(b)])==('~' if phase else '')+f'env[{s}]',(cid,b,s,phase,assign.get('b'+str(b)))
    count+=1
   bound.append(dict(cone_id=cid,proof_design=name,all_local_gate_expressions_match_raw=True,used_leaf_bindings_checked=count,local_gates=len(c['members'])))
 table('PROOF_DESIGN_RAW_GATE_BINDING.csv',bound)
 # Exact six AIG tail decompositions,not inferred from128bit signatures.
 common=set.intersection(*[set(loader.graphs[c]['comb_names']) for u in us[:2] for c in u['cones'][1::2]]);nativecommon=set.intersection(*[set(loader.graphs[c]['comb_names']) for u in us[:2] for c in u['cones'][::2]]);tails=[]
 for u in us[:2]:
  for f in range(3):
   ng=loader.graphs[u['cones'][2*f]];g=loader.graphs[u['cones'][2*f+1]];inc={n:[] for n in range(len(g['op']))}
   for s,d,r,p in g['edge']:inc[d].append((s,r,p))
   def child(n,op):assert g['op'][n]==op and len(inc[n])==1 and inc[n][0][2]==0;return inc[n][0][0]
   a=child(g['root'],7);assert g['op'][a]==4;terms=[]
   for n,_,phase in inc[a]:
    assert phase==0;n=child(n,7);assert g['op'][n]==4;edges=inc[n];q=next(s for s,r,p in edges if g['op'][s]==1);control=next(s for s,r,p in edges if s!=q);assert all(p==0 for s,r,p in edges) and g['keys'][control][1] in common;terms.append((g['slot'][q],control))
   native={r:ng['slot'][s] for s,d,r,p in ng['edge'] if d==ng['root']};a_slot,b_slot=native[2],native[3];c0=next(c for q,c in terms if q==a_slot);c1=next(c for q,c in terms if q==b_slot);assert child(c1,7)==c0
   # T=c1=NOT(c0). With these cut values,tail equalsMUX(A,B,T) for all8assignments.
   for av,bv,tv in itertools.product([0,1],repeat=3):
    def ev(n):
     if n==c0:return 1-tv
     if n==c1:return tv
     if g['op'][n]==1:return {a_slot:av,b_slot:bv}[g['slot'][n]]
     vv=[ev(s)^p for s,r,p in inc[n]]
     return 1-vv[0] if g['op'][n]==7 else vv[0]&vv[1]
    assert ev(g['root'])==(bv if tv else av)
   tails.append(dict(unit_id=u['unit_id'],function=f,A_slot=a_slot,B_slot=b_slot,AIG_T=g['keys'][c1][1],AIG_notT=g['keys'][c0][1],exact_complement_relation=True,all8local_assignments_match_MUX=True,data_shortest_path_native=1,data_shortest_path_AIG=4,common_native_gates=len(nativecommon),common_AIG_gates=len(common)))
 table('EXACT_LOCAL_AIG_MUX_TAILS.csv',tails)
 # CPU ranking independently recalculated from the original frozen cache.
 center=rows('IMPLEMENTATION_CENTER_DIAGNOSTIC.csv');errors=rows('FUNCTION_QUERY_ERRORS.csv');checked=0
 for tag in range(9000,9012):
  for arm in ['INIT','Z0','Z1','R0','R1','P0','P1']:
   with np.load(OLD/f'train_{arm}_tag{tag}.npz') as z:ids=z['cone_ids'].tolist();x=z['root64'].astype(float)
   ix={c:i for i,c in enumerate(ids)}
   for u in us:
    v=x[[ix[c] for c in u['cones']]];vc=v.copy()
    for side in [0,1]:vc[side::2]-=v[side::2].mean(0)
    result=[]
    for mode,y in [('raw',v),('centered',vc)]:
     wins=[]
     for f in range(3):
      for side in [0,1]:
       ds=[math.sqrt(math.dist(y[2*f+side],y[2*j+1-side])**2/64+1e-12) for j in range(3)];ww=[float(ds[f]<ds[j])+.5*float(ds[f]==ds[j]) for j in range(3) if j!=f];wins+=ww
       if mode=='raw':
        row=next(r for r in errors if int(r['tag'])==tag and r['arm']==arm and r['unit_id']==u['unit_id'] and int(r['function'])==f and int(r['side'])==side);assert abs(float(row['pairwise_win'])-np.mean(ww))<1e-12 and abs(float(row['true_distance'])-ds[f])<1e-10
     result.append(float(np.mean(wins)))
    prior=next(r for r in center if int(r['tag'])==tag and r['arm']==arm and r['unit_id']==u['unit_id']);assert abs(float(prior['raw_win'])-result[0])<1e-12 and abs(float(prior['centered_win'])-result[1])<1e-12;checked+=1
 # All role-map gradient norms in the retained vector agree with log values.
 gradrows=rows('FROZEN_TRUE_CE_GRADIENTS.csv')
 import torch
 ck=torch.load(OLD/'INITIAL_STATE.pt',map_location='cpu',weights_only=False);slices={};off=0
 for n,p in ck['model'].items():slices[n]=slice(off,off+p.numel());off+=p.numel()
 with np.load(O/'gradient_vectors.npz') as z:
  for r in gradrows:
   v=z[f'{r["arm"]}_{r["tag"]}_{r["unit_id"]}'];assert len(v)==47360
   for n,s in slices.items():assert abs(float(np.linalg.norm(v[s]))-float(r[n]))<1e-6
 for p,h in read(O/'PROTECTED_INPUTS.json').items():assert sha(R/p)==h,p
 result=dict(passed=True,raw_proof_designs_bound_cones=18,exact_MUX_tail_mappings=6,synthetic_local_algebra_assignments_checked=48,new_real_input_patterns=0,ranking_centering_sets_recomputed=checked,function_query_checks=checked*6,gradient_vectors_checked=len(gradrows),common_native_selector_gates=len(nativecommon),common_AIG_gates=len(common),old_files_unchanged=True,training=0,SAT=0)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
