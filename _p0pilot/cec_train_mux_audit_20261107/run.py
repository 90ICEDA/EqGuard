"""Source-bound proof/role audit,existing128bit replay,cached rankings,frozen VJPs."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,importlib.util,itertools,json,re,sys,traceback,time
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';P=R/'_p0pilot/cec_boundary_panel_expand_20261107';OLD=R/'_p0pilot/cec_dualcode_six_seed42_20261107';BASE=R/'_p0pilot/cec_freeq_preflight_20261106';C=R/'_p0pilot/cec_repaired_contract_20261107'
sys.path.insert(0,str(BASE));import model_interface as M
sys.path.insert(0,str(P));from panel_loader import PanelLoader
torch=M.torch
def read(p):return M.read(p)
def sha(p):return M.sha(p)
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if rr:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert not (O/'COMPLETE.json').exists() and 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 assert read(OLD/'VERIFIED.json')['passed'];protected=dict(read(OLD/'EXECUTION_CONTRACT.json')['protected_files'])
 for n,h in read(OLD/'OUTPUT_MANIFEST.json').items():assert sha(OLD/n)==h,n;protected[str((OLD/n).relative_to(R))]=h
 for p in [OLD/'VERIFIED.json',OLD/'PUBLISHED.json',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 write('AUDIT_CONTRACT.json',dict(scope='3existing trainMUX units;proof andnativepin audit;cached12codes;INIT/R0/R1 frozenCE gradients at9000/9001',training=0,SAT=0,new_real_input_patterns=0,test_reads=0,protected_files=protected))
 us=[u for u in read(C/'TRAIN_TRIPLES.json') if u['has_mux']];assert len(us)==3;write('SELECTED_UNITS.json',us);loader=PanelLoader();cones={c['cone_id']:c for c in read(J/'final_cones.json')};pairs={p['pair_id']:p for p in read(J/'final_pairs.json')};proofs=read(J/'proofs.json');witness=read(J/'witness_contexts.json');rawcache={};proofrows=[];pairrows=[];rolerows=[];stats=[];nodevalues={};models={};rebuilt={};projection=list(csv.DictReader((J/'proof_projection.csv').open(encoding='utf-8-sig',newline='')));selectedproofs=set();MASK=(1<<128)-1
 def protect(p):protected[str(p.relative_to(R))]=sha(p)
 for path in [J/'final_pairs.json',J/'final_cones.json',J/'proofs.json',J/'proof_projection.csv',J/'witness_contexts.json',C/'REUSED_CERTIFICATES.json',P/'DIFFERENT_FUNCTION_CERTIFICATES.json']:protect(path)
 for u in us:
  for fi,pid in enumerate(u['pair_ids']):
   pair=pairs[pid];ids=u['cones'][2*fi:2*fi+2];assert set(ids)=={pair['left_cone'],pair['right_cone']}
   for proofid in pair['proof_ids']:
    proof=proofs[proofid];selectedproofs.add(proofid);folder=R/proof['folder'];model,script,log=[folder/n for n in ['model.v','run.ys','run.log']];st=script.read_text(encoding='utf-8');lt=log.read_text(encoding='utf-8');assert sha(model)==proof['model_sha'] and hashlib.sha256(st.encode()).hexdigest()==proof['script_sha'] and sha(log)==proof['log_sha'];q=int(proof['query_id']);cmd=[l for l in st.splitlines() if l.startswith('sat ')][q];assert re.fullmatch(r'sat '+re.escape(proof['args'])+r' -timeout \d+ -show-inputs -show-outputs -dump_json "[^"]+"',cmd);block=re.split(r'^(?:Q|QUERY)\d{4}\s*$',lt,flags=re.M)[q+1];assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block and 'ERROR:' not in lt
    for p in [model,script,log]:protect(p)
    pr=next(r for r in projection if r['pair_id']==pid and r['proof_id']==proofid);assert {(pr['view_a'],int(pr['root_a'])),(pr['view_b'],int(pr['root_b']))}=={(cones[c]['view'],cones[c]['root_bit']) for c in ids}
    text=model.read_text(encoding='utf-8');blocks={name:body for name,body in re.findall(r'module\s+(\w+)\b(.*?)endmodule',text,re.S)};index=int(pr['index'])
    for name,bit in [('left_design',int(pr['root_a'])),('right_design',int(pr['root_b']))]:
     direct=re.search(r'assign\s+obs\['+str(index)+r'\]\s*=\s*b'+str(bit)+r'\s*;',blocks[name]);concat=re.search(r'assign\s+obs\s*=\s*\{([^}]+)\}\s*;',blocks[name])
     assert direct or (concat and list(reversed([x.strip() for x in concat.group(1).split(',')]))[index]=='b'+str(bit)),(name,index,bit)
    assert re.search(r'observation_diff\s*=\s*\|\s*\(',text), 'aggregate observation must be OR of differences'
    proofrows.append(dict(unit_id=u['unit_id'],function=fi,pair_id=pid,proof_id=proofid,query=q,projection_index=index,root_a=int(pr['root_a']),root_b=int(pr['root_b']),hashes_query_success_and_projection_verified=True))
   for side,cid in enumerate(ids):
    c=cones[cid];g=loader.graphs[cid];path=R/c['raw_path'];assert sha(path)==c['raw_sha'];protect(path)
    if c['view'] not in rawcache:rawcache[c['view']]=next(iter(read(path)['modules'].values()))
    raw=rawcache[c['view']];key=loader.contexts[cid];tokens=loader.tokens[key];index=M.L.ModuleIndex(raw,tokens);reb=index.cone(c['root_bit']);assert json.loads(json.dumps(reb))==g,cid;rebuilt[cid]=reb
    # Independently evaluate raw-module gates,not the local-interface replay function.
    env={tuple(x['token']):int(x['mask_hex'],16) for x in witness[u['context_id']]['input_masks']};leaf={};drivers={}
    for name,port in raw['ports'].items():
     if port['direction']=='input':
      for bitno,bit in enumerate(port['bits']):leaf[bit]=env['PI',name,bitno]
    for name,cell in raw['cells'].items():
     if 'DFF' in cell['type'].upper():
      for pin in ['Q','QN']:
       for bitno,bit in enumerate(cell['connections'].get(pin,[])):leaf[bit]=env['Q',name,bitno]^(MASK if pin=='QN' else 0)
     elif cell['type'] in M.L.SCHEMA:drivers[cell['connections'][M.L.SCHEMA[cell['type']][0]][0]]=(name,cell)
    cache={}
    def ev(bit):
     if isinstance(bit,str):assert bit in ['0','1'];return MASK if bit=='1' else 0
     if bit in cache:return cache[bit]
     if bit in leaf:v=leaf[bit]
     else:
      _,cell=drivers[bit];typ=cell['type'];_,op,ports=M.L.SCHEMA[typ];v=[ev(cell['connections'][p][0]) for p in ports]
      if op=='AND':v=v[0]&v[1]
      elif op=='OR':v=v[0]|v[1]
      elif op=='XOR':v=v[0]^v[1]
      elif op=='NOT':v=MASK^v[0]
      else:v=(v[1]&v[2])|(v[0]&(MASK^v[2]))
     cache[bit]=v;return v
    root=ev(c['root_bit']);assert root==int(u['function_signatures'][fi],16)
    values=[];slotenv={t['slot']:env[t['kind'],t['audit_name'],t['bit']] for t in tokens};inc=collections.defaultdict(list)
    for s,d,r,p in g['edge']:inc[d].append((s,r,p))
    for n,opid in enumerate(g['op']):
     op=M.L.OPS[opid]
     if op in ['PI','Q']:v=slotenv[g['slot'][n]]
     elif op.startswith('CONST'):v=MASK if op=='CONST1' else 0
     else:
      d={r:values[s]^(MASK if p else 0) for s,r,p in inc[n]};vv=[values[s]^(MASK if p else 0) for s,r,p in inc[n]]
      if op=='AND':v=vv[0]&vv[1]
      elif op=='OR':v=vv[0]|vv[1]
      elif op=='XOR':v=vv[0]^vv[1]
      elif op=='NOT':v=MASK^vv[0]
      else:v=(d[4]&d[3])|((MASK^d[4])&d[2])
     values.append(v)
    assert values[g['root']]==root;nodevalues[cid]=values
    for n,op in enumerate(g['op']):
     if op!=8:continue
     cellname=g['keys'][n][1];cell=raw['cells'][cellname];ports=M.L.SCHEMA[cell['type']][2];d={r:values[s]^(MASK if p else 0) for s,r,p in inc[n]};a,b,s=d[2],d[3],d[4]
     for role,pin in zip([2,3,4],ports):
      edge=next(e for e in g['edge'] if e[1]==n and e[2]==role);sn,_,_,phase=edge;sourcebit=cell['connections'][pin][0];assert (values[sn]^(MASK if phase else 0))==ev(sourcebit);rolerows.append(dict(unit_id=u['unit_id'],function=fi,side=side,cone_id=cid,mux_node=n,mux_cell=cellname,native_type=cell['type'],role=role,pin=pin,source_bit=sourcebit,source_op=M.L.OPS[g['op'][sn]],source_slot=g['slot'][sn],source_level=g['level'][sn],phase=phase,raw_pin_matches_signed_edge=True))
    # Shortest AND longest dependency distances to each node,computed backwards.
    shortest={g['root']:0};longest={g['root']:0}
    for n in reversed(range(len(g['op']))):
     for sn,_,_ in inc[n]:shortest[sn]=min(shortest.get(sn,10**9),shortest[n]+1);longest[sn]=max(longest.get(sn,-1),longest[n]+1)
    stats.append(dict(unit_id=u['unit_id'],function=fi,side=side,cone_id=cid,root_cell=c['output_cell'],root_bit=c['root_bit'],root_op=M.L.OPS[g['op'][g['root']]],gates=sum(o>=4 for o in g['op']),depth=max(g['level']),boundary=sum(o<2 for o in g['op']),MUX_count=g['op'].count(8),one_fraction=root.bit_count()/128,min_leaf_distance=min(shortest[n] for n,o in enumerate(g['op']) if o<2),max_leaf_distance=max(longest[n] for n,o in enumerate(g['op']) if o<2)))
   pairrows.append(dict(unit_id=u['unit_id'],function=fi,pair_id=pid,true_left=ids[0],true_right=ids[1],signature=u['function_signatures'][fi],raw_replay_equal=True))
 table('PROOF_BINDING_AUDIT.csv',proofrows);table('FUNCTION_PAIRS.csv',pairrows);table('RAW_PIN_ROLE_AUDIT.csv',rolerows);table('CONE_STRUCTURE.csv',stats)
 # Reuse all nine saved negative certificates,never substitute a new SAT result.
 certs={r['certificate_id']:r for r in read(P/'DIFFERENT_FUNCTION_CERTIFICATES.json')};certrows=[]
 for r in read(C/'REUSED_CERTIFICATES.json'):
  if r['unit_id'] not in {u['unit_id'] for u in us}:continue
  u=next(u for u in us if u['unit_id']==r['unit_id']);c=certs[r['certificate_id']];fs=[u['pair_ids'].index(p) for p in r['pair_ids']];out=[(nodevalues[cid][loader.graphs[cid]['root']]>>c['pattern'])&1 for f in fs for cid in u['cones'][2*f:2*f+2]];assert out[0]==out[1] and out[2]==out[3] and out[0]!=out[2];hamming=(int(u['function_signatures'][fs[0]],16)^int(u['function_signatures'][fs[1]],16)).bit_count();certrows.append(dict(unit_id=u['unit_id'],functions=str(fs),certificate_id=r['certificate_id'],saved_pattern=c['pattern'],outputs=str(out),different_on_saved128=hamming))
 table('NEGATIVE_CERTIFICATE_REPLAY.csv',certrows)
 # Exact common-subexpression hashes within implementation;not a CEC substitute.
 expressions={};muxrows=[]
 for u in us:
  for cid in u['cones']:
   g=loader.graphs[cid];inc=collections.defaultdict(list)
   for s,d,r,p in g['edge']:inc[d].append((s,r,p))
   hh=[]
   for n,op in enumerate(g['op']):
    key=(op,g['slot'][n]) if op<4 else (op,sorted((r,p,hh[s]) for s,r,p in inc[n]));hh.append(hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest())
   expressions[cid]=hh
   for n,op in enumerate(g['op']):
    if op==8:
     d={r:nodevalues[cid][s]^(MASK if p else 0) for s,r,p in inc[n]};muxrows.append(dict(unit_id=u['unit_id'],cone_id=cid,node=n,S_ones=d[4].bit_count(),data_disagree=(d[2]^d[3]).bit_count(),select0_and_data_disagree=((MASK^d[4])&(d[2]^d[3])).bit_count(),select1_and_data_disagree=(d[4]&(d[2]^d[3])).bit_count(),A_expr=next(expressions[cid][s] for s,r,p in inc[n] if r==2),B_expr=next(expressions[cid][s] for s,r,p in inc[n] if r==3),S_expr=next(expressions[cid][s] for s,r,p in inc[n] if r==4)))
 write('MUX_EXISTING_PATTERN_CONTEXT.json',muxrows)
 # Cached function-level query errors and removal of a common implementation offset.
 queryrows=[];center=[];unitsummary=[]
 for tag in range(9000,9012):
  for arm in ['INIT','Z0','Z1','R0','R1','P0','P1']:
   with np.load(OLD/f'train_{arm}_tag{tag}.npz') as z:ids=z['cone_ids'].tolist();x=z['root64'].astype(float)
   ix={c:i for i,c in enumerate(ids)}
   for u in us:
    v=x[[ix[c] for c in u['cones']]];vc=v.copy();means=[v[s::2].mean(0) for s in [0,1]]
    for side in [0,1]:vc[side::2]-=means[side]
    records=[]
    for mode,zz in [('raw',v),('candidate_set_centered',vc)]:
     wins=[]
     for f in range(3):
      for side in [0,1]:
       ds=np.sqrt(np.mean((zz[2*f+side]-zz[[2*j+1-side for j in range(3)]])**2,1)+1e-12);true=float(ds[f]);ww=[float(true<ds[j])+.5*float(true==ds[j]) for j in range(3) if j!=f];wins.extend(ww)
       if mode=='raw':queryrows.append(dict(tag=tag,arm=arm,unit_id=u['unit_id'],function=f,side=side,true_distance=true,wrong1_distance=float(ds[(f+1)%3]),wrong2_distance=float(ds[(f+2)%3]),rank=1+int(np.sum(ds<true)),pairwise_win=float(np.mean(ww)),winning_candidate=int(np.argmin(ds))))
     records.append(float(np.mean(wins)))
    within=np.sqrt(np.mean(vc**2));offset=np.sqrt(np.mean((means[0]-means[1])**2));center.append(dict(tag=tag,arm=arm,unit_id=u['unit_id'],raw_win=records[0],centered_win=records[1],implementation_offset_RMS=float(offset),within_side_RMS=float(within),offset_over_within=float(offset/max(within,1e-12))))
 table('FUNCTION_QUERY_ERRORS.csv',queryrows);table('IMPLEMENTATION_CENTER_DIAGNOSTIC.csv',center)
 # Frozen true-CE gradients,not a new optimizer or parameter update.
 gradientrows=[];leafrows=[];vectors={};forwards=autograd=0
 for arm in ['INIT','R0','R1']:
  m=M.fresh('cuda');ck=torch.load(OLD/('INITIAL_STATE.pt' if arm=='INIT' else arm+'/resume.pt'),map_location='cuda',weights_only=False);m.load_state_dict(ck['model']);m.eval();before=M.state_digest(m)
  for tag in [9000,9001]:
   for u in us:
    ids=u['cones'];a=loader.arrays(ids,tag);g=M.pack(a,'cuda');g['x'].requires_grad_(True);root,au=m.encode(g);forwards+=1;anchors=torch.arange(6,device='cuda');candidates=torch.tensor([[2*j+1-(i%2) for j in range(3)] for i in range(6)],device='cuda');real=torch.tensor([i//2 for i in range(6)],device='cuda');dist=torch.sqrt((root[anchors,None,:]-root[candidates]).square().mean(-1)+1e-12);loss=torch.nn.functional.cross_entropy(-dist,real);pp=list(m.parameters());vv=torch.autograd.grad(loss,[*pp,g['x']],allow_unused=True);autograd+=1;assert all(v is None or torch.isfinite(v).all() for v in vv);pg={n:0. if v is None else float(v.norm()) for (n,p),v in zip(m.named_parameters(),vv[:-1])};gx=vv[-1].detach().cpu().numpy();vectors[f'{arm}_{tag}_{u["unit_id"]}']=np.concatenate([np.zeros(p.numel(),np.float32) if v is None else v.detach().cpu().numpy().ravel() for p,v in zip(pp,vv[:-1])]);gradientrows.append(dict(arm=arm,tag=tag,unit_id=u['unit_id'],true_CE=float(loss.detach()),input_identity_gradient_norm=float(np.linalg.norm(gx[:,9:])),**pg))
    for i,cid in enumerate(ids):
     local=loader.graphs[cid];ptr=a['graph_ptr'][i];inc=collections.defaultdict(list)
     for s,d,r,p in local['edge']:inc[d].append(s)
     dd={local['root']:0}
     for n in reversed(range(len(local['op']))):
      for sn in inc[n]:dd[sn]=min(dd.get(sn,10**9),dd[n]+1)
     for n,op in enumerate(local['op']):
      if op<2:leafrows.append(dict(arm=arm,tag=tag,unit_id=u['unit_id'],function=i//2,side=i%2,slot=local['slot'][n],shortest_distance=dd[n],identity_gradient_norm=float(np.linalg.norm(gx[ptr+n,9:]))))
    assert all(p.grad is None for p in pp);del g,root,loss,vv;gc.collect();torch.cuda.empty_cache()
  assert M.state_digest(m)==before;del m,ck;gc.collect();torch.cuda.empty_cache()
 table('FROZEN_TRUE_CE_GRADIENTS.csv',gradientrows);table('LEAF_GRADIENT_PATHS.csv',leafrows);np.savez_compressed(O/'gradient_vectors.npz',**vectors)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('PROTECTED_INPUTS.json',protected);write('COMPLETE.json',dict(passed=True,units=3,function_pairs=9,true_proof_queries=len(selectedproofs),negative_certificates=len(certrows),raw_graphs_rebuilt=len(rebuilt),native_MUX_instances=sum(s['MUX_count'] for s in stats),functions_without_MUX=sum(s['MUX_count']==0 for s in stats if s['side']==0),model_forwards=forwards,autograd_calls=autograd,optimizer_objects=0,training=0,SAT=0,new_real_input_patterns=0,test_reads=0,old_files_and_frozen_states_unchanged=True))
 print('TRAIN_MUX_AUDIT_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
