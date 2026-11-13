"""Boundary alignment only; six 50-step pretraining runs, no detector/SAT/test."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']: os.environ[k]='1'
from pathlib import Path
import sys,json,gzip,collections,math,time,gc,csv,traceback,hashlib
import numpy as np
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
PRE=R/'_p0pilot/cec_pretrain_ready_20261105'; I=R/'_p0pilot/cec_interface_minimal_20261105'
sys.path.insert(0,str(PRE)); import engine as E
torch=E.torch
from sklearn.metrics import roc_auc_score
read=E.read
def write(name,x): E.write(O/name,x)
def table(name,rows):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def code(kind,slot):
 h=hashlib.sha256(json.dumps(['boundary_vector_v1',kind,int(slot)],separators=(',',':')).encode()).digest()
 v=np.frombuffer(h,dtype='<u2').astype(np.float32)-32767.5
 return v/np.linalg.norm(v)

class Boundary:
 def __init__(self,contract,cones):
  maps=read(I/'boundary_maps_audit_only.json'); self.maps={m['context_key']:m for m in maps}
  vm={v['view']:(key,v) for key,q in contract['shared_inputs'].items() for v in q['views'] if key in ['trans_train','trans_val']}
  names=(R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()
  view_context={}; raws={}
  with gzip.open(I/'cone_pin_incidence.jsonl.gz','rt',encoding='utf-8') as f:
   for line in f:
    p=json.loads(line); c=cones[p['cone_id']]; view=c['view']; key=p['context_lookup']
    assert view not in view_context or view_context[view]==key
    view_context[view]=key; raws[view]=c['raw_path']
    assert p['graph_rows']==c['graph_rows']
  self.context_views={k:sorted(v for v,c in view_context.items() if c==k) for k in self.maps}
  self.records=[]; audit=[]; self.raw_files=[]
  schema={'AND2X2':['IN1','IN2'],'OR2X1':['IN1','IN2'],'XOR2X1':['IN1','IN2'],'INVX0':['IN'],'MX2X1_RS':['A','B','S0'],'$and':['A','B'],'$or':['A','B'],'$xor':['A','B'],'$not':['A'],'$mux':['A','B','S']}
  for view,key in sorted(view_context.items()):
   domain,v=vm[view]; path=R/raws[view]; self.raw_files.append(path)
   expected={c['raw_sha'] for c in cones.values() if c['view']==view}; assert expected=={E.sha(path)}
   m=next(iter(read(path)['modules'].values())); nn=[n.strip().lstrip('\\') for n in names[v['old_start']:v['old_stop']]]
   assert len(nn)==v['physical_stop']-v['start'] and len(nn)==len(set(nn))
   assert set(nn)<=set(m['cells']),('physical graph cell missing from raw',view)
   rowmap={n:v['start']+j for j,n in enumerate(nn)}
   aux=set(m['cells'])-set(nn)
   virtual_path=R/'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2/views'/view/'virtual_nodes.json'
   virtual=read(virtual_path);self.raw_files.append(virtual_path)
   assert len(aux)==len(virtual)==v['stop']-v['physical_stop']
   # Match auxiliary expressions by exact output and input bit semantics, never by order.
   def bit(net):
    if net in ['#0','#1']:return net[1:]
    assert net in m['netnames'],(view,'missing auxiliary net',net)
    bb=m['netnames'][net]['bits'];assert len(bb)==1;return bb[0]
   typmap={'$and':'V2_ASSIGN_AND','$or':'V2_ASSIGN_OR','$xor':'V2_ASSIGN_XOR','$not':'V2_ASSIGN_NOT','$mux':'V2_ASSIGN_MUX'}
   matched=set()
   for j,z in enumerate(virtual):
    candidates=[n for n in aux if m['cells'][n]['connections']['Y']==[bit(z['output'])] and typmap.get(m['cells'][n]['type'])==z['type']]
    assert len(candidates)==1,(view,'ambiguous auxiliary output',z)
    n=candidates[0];g=m['cells'][n];pins=['S','B','A'] if g['type']=='$mux' else schema[g['type']]
    assert [g['connections'][p][0] for p in pins]==[bit(t) for t in z['inputs']],(view,'auxiliary input mismatch',n)
    rowmap[n]=v['physical_stop']+j;matched.add(n)
   assert matched==aux
   for c in cones.values():
    if c['view']==view:
     # Historical graph_rows is numerically sorted; members uses name order.
     # Never zip these two lists to map incidence-local gates onto graph rows.
     assert sorted(c['graph_rows'])==sorted(rowmap[n] for n in c['members'])
     assert c['root_row']==rowmap[c['output_cell']]
   slots={(t['kind'],t['audit_name'],t['bit']):t['slot'] for t in self.maps[key]['tokens']}; leaf={}
   for n,p in m['ports'].items():
    if p['direction']=='input':
     for j,b in enumerate(p['bits']): leaf[b]=('PI',slots['PI',n,j],0)
   for n,g in m['cells'].items():
    if 'DFF' in g['type'].upper():
     for pin in ['Q','QN']:
      for j,b in enumerate(g['connections'].get(pin,[])): leaf[b]=('Q',slots['Q',n,j],int(pin=='QN'))
   rr=[]; const=collections.Counter(); dff=0; incidences=0
   for n,g in m['cells'].items():
    if 'DFF' in g['type'].upper(): dff+=1; continue
    assert g['type'] in schema,(view,n,g['type'])
    bb=[]; counts=np.zeros(4,np.float32)
    for pin in schema[g['type']]:
     for b in g['connections'][pin]:
      if b in leaf:
       kind,s,phase=leaf[b];counts[0 if kind=='PI' else 1]+=1;bb.append((kind,s,phase));incidences+=1
      elif b in ['0','1']: counts[2+int(b)]+=1;const[b]+=1
    if counts.sum(): rr.append((rowmap[n],counts,bb))
   self.records.append(dict(view=view,key=key,domain=domain,rank=self.context_views[key].index(view),rows=rr))
   audit.append(dict(view=view,domain=domain,physical_nodes=len(nn),auxiliary_nodes_verified=len(aux),boundary_consumers=len(rr),variable_pin_incidences=incidences,constant_pins=sum(const.values()),dff_zero_rows=dff,all_names_and_cone_rows_verified=True))
  self.counts={}
  for domain in ['trans_train','trans_val']:
   rows=sorted(r for z in self.records if z['domain']==domain for r,_,_ in z['rows'])
   assert len(rows)==len(set(rows)); self.counts[domain]=len(rows)
  table('row_mapping_audit.csv',audit)
  write('MAPPING_VERIFIED.json',dict(views=len(audit),contexts=len(self.maps),rows=self.counts,whole_view_direct_boundary=True,no_DFF_side_input=True,no_label_inputs=True))
 def features(self,domain,alignment,tag):
  assert alignment in ['shared','viewshuffle']
  # PRNG seeds depend on numeric update only; names/context IDs never enter vector contents.
  rng=np.random.default_rng(420000+tag); perm={}
  for key in sorted(self.maps):
   for kind in ['PI','Q']:
    slots=[t['slot'] for t in self.maps[key]['tokens'] if t['kind']==kind]
    perm[key,kind]=(slots,rng.permutation(len(slots)))
  allrows=[]; values=[]
  for rec in self.records:
   if rec['domain']!=domain: continue
   key=rec['key']; vectors={}
   for kind in ['PI','Q']:
    slots,p=perm[key,kind]; n=len(slots); shift=0 if alignment=='shared' or rec['rank']==0 or n<2 else 1+(rec['rank']-1)%(n-1)
    # Distinct codes within every view; same vocabulary, aliases and complement preserved.
    vocab=np.stack([code(kind,s) for s in slots]) if slots else np.zeros((0,16))
    for j,s in enumerate(slots): vectors[kind,s]=vocab[p[(j+shift)%n]]
    assert len(set(int(x) for x in p))==n
    if shift: assert all(p[(j+shift)%n]!=p[j] for j in range(n))
   for row,counts,bb in rec['rows']:
    x=np.zeros(20,np.float32);x[:4]=np.log1p(counts)
    for kind,s,phase in bb: x[4:]+=vectors[kind,s]*(-1 if phase else 1)
    x[4:]/=math.sqrt(max(1,float(counts.sum())));allrows.append(row);values.append(x)
  rows=np.array(allrows,np.int64); xx=np.stack(values)
  assert np.isfinite(xx).all() and len(rows)==self.counts[domain]
  return torch.tensor(rows,device='cuda'),torch.tensor(xx,device='cuda')

class Model(E.EncoderModel):
 def __init__(self):
  super().__init__();self.boundary_adapter=torch.nn.Linear(20,39,bias=False);torch.nn.init.zeros_(self.boundary_adapter.weight)
 def encode(self,x,e,side=None):
  if side is not None:
   rows,xx=side;delta=self.boundary_adapter(xx).to(x.dtype);x=x.index_add(0,rows,delta)
  return super().encode(x,e)

def initial():
 E.seed_all(42);m=Model().cuda();state=torch.load(E.H/'init_s42.pt',map_location='cuda',weights_only=True)
 missing,extra=m.load_state_dict(state,strict=False);assert missing==['boundary_adapter.weight'] and not extra
 for k,v in state.items():assert torch.equal(v,m.state_dict()[k])
 assert m.boundary_adapter.weight.count_nonzero()==0
 for n,p in m.named_parameters():p.requires_grad_(not n.startswith('classifier.'))
 E.seed_all(819);head=E.Projection().cuda();return m,head

def graph(domain):
 q=E.T.CONTRACT['shared_inputs'][domain];f=R/q['folder'];raw=np.load(f/'x39.npy',mmap_mode='r')
 for n in ['x39','edge_index']:
  path=f/(n+'.npy');assert E.sha(path)==E.T.CONTRACT['files'][str(path.relative_to(R))]
 x=torch.tensor(np.asarray(raw),device='cuda');x[:,25:]=((x[:,25:]-torch.tensor(E.T.NORM['mean'][25:],device='cuda'))/torch.tensor(E.T.NORM['std'][25:],device='cuda')).clamp(-10,10)
 return x,torch.tensor(np.asarray(np.load(f/'edge_index.npy',mmap_mode='r')),device='cuda')

def pool(h,cids,cones):
 roots=torch.tensor([cones[c]['root_row'] for c in cids],device='cuda');lengths=torch.tensor([len(cones[c]['graph_rows']) for c in cids],device='cuda')
 flat=torch.tensor([r for c in cids for r in cones[c]['graph_rows']],device='cuda');seg=torch.repeat_interleave(torch.arange(len(cids),device='cuda'),lengths)
 means=torch.zeros(len(cids),64,device='cuda').index_add_(0,seg,h[flat].float())/lengths[:,None]
 return torch.cat([h[roots],means.to(h.dtype)],1)

def preflight(x,e,b,cones,byid,schedule):
 m,head=initial();base,_=E.load_initial(42,'cuda');base.eval();m.eval();side=b.features('trans_train','shared',0)
 with torch.inference_mode():
  assert torch.equal(x,x.index_add(0,side[0],m.boundary_adapter(side[1])))
  ref=base.encode(x,e); now=m.encode(x,e,side);delta=float((ref-now).abs().max())
  # GPU scatter sums are not bitwise deterministic; input and weights are exact.
  assert torch.allclose(ref,now,atol=2e-4,rtol=2e-5),delta
  del ref,now
 del base; gc.collect();torch.cuda.empty_cache()
 rr=schedule[1];cids=sorted({p[k] for r in rr for p in [byid[r['pair_a']],byid[r['pair_b']]] for k in ['left_cone','right_cone']});ix={c:i for i,c in enumerate(cids)}
 E.seed_all(100043);m.train();head.train()
 with torch.autocast('cuda',dtype=torch.bfloat16):z=head(pool(m.encode(x,e,side),cids,cones))
 loss,parts=E.terms(z,rr,byid,ix,'R');loss.backward()
 adapter=float(m.boundary_adapter.weight.grad.norm());enc=sum(float(p.grad.norm()) for n,p in m.named_parameters() if p.grad is not None and not n.startswith('boundary_adapter.'))
 assert adapter>0 and enc>0 and np.isfinite([adapter,enc,float(loss.detach())]).all()
 # Checks distinguish identity, retain polarity, preserve commutative summary.
 assert not np.array_equal(code('PI',0),code('PI',1));assert np.allclose(code('Q',0)+(-code('Q',0)),0)
 write('PREFLIGHT.json',dict(passed=True,zero_adapter_output_max_delta=delta,adapter_grad_norm=adapter,encoder_grad_norm_sum=enc,loss=float(loss.detach()),optimizer_steps=0,backward_calls=1,model_parameters=sum(p.numel() for p in m.parameters()),peak_cuda_bytes=torch.cuda.max_memory_allocated(),rows_verified=True))
 del m,head,z,loss,parts,side;gc.collect();torch.cuda.empty_cache()

def train(alignment,arm,x,e,b,cones,byid,schedule,binding):
 name=alignment+'_'+arm;out=O/name;out.mkdir(exist_ok=True)
 if (out/'COMPLETE.json').exists():assert read(out/'COMPLETE.json')['binding']==binding;print('REUSE',name,flush=True);return
 m,head=initial();opt=torch.optim.Adam([p for p in m.parameters() if p.requires_grad]+list(head.parameters()),lr=.0002,weight_decay=.001);history=[];start=0
 if (out/'resume.pt').exists():
  saved=torch.load(out/'resume.pt',map_location='cuda',weights_only=False);assert saved['binding']==binding;m.load_state_dict(saved['model']);head.load_state_dict(saved['projection']);opt.load_state_dict(saved['optimizer']);start=saved['completed'];history=saved['history'];del saved
 torch.cuda.reset_peak_memory_stats()
 for u in range(start+1,51):
  t=time.perf_counter();rr=schedule[u];cids=sorted({p[k] for r in rr for p in [byid[r['pair_a']],byid[r['pair_b']]] for k in ['left_cone','right_cone']});ix={c:i for i,c in enumerate(cids)}
  side=b.features('trans_train',alignment,u);E.seed_all(100042+u);m.train();head.train();opt.zero_grad(set_to_none=True)
  with torch.autocast('cuda',dtype=torch.bfloat16):z=head(pool(m.encode(x,e,side),cids,cones))
  loss,parts=E.terms(z,rr,byid,ix,arm);assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_([p for p in m.parameters() if p.requires_grad]+list(head.parameters()),1.)
  assert torch.isfinite(norm);opt.step();row=dict(update=u,seconds=time.perf_counter()-t,grad_norm=float(norm),**{k:float(v.detach()) for k,v in parts.items()});history.append(row)
  del loss,z,parts,side
  assert all(bool(torch.isfinite(p).all()) for p in m.parameters())
  E.save(out/'resume.pt',dict(binding=binding,completed=u,model=m.state_dict(),projection=head.state_dict(),optimizer=opt.state_dict(),history=history));E.write(out/'history.json',history)
  if u==1:
   peak=torch.cuda.max_memory_allocated();total=torch.cuda.get_device_properties(0).total_memory
   assert peak/total<.95 and row['representation_std']>.01
   E.write(out/'FIRST_STEP.json',dict(passed=True,peak_bytes=peak,total_bytes=total,history=row))
  if u==1 or u%10==0:print(name,u,row,flush=True)
 E.write(out/'COMPLETE.json',dict(binding=binding,updates=50,selected='fixed_last50',checkpoint_sha=E.sha(out/'resume.pt'),peak_bytes=torch.cuda.max_memory_allocated(),adapter_weight_norm=float(m.boundary_adapter.weight.norm()),classifier_unchanged=True))
 del m,head,opt;gc.collect();torch.cuda.empty_cache()

def metrics(alignment,arm,remap,space,xx,ids,cones,certs):
 ix={c:i for i,c in enumerate(ids)};rr=[]
 def rms(a,b):return float(np.sqrt(np.mean((a-b)**2)))
 for c in certs:
  la,ra,lb,rb=[xx[ix[k]] for k in c['cones']];a=[rms(la,ra),rms(lb,rb)];w=[rms(la,rb),rms(lb,ra)];n=[rms(la,lb),rms(ra,rb)]
  recipe='|'.join(sorted(cones[c['cones'][k]]['view'].split('__')[-1] for k in [0,1]));mn=min(len(cones[k]['graph_rows']) for k in c['cones'])
  rr.append(dict(alignment=alignment,arm=arm,remap=remap,space=space,source=c['source'],recipe=recipe,size_bin='1-7' if mn<8 else '8-15' if mn<16 else '16-63' if mn<64 else '64+',certificate=c['certificate_id'],real0=a[0],real1=a[1],wrong0=w[0],wrong1=w[1],within0=n[0],within1=n[1],anchor_win=float(np.mean([float(t<f)+.5*float(t==f) for t,f in zip(a,w)]))))
 def stats(group):
  a=np.array([v for r in group for v in [r['real0'],r['real1']]]);w=np.array([v for r in group for v in [r['wrong0'],r['wrong1']]]);n=np.array([v for r in group for v in [r['within0'],r['within1']]])
  return dict(blocks=len(group),cross_auc=float(roc_auc_score([1]*len(a)+[0]*len(w),-np.r_[a,w])),same_view_comparison_auc=float(roc_auc_score([1]*len(a)+[0]*len(n),-np.r_[a,n])),anchor_win=float(np.mean([r['anchor_win'] for r in group])),real_rms=float(a.mean()),wrong_rms=float(w.mean()))
 base=dict(alignment=alignment,arm=arm,remap=remap,space=space);ss=[]
 for col in ['source','recipe','size_bin']:
  for v in sorted({r[col] for r in rr}):ss.append(dict(**base,stratum=col,value=v,**stats([r for r in rr if r[col]==v])))
 s=stats(rr);src=[r for r in ss if r['stratum']=='source'];center=xx-xx.mean(0);sv=np.linalg.svd(center,compute_uv=False);energy=sv**2;pr=energy/energy.sum();rank=float(np.exp(-np.sum(pr[pr>0]*np.log(pr[pr>0]))))
 return rr,dict(**base,**s,source_macro_auc=float(np.mean([r['cross_auc'] for r in src])),source_macro_anchor_win=float(np.mean([r['anchor_win'] for r in src])),mean_std=float(xx.std(0).mean()),effective_rank=rank),ss

def evaluate(b,cones):
 certs=read(R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json');assert len(certs)==68
 replay=read(I/'EXPORTED_WITNESS_REPLAY.json');assert replay['existing_certificates']==68 and replay['pass_all']
 ids=sorted({c for q in certs for c in q['cones']});assert all(cones[c]['split']=='val' for c in ids)
 trainids={r[k] for r in read(PRE/'function_inventory.json') for k in ['left_cone','right_cone'] if cones[r[k]]['split']=='train'};assert not set(ids)&trainids
 x,e=graph('trans_val');blocks=[];summary=[];strata=[]
 for alignment in ['shared','viewshuffle']:
  for arm in ['Z','R','P']:
   out=O/(alignment+'_'+arm);m,head=initial();saved=torch.load(out/'resume.pt',map_location='cuda',weights_only=False);assert saved['completed']==50;m.load_state_dict(saved['model']);head.load_state_dict(saved['projection']);del saved;m.eval();head.eval()
   before={k:v.clone() for k,v in m.state_dict().items()}
   for tag in [9000,9001]:
    side=b.features('trans_val',alignment,tag)
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
     h=m.encode(x,e,side);u=pool(h,ids,cones);z=head(u);uu=u.float().cpu().numpy().astype(np.float64);zz=z.float().cpu().numpy().astype(np.float64)
    np.savez_compressed(out/f'val_repr_remap{tag}.npz',cone_ids=np.array(ids),concat128=uu,projection32=zz)
    for space,xx in [('root64',uu[:,:64]),('concat128',uu),('projection32',zz)]:
     rr,s,ss=metrics(alignment,arm,tag,space,xx,ids,cones,certs);blocks+=rr;summary.append(s);strata+=ss
    del side,h,u,z
   assert all(torch.equal(before[k],v) for k,v in m.state_dict().items());del m,head,before;gc.collect();torch.cuda.empty_cache()
 table('evaluation_blocks.csv',blocks);table('evaluation_summary.csv',summary);table('evaluation_strata.csv',strata)
 contrasts=[]
 for remap in [9000,9001]:
  for space in ['root64','concat128','projection32']:
   for metric in ['cross_auc','source_macro_auc','anchor_win','source_macro_anchor_win']:
    get=lambda a,t:next(r[metric] for r in summary if r['alignment']==a and r['arm']==t and r['remap']==remap and r['space']==space)
    d={t:get('shared',t)-get('viewshuffle',t) for t in ['Z','R','P']}
    contrasts.append(dict(remap=remap,space=space,metric=metric,D_Z=d['Z'],D_R=d['R'],D_P=d['P'],R_minus_P=d['R']-d['P'],R_minus_Z=d['R']-d['Z']))
 table('alignment_contrasts.csv',contrasts)
 write('ANALYSIS_COMPLETE.json',dict(validation_blocks=68,unique_cones=len(ids),sources=len({c['source'] for c in certs}),remaps=[9000,9001],fixed50=True,no_test=True,no_new_SAT=True,eval_no_parameter_or_BN_update=True,training_eval_cones_disjoint=True))

def main():
 O.mkdir(exist_ok=True);assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 plan=read(I/'NEXT_SINGLE_FACTOR_CONTRACT.json');assert len(plan['conditions'])==6
 for n,h in plan['bindings'].items(): assert E.sha(PRE/n)==h
 E.set_inputs();cones={c['cone_id']:c for c in read(E.J/'final_cones.json')};b=Boundary(E.T.CONTRACT,cones)
 inventory=read(PRE/'function_inventory.json');byid={p['pair_id']:p for p in inventory};schedule=collections.defaultdict(list)
 for row in read(PRE/'schedule.json'):
  if row['mode']=='main' and row['seed']==42: schedule[row['update']].append(row)
 assert len(schedule)==50 and sum(map(len,schedule.values()))==250
 assert all(cones[byid[r[k]][side]]['split']=='train' for rr in schedule.values() for r in rr for k in ['pair_a','pair_b'] for side in ['left_cone','right_cone'])
 bindings={str(p.relative_to(R)):E.sha(p) for p in [Path(__file__),I/'NEXT_SINGLE_FACTOR_CONTRACT.json',I/'cone_pin_incidence.jsonl.gz',I/'boundary_maps_audit_only.json',PRE/'engine.py',PRE/'schedule.json',PRE/'function_inventory.json',PRE/'negative_certificates.json',E.H/'init_s42.pt',E.V/'input_contract.json',E.V/'normalization.npz',*b.raw_files]}
 contract=dict(frozen_files=bindings,seed=42,pretrain_updates=300,finetune_updates=0,new_SAT=0,test_reads=0,adapter_parameters=780,original_parameters=46620,protocol='6x50;shared-vs-within-kind-viewshuffle;original MSE;dropout.2;BN unchanged;fixed50;eval remaps9000/9001',zero_optimizer_preflight_backward=1)
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 x,e=graph('trans_train')
 if not (O/'PREFLIGHT.json').exists():preflight(x,e,b,cones,byid,schedule)
 assert read(O/'PREFLIGHT.json')['passed']
 for alignment in ['shared','viewshuffle']:
  for arm in ['Z','R','P']:
   train(alignment,arm,x,e,b,cones,byid,schedule,dict(contract_sha=E.sha(O/'EXECUTION_CONTRACT.json'),alignment=alignment,arm=arm))
 del x,e;gc.collect();torch.cuda.empty_cache()
 if not (O/'ANALYSIS_COMPLETE.json').exists():evaluate(b,cones)
 for p,h in bindings.items():assert E.sha(R/p)==h
 write('COMPLETE.json',dict(training_updates=300,preflight_backward_calls=1,finetune_updates=0,SAT=0,test_reads=0,old_inputs_unchanged=True,all_six_runs_complete=True))
 print('ALL_COMPLETE',flush=True)
if __name__=='__main__':
 try: main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%Y%m%d_%H%M%S")}.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
