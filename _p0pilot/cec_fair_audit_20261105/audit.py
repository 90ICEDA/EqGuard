"""CPU-only audit: cached representations, certified cross-implementation swaps, input fixtures.
No model forward, optimizer, SAT, Yosys or edits to historical experiment artifacts.
"""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,importlib.util,json
import numpy as np
from sklearn.metrics import roc_auc_score
import torch
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
J=R/'_p0pilot/cec_joint_expand_20261105';OLD=R/'_p0pilot/cec_mechanism_seed42_20261105';CERT=R/'_p0pilot/cec_cert_expand_20261105';inputs={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def track(p):p=Path(p);inputs[str(p.relative_to(R))]=sha(p);return p
def read(p):return json.loads(track(p).read_text(encoding='utf-8-sig'))
def write(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(name,rows):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def module(path,name):
 track(path);s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def rms(a,b):return float(np.sqrt(np.mean((a-b)**2)))

def evaluate():
 pairs=read(J/'final_pairs.json');byid={p['pair_id']:p for p in pairs};cones={c['cone_id']:c for c in read(J/'final_cones.json')};certs=read(CERT/'validation_negative_certificates.json');plan=read(OLD/'PREPARED.json');ids=plan['val_cones'];ix={c:i for i,c in enumerate(ids)}
 # Independently replay existing certificates. Import disables Yosys; main is NOT called.
 replay=module(CERT/'expand_certs.py','replay_existing_only');store=replay.Store();ctx=read(CERT/'validation_witness_contexts.json')
 for c in certs:
  out=replay.verify(store,cones,c,ctx[c['context_id']]);assert out==c['expected_outputs'] and out[0]==out[1] and out[2]==out[3] and out[0]!=out[2]
  pa,pb=[byid[c[k]] for k in ['pair_a','pair_b']];assert pa['source_object']==pb['source_object']==c['source'] and pa['context_id']==pb['context_id']==c['context_id']
  assert cones[pa['left_cone']]['view']==cones[pb['left_cone']]['view'] and cones[pa['right_cone']]['view']==cones[pb['right_cone']]['view']
 del store
 records=[];summary=[];strata=[]
 for family,folder in [('mse','cec_pretrain_ready_20261105'),('dropout0','cec_dropout_seed42_20261105'),('rank','cec_rank_seed42_20261105')]:
  for arm in ['Z','R','P']:
   if family=='mse':hp=dict(np.load(track(OLD/f'head_{arm}.npz')))
   else:
    saved=torch.load(track(R/f'_p0pilot/{folder}/runs/main/seed42/{arm}/pretrain/resume.pt'),map_location='cpu',weights_only=False);assert saved['completed']==50;hp={k:v.numpy() for k,v in saved['projection'].items()};del saved
   for stage in ['pre','best']:
    file=OLD/f'embeddings/{arm}_{stage}/val_eval_running.npy' if family=='mse' else R/f'_p0pilot/{folder}/{arm}_{stage}_val_concat128.npy'
    u=np.load(track(file)).astype(np.float64);assert u.shape==(len(ids),128) and np.isfinite(u).all()
    z=np.maximum(u@hp['0.weight'].T+hp['0.bias'],0)@hp['2.weight'].T+hp['2.bias']
    for space,x in [('root64',u[:,:64]),('concat128',u),('projection32',z)]:
     rr=[]
     for c in certs:
      la,ra,lb,rb=[x[ix[k]] for k in c['cones']];real=[rms(la,ra),rms(lb,rb)];wrong=[rms(la,rb),rms(lb,ra)];within=[rms(la,lb),rms(ra,rb)]
      rec='|'.join(sorted(cones[c['cones'][k]]['view'].split('__')[-1] for k in [0,1]));sizes=[len(cones[k]['graph_rows']) for k in c['cones']];mn=min(sizes);bin='1-7' if mn<8 else '8-15' if mn<16 else '16-63' if mn<64 else '64+'
      # Compare each left anchor's real and wrong right endpoints. Ties get half credit.
      wins=[float(a<b)+.5*float(a==b) for a,b in zip(real,wrong)];gap=np.mean(wrong)-np.mean(real)
      r=dict(family=family,arm=arm,stage=stage,space=space,source=c['source'],role='injection' if '__inj' in c['source'] else 'control',recipe=rec,size_bin=bin,certificate_id=c['certificate_id'],pair_a=c['pair_a'],pair_b=c['pair_b'],min_nodes=mn,max_nodes=max(sizes),real0=real[0],real1=real[1],wrong0=wrong[0],wrong1=wrong[1],within0=within[0],within1=within[1],gap=float(gap),relative_gap=float(gap/max(.5*(np.mean(wrong)+np.mean(real)),1e-12)),anchor_win=float(np.mean(wins)),block_win=float(np.mean(real)<np.mean(wrong))+.5*float(np.mean(real)==np.mean(wrong)))
      rr.append(r)
     records+=rr
     def stats(group):
      t=np.array([v for r in group for v in [r['real0'],r['real1']]]);f=np.array([v for r in group for v in [r['wrong0'],r['wrong1']]]);n=np.array([v for r in group for v in [r['within0'],r['within1']]])
      return dict(blocks=len(group),unique_pairs=len({r[k] for r in group for k in ['pair_a','pair_b']}),cross_auc=float(roc_auc_score([1]*len(t)+[0]*len(f),-np.r_[t,f])),within_comparison_auc=float(roc_auc_score([1]*len(t)+[0]*len(n),-np.r_[t,n])),real_rms=float(t.mean()),wrong_cross_rms=float(f.mean()),within_rms=float(n.mean()),anchor_win=float(np.mean([r['anchor_win'] for r in group])),block_win=float(np.mean([r['block_win'] for r in group])),relative_gap=float(np.mean([r['relative_gap'] for r in group])))
     base=dict(family=family,arm=arm,stage=stage,space=space);srcstats=[]
     for source in sorted({r['source'] for r in rr}):
      ss=[r for r in rr if r['source']==source];v=stats(ss);srcstats.append(v);strata.append(dict(**base,stratum='source',value=source,**v))
     s=stats(rr);summary.append(dict(**base,**s,source_macro_cross_auc=float(np.mean([r['cross_auc'] for r in srcstats])),source_macro_anchor_win=float(np.mean([r['anchor_win'] for r in srcstats]))))
     for col in ['recipe','size_bin']:
      for value in sorted({r[col] for r in rr}):strata.append(dict(**base,stratum=col,value=value,**stats([r for r in rr if r[col]==value])))
    print('EVALUATED',family,arm,stage,flush=True)
 table('fair_cross_blocks.csv',records);table('fair_cross_summary.csv',summary);table('fair_cross_strata.csv',strata)
 write('CERTIFICATES_VERIFIED.json',dict(blocks=68,independent_scalar_replay_pass=True,matching='same source/context/left view/right view;true and wrong edges share endpoints within each block',selection='existing fixed-hash posthoc validation certificates, no new samples',limits=['5 sources/1 host;small source blocks 2/1/1','no independence claim across repeated cones','size strata use minimum of four cones;not exact gate/size joint matching','projection32 at best is a frozen pretraining-head probe, not detector input']))
 return pairs,cones

def information(pairs,cones):
 v=module(R/'_p0pilot/control_boundary_v3_20261104/feature_encoding_v3_po.py','audit_v3_parser');lib={'BUFX':dict(input=['A'],output=['Y'],scalar=True),'MX2X1_RS':dict(input=['A','B','S0'],output=['Y'],scalar=True),'INVX0':dict(input=['IN'],output=['QN'],scalar=True)};order=[s[5:] for s in v.COLS[:25]];mapping={'BUFX':'BUFX','MX2X1_RS':'MUXX','INVX0':'INVX'}
 fixtures=O/'fixtures';fixtures.mkdir(exist_ok=True)
 text='module top(a,b,s,y);\ninput a,b,s;\noutput y;\nwire na,nb,ns;\nBUFX ua (.A(a),.Y(na));\nBUFX ub (.A(b),.Y(nb));\nBUFX us (.A(s),.Y(ns));\nMX2X1_RS m (.A(na),.B(nb),.S0(ns),.Y(y));\nendmodule\n'
 examples=[]
 for kind,left,right,names,fn,gn in [
  ('mux_select_data_pin_swap',text,text.replace('.A(na),.B(nb),.S0(ns)','.A(ns),.B(nb),.S0(na)'),['ua','ub','us','m'],lambda a,b,s:b if s else a,lambda a,b,s:b if a else s),
  ('boundary_PI_identity_swap','module top(a,b,s,y);\ninput a,b,s;\noutput y;\nINVX0 m (.IN(a),.QN(y));\nendmodule\n','module top(a,b,s,y);\ninput a,b,s;\noutput y;\nINVX0 m (.IN(b),.QN(y));\nendmodule\n',['m'],lambda a,b,s:1-a,lambda a,b,s:1-b)]:
  graphs=[];xs=[]
  for tag,body in [('left',left),('right',right)]:
   path=fixtures/f'{kind}_{tag}.v';path.write_text(body,encoding='utf-8');g=v.parse(path,names,lib);graphs.append(g);xs.append(v.features(g,mapping,order));np.save(fixtures/f'{kind}_{tag}_x39.npy',xs[-1])
  same_x=np.array_equal(*xs);same_e=np.array_equal(graphs[0]['edge_index'],graphs[1]['edge_index']);same_r=np.array_equal(graphs[0]['edge_roles'],graphs[1]['edge_roles']);diff=[dict(a=a,b=b,s=s,left=fn(a,b,s),right=gn(a,b,s)) for a in [0,1] for b in [0,1] for s in [0,1] if fn(a,b,s)!=gn(a,b,s)]
  assert same_x and same_e and same_r and diff;examples.append(dict(case=kind,identical_x39=same_x,identical_edge_index=same_e,identical_edge_roles=same_r,different_patterns=len(diff),total_patterns=8,witnesses=diff,scope='synthetic counterexample using actual v3 producer;not measured prevalence in dataset;no SAT'))
 raw={};rawcount=collections.Counter();rows=[]
 for c in cones.values():
  path=c['raw_path']
  if path not in raw:
   q=read(R/path);assert inputs[path]==c['raw_sha'];m=next(iter(q['modules'].values()));raw[path]=m
  m=raw[path];mux=[n for n in c['members'] if m['cells'][n]['type'] in ['MX2X1_RS','$mux']];leaf=collections.Counter(t[0] for t in c['leaves'])
  # Internal combinational distance from root: counts ancestors omitted from a 3-layer root receptive field.
  members=set(c['members']);drivers={}
  for n in c['members']:
   g=m['cells'][n];out='Y' if g['type'] in ['$and','$or','$xor','$not','$mux','MX2X1_RS'] else 'QN' if g['type']=='INVX0' else 'Q'
   for bit in g['connections'][out]:drivers[bit]=n
  seen={c['output_cell']};front=set(seen)
  for _ in range(3):
   nxt=set()
   for n in front:
    g=m['cells'][n];out='Y' if g['type'] in ['$and','$or','$xor','$not','$mux','MX2X1_RS'] else 'QN' if g['type']=='INVX0' else 'Q'
    for pin,bits in g['connections'].items():
     if pin==out:continue
     nxt.update(drivers[b] for b in bits if b in drivers)
   front=nxt-seen;seen|=nxt
  rows.append(dict(split=c['split'],cone_id=c['cone_id'],view=c['view'],members=len(members),mux_cells=len(mux),PI_leaves=leaf['PI'],Q_leaves=leaf['Q'],constants=len(c['constants']),members_outside_3hop=len(members-seen),root_3hop_member_fraction=len(members&seen)/max(len(members),1)))
 table('boundary_cone_inventory.csv',rows)
 totals=[]
 for split in ['train','val']:
  rr=[x for x in rows if x['split']==split];totals.append(dict(split=split,unique_cones=len(rr),cones_with_mux=sum(r['mux_cells']>0 for r in rr),cones_with_PI=sum(r['PI_leaves']>0 for r in rr),cones_with_Q=sum(r['Q_leaves']>0 for r in rr),cones_with_constants=sum(r['constants']>0 for r in rr),cones_with_members_outside_root_3hop=sum(r['members_outside_3hop']>0 for r in rr),median_root_3hop_member_fraction=float(np.median([r['root_3hop_member_fraction'] for r in rr]))))
 write('INPUT_INFORMATION_AUDIT.json',dict(existing_information=['25 gate classes include registers','touches_PI/touches_PO','directed PI/PO distances','register-side distances/exact2 context','directed cell-to-cell connectivity'],missing_or_unused=['combinational edge pin identity A/B/S0;all role1','PI input signal identity/index per consumer pin','physical Q identity and Q/QN polarity in model input','cone boundary leaf tokens/constants/context known to proof but not passed to model/projection','edge_roles metadata retained but loader only passes x39 and edge_index'],fixtures=examples,cone_summary=totals,scope='3-hop statistic only internal raw combinational ancestors of root, not total GNN receptive field;mean pooling still includes every cone member;does not prove all large cones unlearnable'))

def invalidate():
 P=R/'_p0pilot/cec_nodepair_pilot_20261105';original={str(p.relative_to(R)):sha(p) for p in P.rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.name!='INVALIDATED_20261105.json'}
 status=dict(status='INVALID_FOR_EQUIVALENT_PRETRAINING_AND_HELDOUT_CLAIMS',preserve_original_artifacts=True,reasons=['1000 proved pair_a and 1000 differ pair_b both passed as real equivalence edges to unchanged engine','negative and swapped edges lack original common-context witness contract','heldout chosen by positional slicing rather than actual training membership'],verified_previous_audit=dict(proved_holdout_pairs=3000,proved_training_overlap=726,differ_holdout_pairs=3000,differ_training_overlap=486),scope='does not invalidate original CEC pool, MSE/dropout/ranking/centering runs',original_files_sha256=original)
 write('NODEPAIR_INVALIDATION.json',status)
 marker=P/'INVALIDATED_20261105.json'
 if not marker.exists():marker.write_text(json.dumps(dict(status=status['status'],details='_p0pilot/cec_fair_audit_20261105/NODEPAIR_INVALIDATION.json',preserve_existing_files=True),ensure_ascii=False,indent=2),encoding='utf-8')
 return original

def main():
 O.mkdir(exist_ok=True);assert not (O/'COMPLETE.json').exists(),'Completed audit exists; reuse outputs'
 original=invalidate();pairs,cones=evaluate();information(pairs,cones)
 assert all(sha(R/p)==h for p,h in original.items())
 assert all(sha(R/p)==h for p,h in inputs.items())
 write('COMPLETE.json',dict(training_updates=0,optimizer_steps=0,model_forwards=0,new_SAT_queries=0,new_Yosys=0,cached_families=['mse','dropout0','rank'],seed=42,original_pilot_files_unchanged=True,inputs_unchanged=True,input_sha256=inputs,certificates=68))
 print('AUDIT_COMPLETE',flush=True)
if __name__=='__main__':main()
