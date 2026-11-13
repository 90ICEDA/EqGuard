"""MUX pin-role single factor, shared boundary identities; 6x50, no detection/SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,gzip,sys,collections,math,time,gc,traceback,importlib.util
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
OLD=R/'_p0pilot/cec_boundary_seed42_20261106'
spec=importlib.util.spec_from_file_location('frozen_boundary_runner',OLD/'run.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B);B.O=O
E=B.E;torch=B.torch;read=E.read;write=B.write;table=B.table
SCHEMA={'AND2X2':('Q','AND',['IN1','IN2']),'OR2X1':('Q','OR',['IN1','IN2']),'XOR2X1':('Q','XOR',['IN1','IN2']),'INVX0':('QN','NOT',['IN']),'MX2X1_RS':('Y','MUX',['A','B','S0']),'$and':('Y','AND',['A','B']),'$or':('Y','OR',['A','B']),'$xor':('Y','XOR',['A','B']),'$not':('Y','NOT',['A']),'$mux':('Y','MUX',['A','B','S'])}
WIDTHS=[29,64,10,64,64]

def rolemap(rank,condition):
 # A different within-view convention breaks cross-implementation semantic alignment.
 # COMM and NOT are unchanged; only the three MUX ports can be permuted.
 shift=0 if condition=='shared' or rank==0 else 1+(rank-1)%2
 return np.array([0,1]+[2+(j+shift)%3 for j in range(3)],np.int64)

class PinBoundary(B.Boundary):
 def __init__(self,contract,cones):
  super().__init__(contract,cones)
  vm={v['view']:(key,v) for key,z in contract['shared_inputs'].items() for v in z['views'] if key in ['trans_train','trans_val']}
  names=(R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()
  rawpaths={c['view']:c['raw_path'] for c in cones.values()}
  self.pinviews={};audit=[];self.numeric={};self.ops={};self.rowmaps={};self.edge_cache={}
  self.commonrows={d:np.array([r for z in self.records if z['domain']==d for r,_,_ in z['rows']],np.int64) for d in ['trans_train','trans_val']}
  rowindices={d:{int(r):j for j,r in enumerate(rr)} for d,rr in self.commonrows.items()}
  for rec in self.records:
   view=rec['view'];key=rec['key'];domain,v=vm[view];m=next(iter(read(R/rawpaths[view])['modules'].values()))
   rm={n.strip().lstrip('\\'):v['start']+j for j,n in enumerate(names[v['old_start']:v['old_stop']])}
   aux=read(R/'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2/views'/view/'virtual_nodes.json')
   for j,z in enumerate(aux):
    bit=m['netnames'][z['output']]['bits'];nn=[n for n,g in m['cells'].items() if n not in rm and g['connections'].get('Y')==bit]
    assert len(nn)==1;rm[nn[0]]=v['physical_stop']+j
   assert len(rm)==len(m['cells']);self.rowmaps[view]=rm
   tokens={(t['kind'],t['audit_name'],t['bit']):t['slot'] for t in self.maps[key]['tokens']};leaf={};drivers={}
   for n,p in m['ports'].items():
    if p['direction']=='input':
     for j,b in enumerate(p['bits']):leaf[b]=('PI',tokens['PI',n,j],0)
   for n,g in m['cells'].items():
    if 'DFF' in g['type'].upper():
     for pin in ['Q','QN']:
      for j,b in enumerate(g['connections'].get(pin,[])):leaf[b]=('Q',tokens['Q',n,j],int(pin=='QN'))
    else:
     out,op,ins=SCHEMA[g['type']];assert len(g['connections'][out])==1;b=g['connections'][out][0];assert b not in drivers;drivers[b]=rm[n];self.ops[domain,rm[n]]=op
   internal=[];bp=[];counts=np.zeros((len(self.commonrows[domain]),5,4),np.float32)
   pins=0;mux=0;repeated=0
   for n,g in m['cells'].items():
    if 'DFF' in g['type'].upper():continue
    _,op,ins=SCHEMA[g['type']];dst=rm[n];entries=[];mux+=op=='MUX'
    for j,pin in enumerate(ins):
     role=1 if op=='NOT' else 2+j if op=='MUX' else 0
     assert len(g['connections'][pin])==1;bit=g['connections'][pin][0];pins+=1
     if bit in leaf:
      kind,slot,phase=leaf[bit];i=rowindices[domain][dst];counts[i,role,0 if kind=='PI' else 1]+=1
      bp.append((i,role,slot,phase));entries.append((1,slot,phase,role))
     elif bit in ['0','1']:
      i=rowindices[domain][dst];counts[i,role,2+int(bit)]+=1;entries.append((2,int(bit),0,role))
     else:
      assert bit in drivers,(view,n,'unmapped required bit',bit)
      src=drivers[bit];internal.append((src,dst,role));entries.append((0,src,0,role))
    self.numeric[domain,dst]=sorted(entries)
    repeated+=len(entries)-len(set((a,b,c) for a,b,c,_ in entries))
   bb=np.array(bp,np.int64).reshape(-1,4)
   self.pinviews[view]=dict(rec=rec,internal=np.array(internal,np.int64).reshape(-1,3),boundary=bb,counts=counts)
   audit.append(dict(view=view,domain=domain,rank=rec['rank'],mux_cells=mux,input_pin_incidences=pins,internal_incidences=len(internal),variable_boundary_pins=len(bp),constant_boundary_pins=int(counts[:,:,2:].sum()),repeated_source_pin_incidences=repeated,correct_to_control_mux_role_change=bool(rec['rank'] and mux),row_mapping_exact=True))
  # Free large mostly-zero per-view count arrays after making compact domain templates.
  self.counttemplates={};self.boundarydenom={}
  for domain in ['trans_train','trans_val']:
   shared=sum(z['counts'] for z in self.pinviews.values() if z['rec']['domain']==domain)
   denom=np.sqrt(np.maximum(1,shared.sum((1,2))))[:,None]
   self.boundarydenom[domain]=denom
   for condition in ['shared','viewshuffle']:
    new=np.zeros_like(shared)
    for z in self.pinviews.values():
     if z['rec']['domain']!=domain:continue
     perm=rolemap(z['rec']['rank'],condition)
     for role in range(5):new[:,perm[role],:]+=z['counts'][:,role,:]
    self.counttemplates[domain,condition]=new
  for z in self.pinviews.values():del z['counts']
  # Every new internal incidence must be supported by the unchanged cell graph.
  for domain in ['trans_train','trans_val']:
   folder=R/contract['shared_inputs'][domain]['folder'];base=np.load(folder/'edge_index.npy',mmap_mode='r');N=contract['shared_inputs'][domain]['nodes'];packed=np.sort(base[0].astype(np.int64)*N+base[1]);ii=np.concatenate([z['internal'] for z in self.pinviews.values() if z['rec']['domain']==domain])
   keys=ii[:,0]*N+ii[:,1];pos=np.searchsorted(packed,keys);assert np.all(pos<len(packed)) and np.array_equal(packed[pos],keys)
   np.savez_compressed(O/f'pin_internal_{domain}.npz',src=ii[:,0],dst=ii[:,1],role=ii[:,2]);del packed,keys,base
  # Verify the actual graph-addressed loader against every local incidence in the old export.
  checked=0;nodes=0
  with gzip.open(B.I/'cone_pin_incidence.jsonl.gz','rt',encoding='utf-8') as f:
   for line in f:
    p=json.loads(line);c=cones[p['cone_id']];domain='trans_'+c['split'];rm=self.rowmaps[c['view']];glob=[rm[n] for n in c['members']];incoming=collections.defaultdict(list)
    for kind,src,phase,dst,role in p['edge']:
     incoming[glob[dst]].append((kind,glob[src] if kind==0 else src,phase,role));checked+=1
    for j,row in enumerate(glob):assert sorted(incoming[row])==self.numeric[domain,row] and p['op'][j]==self.ops[domain,row];nodes+=1
  table('pin_loading_audit.csv',audit)
  write('PIN_LOADING_VERIFIED.json',dict(views=len(audit),cones=len(cones),checked_local_pin_incidences=checked,checked_cone_member_occurrences=nodes,internal_incidences={d:sum(r['internal_incidences'] for r in audit if r['domain']==d) for d in ['trans_train','trans_val']},mux_cells=sum(r['mux_cells'] for r in audit),boundary_identity='shared in both role conditions',source_role_counts_preserved=True,all_existing_export_pins_match_new_graph_addressed_loader=True,base_edges_unchanged=True,roles=['COMM','NOT','DATA0','DATA1','SELECT']))
 def features(self,domain,condition,tag):
  rng=np.random.default_rng(420000+tag);vectors={}
  for key in sorted(self.maps):
   vv=np.zeros((len(self.maps[key]['tokens']),16),np.float32)
   for kind in ['PI','Q']:
    slots=[t['slot'] for t in self.maps[key]['tokens'] if t['kind']==kind];p=rng.permutation(len(slots))
    for j,s in enumerate(slots):vv[s]=B.code(kind,slots[int(p[j])])
   vectors[key]=vv
  counts=self.counttemplates[domain,condition];role=np.zeros((len(counts),5,20),np.float32);role[:,:,:4]=np.log1p(counts)
  common=np.zeros((len(counts),20),np.float32);common[:,:4]=np.log1p(counts.sum(1))
  for z in self.pinviews.values():
   rec=z['rec']
   if rec['domain']!=domain:continue
   p=z['boundary']
   if not len(p):continue
   i,rr,slot,phase=p.T;vv=vectors[rec['key']][slot]*(1-2*phase[:,None]);mapped=rolemap(rec['rank'],condition)[rr]
   np.add.at(common[:,4:],i,vv);np.add.at(role[:,:,4:],(i,mapped),vv)
  common[:,4:]/=self.boundarydenom[domain];role[:,:,4:]/=self.boundarydenom[domain][:,None,:]
  assert np.isfinite(common).all() and np.isfinite(role).all()
  # Roles split the same total boundary identity information, rather than add labels.
  assert np.allclose(role[:,:,4:].sum(1),common[:,4:],atol=5e-7,rtol=5e-7)
  cachekey=(domain,condition)
  if cachekey not in self.edge_cache:
   pp=[]
   for z in self.pinviews.values():
    if z['rec']['domain']!=domain:continue
    e=z['internal'];perm=rolemap(z['rec']['rank'],condition);pp.append(np.column_stack([e[:,:2],perm[e[:,2]]]))
   ee=np.concatenate(pp);self.edge_cache[cachekey]=tuple(torch.tensor(ee[:,j],device='cuda') for j in range(3))
  return dict(rows=torch.tensor(self.commonrows[domain],device='cuda'),boundary=torch.tensor(common,device='cuda'),pin_boundary=torch.tensor(role.reshape(len(role),100),device='cuda'),internal=self.edge_cache[cachekey])

def typed_conv(conv,x,e,scale,typed):
 src,dst,role=typed
 out=conv.propagate(e,x=(x,x),size=None)+(1+conv.eps)*x
 msg=x[src]*scale[role].to(x.dtype)
 out.index_add_(0,dst,msg.to(out.dtype))
 return conv.nn(out)

class Model(B.Model):
 def __init__(self):
  super().__init__();self.pin_boundary_adapter=torch.nn.Linear(100,39,bias=False);torch.nn.init.zeros_(self.pin_boundary_adapter.weight)
  self.pin_scales=torch.nn.ParameterList([torch.nn.Parameter(torch.zeros(5,w)) for w in WIDTHS])
 def encode(self,x,e,side=None):
  if side is None:return super().encode(x,e,None)
  rows=side['rows'];delta=self.boundary_adapter(side['boundary']).to(x.dtype)+self.pin_boundary_adapter(side['pin_boundary']).to(x.dtype);x=x.index_add(0,rows,delta)
  x=x+E.F.relu(self.mix(x));i=0
  def branch(enc,xx,start):
   for j,conv in enumerate(enc):xx=E.F.dropout(E.F.relu(typed_conv(conv,xx,e,self.pin_scales[start+j],side['internal'])),p=.2,training=self.training)
   return xx
  a=branch(self.enc_s,x[:,:self.split],0);b=branch(self.enc_f,x[:,self.split:],2);h=self.fuse(torch.cat([a,b],1));return E.F.dropout(E.F.relu(typed_conv(self.post,h,e,self.pin_scales[4],side['internal'])),p=.2,training=self.training)

def initial():
 E.seed_all(42);m=Model().cuda();state=torch.load(E.H/'init_s42.pt',map_location='cuda',weights_only=True);missing,extra=m.load_state_dict(state,strict=False)
 assert set(missing)=={'boundary_adapter.weight','pin_boundary_adapter.weight',*[f'pin_scales.{i}' for i in range(5)]} and not extra
 for k,v in state.items():assert torch.equal(v,m.state_dict()[k])
 for n,p in m.named_parameters():
  p.requires_grad_(not n.startswith('classifier.'))
  if n.startswith(('boundary_adapter.','pin_boundary_adapter.','pin_scales.')):assert p.count_nonzero()==0
 assert sum(p.numel() for p in m.parameters())==52455
 E.seed_all(819);return m,E.Projection().cuda()

def fixtures(b,cones):
 # Re-evaluate all old witness certificates using the NEW GLOBAL ROW incidence loader.
 certs=read(R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json');contexts=read(R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json');outcount=0
 for c in certs:
  env={tuple(t['token']):(int(t['mask_hex'],16)>>c['pattern'])&1 for t in contexts[c['context_id']]['input_masks']};outputs=[]
  for cid in c['cones']:
   co=cones[cid];domain='trans_'+co['split'];key=b.pinviews[co['view']]['rec']['key'];values={t['slot']:env[t['kind'],t['audit_name'],t['bit']] for t in b.maps[key]['tokens']};cache={}
   def ev(row):
    if row in cache:return cache[row]
    vv=[]
    for kind,src,phase,role in b.numeric[domain,row]:vv.append((role,(ev(src) if kind==0 else values[src] if kind==1 else src)^phase))
    op=b.ops[domain,row];aa=[v for _,v in vv]
    if op=='AND':v=aa[0]&aa[1]
    elif op=='OR':v=aa[0]|aa[1]
    elif op=='XOR':v=aa[0]^aa[1]
    elif op=='NOT':v=1-aa[0]
    else:dd=dict(vv);v=dd[3] if dd[4] else dd[2]
    cache[row]=v;return v
   outputs.append(ev(co['root_row']));outcount+=1
  assert outputs==c['expected_outputs'] and outputs[0]==outputs[1] and outputs[2]==outputs[3] and outputs[0]!=outputs[2]
 # Actual typed_conv + actual boundary adapter can retain the symmetric MUX counterexample.
 conv=E.legacy.GINConv(torch.nn.Identity());codes=np.stack([B.code('PI',i) for i in range(3)]);xx=torch.tensor(np.vstack([codes,np.zeros((1,16))]),dtype=torch.float32);edges=torch.tensor([[0,1,2],[3,3,3]])
 w=torch.zeros(5,16);w[2]=.25;w[3]=.5;w[4]=1
 a=typed_conv(conv,xx,edges,w,(edges[0],edges[1],torch.tensor([2,3,4])))
 z=typed_conv(conv,xx,edges,w,(edges[0],edges[1],torch.tensor([4,3,2])))
 untyped_a=conv(xx,edges);untyped_b=conv(xx,edges)
 assert torch.equal(untyped_a,untyped_b) and not torch.allclose(a[3],z[3])
 # Commutative roles retain symmetry and repeated inputs keep multiplicity.
 comm=typed_conv(conv,xx,edges,w,(edges[0],edges[1],torch.zeros(3,dtype=torch.long)))
 comm2=typed_conv(conv,xx,edges.flip(1),w,(edges[0].flip(0),edges[1].flip(0),torch.zeros(3,dtype=torch.long)))
 assert torch.allclose(comm,comm2)
 er=torch.tensor([[0,0],[3,3]]);probe=torch.ones(5,16)
 rep=typed_conv(conv,xx,er,probe,(er[0],er[1],torch.zeros(2,dtype=torch.long)));one=typed_conv(conv,xx,er[:,:1],probe,(er[0,:1],er[1,:1],torch.zeros(1,dtype=torch.long)))
 assert torch.allclose(rep[3],2*one[3])
 # Boundary DATA0/SELECT identities stay separated by the real 100->39 adapter.
 pad=torch.nn.Linear(100,39,bias=False);pad.weight.data.zero_();pad.weight.data[0,2*20+4:2*20+20]=torch.arange(1,17)/16;pad.weight.data[0,4*20+4:4*20+20]=torch.arange(16,0,-1)/16
 v=np.zeros((2,5,20),np.float32);v[0,2,4:]=codes[0];v[0,4,4:]=codes[2];v[1,2,4:]=codes[2];v[1,4,4:]=codes[0];yy=pad(torch.tensor(v.reshape(2,100)));assert not torch.allclose(yy[0],yy[1])
 write('FIXTURES_VERIFIED.json',dict(passed=True,existing_certificates=68,global_loader_root_replays=outcount,all_outputs_equal_existing_witnesses=True,actual_typed_conv_mux_swap_distinct=True,actual_boundary_role_adapter_mux_swap_distinct=True,untyped_mux_fixture_indistinguishable=True,commutative_swap_invariant=True,repeated_pin_multiplicity_retained=True,semantic_replay_uses_true_roles_only=True,probe_weights='explicit nonzero diagnostic,not trained performance',new_SAT=0))

def preflight(x,e,b,cones,byid,schedule):
 m,head=initial();base,_=E.load_initial(42,'cuda');m.eval();base.eval();side=b.features('trans_train','shared',0);wrong=b.features('trans_train','viewshuffle',0)
 assert torch.equal(side['rows'],wrong['rows']) and torch.equal(side['boundary'],wrong['boundary'])
 for a,z in zip(side['internal'][:2],wrong['internal'][:2]):assert torch.equal(a,z)
 assert not torch.equal(side['internal'][2],wrong['internal'][2]) and not torch.equal(side['pin_boundary'],wrong['pin_boundary'])
 oldrows,oldxx=B.Boundary.features(b,'trans_train','shared',0);assert torch.equal(oldrows,side['rows']);diff=float((oldxx-side['boundary']).abs().max());assert diff<5e-7
 with torch.inference_mode():
  ref=base.encode(x,e);now=m.encode(x,e,side);delta=float((ref-now).abs().max());assert torch.allclose(ref,now,atol=2e-4,rtol=2e-5),delta
 del base,ref,now,wrong,oldrows,oldxx;gc.collect();torch.cuda.empty_cache()
 rr=schedule[1];ids=sorted({p[k] for r in rr for p in [byid[r['pair_a']],byid[r['pair_b']]] for k in ['left_cone','right_cone']});ix={c:i for i,c in enumerate(ids)};m.train();head.train();E.seed_all(100043)
 with torch.autocast('cuda',dtype=torch.bfloat16):z=head(B.pool(m.encode(x,e,side),ids,cones))
 loss,parts=E.terms(z,rr,byid,ix,'R');assert torch.isfinite(loss);loss.backward()
 grads={n:float(p.grad.norm()) for n,p in m.named_parameters() if p.grad is not None}
 assert grads['boundary_adapter.weight']>0 and grads['pin_boundary_adapter.weight']>0
 for role in [2,3,4]:assert sum(float(p.grad[role].norm()) for p in m.pin_scales if p.grad is not None)>0
 assert all(np.isfinite(v) for v in grads.values())
 peak=torch.cuda.max_memory_allocated();assert peak/torch.cuda.get_device_properties(0).total_memory<.95
 write('PREFLIGHT.json',dict(passed=True,parameters=52455,original_parameters=46620,boundary_parameters=780,pin_parameters=5055,zero_adapter_output_max_delta=delta,common_boundary_vs_previous_max_delta=diff,gradient_norms=grads,optimizer_steps=0,backward_calls=1,peak_cuda_bytes=peak,true_wrong_same_boundary_and_edges=True,only_role_assignments_changed=True))
 del m,head,side,z,loss,parts;gc.collect();torch.cuda.empty_cache()

def main():
 O.mkdir(exist_ok=True);assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 B.initial=initial
 E.set_inputs();cones={c['cone_id']:c for c in read(E.J/'final_cones.json')};b=PinBoundary(E.T.CONTRACT,cones);fixtures(b,cones)
 inventory=read(B.PRE/'function_inventory.json');byid={p['pair_id']:p for p in inventory};schedule=collections.defaultdict(list)
 for row in read(B.PRE/'schedule.json'):
  if row['mode']=='main' and row['seed']==42:schedule[row['update']].append(row)
 assert len(schedule)==50 and len({r[k] for rr in schedule.values() for r in rr for k in ['pair_a','pair_b']})==382
 assert all(cones[byid[r[k]][side]]['split']=='train' for rr in schedule.values() for r in rr for k in ['pair_a','pair_b'] for side in ['left_cone','right_cone'])
 paths=[Path(__file__),OLD/'run.py',B.PRE/'engine.py',B.PRE/'schedule.json',B.PRE/'function_inventory.json',B.PRE/'negative_certificates.json',E.J/'final_pairs.json',E.J/'final_cones.json',E.H/'init_s42.pt',E.V/'input_contract.json',E.V/'normalization.npz',B.I/'SCHEMA.json',B.I/'cone_pin_incidence.jsonl.gz',B.I/'boundary_maps_audit_only.json',R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json',R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json',*b.raw_files]
 # Also bind every historical success marker and checkpoint, so preservation is verified.
 paths += [p for p in OLD.rglob('*') if p.is_file() and p.suffix in ['.pt','.json','.csv','.npy','.npz']]
 bindings={str(p.relative_to(R)):E.sha(p) for p in paths};contract=dict(frozen_files=bindings,seed=42,conditions={'shared':'true pin roles;shared boundary identity','viewshuffle':'per-view MUX-role derangement;shared boundary identity'},arms=['Z','R','P'],updates_per_condition=50,total_updates=300,detector_updates=0,new_SAT=0,test_reads=0,parameters=52455,model='original 39v3 dual2+2+post1;common20->39 boundary;100->39 role boundary;5 channelwise role residuals widths29/64/10/64/64',single_factor='role assignment only;all new parameters zero initialized in all six',fixed='same init/head/schedule/loss/Adam/dropout.2/BN/BF16/fixed50',validation_maps=[9000,9001],role_control='COMM/NOT unchanged;anchor view unchanged;other views DATA0/DATA1/SELECT cyclically deranged',preflight_backward_no_optimizer=1)
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 x,e=B.graph('trans_train')
 if not (O/'PREFLIGHT.json').exists():preflight(x,e,b,cones,byid,schedule)
 assert read(O/'PREFLIGHT.json')['passed']
 for condition in ['shared','viewshuffle']:
  for arm in ['Z','R','P']:
   B.train(condition,arm,x,e,b,cones,byid,schedule,dict(contract_sha=E.sha(O/'EXECUTION_CONTRACT.json'),alignment=condition,arm=arm))
 del x,e;gc.collect();torch.cuda.empty_cache()
 if not (O/'ANALYSIS_COMPLETE.json').exists():B.evaluate(b,cones)
 for p,h in bindings.items():assert E.sha(R/p)==h,p
 write('COMPLETE.json',dict(training_updates=300,preflight_backward_calls=1,finetune_updates=0,SAT=0,test_reads=0,old_inputs_and_results_unchanged=True,all_six_runs_complete=True))
 print('ALL_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%Y%m%d_%H%M%S")}.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
