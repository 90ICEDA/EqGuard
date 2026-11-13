"""Repaired-pool actual loading and no-update gradient preflight."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,json,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;C=R/'_p0pilot/cec_repaired_contract_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106';P=R/'_p0pilot/cec_boundary_panel_expand_20261107'
sys.path.insert(0,str(PRE));import model_interface as M
import preflight as F
sys.path.insert(0,str(P));from panel_loader import PanelLoader
torch=M.torch
def read(p):return M.read(p)
def sha(p):return M.sha(p)
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
class Loader(M.Loader):
 def __init__(self):
  for n,h in read(C/'FROZEN_INDICES.json').items():assert sha(C/n)==h,n
  p=PanelLoader();self.graphs=p.graphs;self.contexts=p.contexts;self.tokens=p.tokens;self.training={u['unit_id']:u for u in read(C/'TRAIN_TRIPLES.json')};self.contract=read(C/'REPAIRED_CONTRACT.json');self.schedule=read(C/'SCHEDULE_SEED42.json')
  for step in self.schedule:
   for r in step['units']:r['common_negative_edges']=r['negative_edges']
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert not (O/'COMPLETE.json').exists();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 protected=dict(read(C/'VERIFIED.json')['protected_files'])
 for p in [C/n for n in ['FROZEN_INDICES.json','REPAIRED_CONTRACT.json','TRAIN_TRIPLES.json','VAL_H3_NONFORCED.json','SCHEDULE_SEED42.json','BUDGET.json']]+[PRE/'INITIAL_STATE.pt',PRE/'model_interface.py',PRE/'preflight.py',P/'panel_loader.py',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('EXECUTION_CONTRACT.json',dict(scope='actual repairedloader andfrozen gradients only',training=0,SAT=0,optimizer_objects=0,parent_contract_sha=sha(C/'REPAIRED_CONTRACT.json'),protected_files=protected))
 loader=Loader();model=M.fresh('cuda');initial=torch.load(PRE/'INITIAL_STATE.pt',map_location='cuda',weights_only=False);model.load_state_dict(initial['model']);model.eval();before=M.state_digest(model);assert before==initial['digest'];assert sum(p.numel() for p in model.parameters())==47360
 stats=[];gradsteps={1,2,16,32};forwards=backwards=0;firstmux=None
 for update in range(1,33):
  b=loader.batch(update,'cuda');a=b['arrays'];g=b['graph'];lossin=b['loss'];assert lossin['candidates'].shape==(12,3) and lossin['negative_edges'].shape==(12,2);assert abs(float(lossin['query_weight'].sum())-1)<2e-7 and abs(float(lossin['negative_weight'].sum())-1)<2e-7
  if firstmux is None and np.any(a['edge_role']>=2):firstmux=update
  with torch.no_grad():root,h,_,consumed=model.encode(g,True);parts,totals,aux=M.objective(root,lossin)
  forwards+=1;assert torch.isfinite(root).all() and all(torch.isfinite(v) for v in totals.values());geom=F.geometry(root.cpu().numpy());assert geom['root_mean_std']>1e-5
  nd=aux['negative_distances'].cpu().numpy();d=aux['distances'].cpu().numpy();stats.append(dict(update=update,units=2,roots=12,queries=12,distances=36,negatives=12,nodes=g['nodes'],edges=g['edges'],depth=g['max_level'],min_negative_distance=float(nd.min()),zero_negative_pairs=int(np.sum(nd<=1.00001e-6)),flat_candidate_queries=int(np.sum(np.ptp(d,axis=1)<=1e-7)),**geom,**{k:float(v) for k,v in parts.items()},**{'loss_'+k:float(v) for k,v in totals.items()}))
  assert consumed['consumed_nodes']==g['nodes'] and consumed['consumed_pin_edges']==g['edges']
  np.savez_compressed(O/f'preview{update:02}.npz',cone_ids=np.array(b['cone_ids']),root64=root.cpu().numpy(),**{k:v.cpu().numpy() for k,v in lossin.items()})
  if update==1:
   reference=F.numpy_reference(model.state_dict(),a);error=float(np.max(np.abs(reference-h.cpu().numpy())));assert np.allclose(reference,h.cpu().numpy(),atol=2e-5,rtol=2e-5);write('REFERENCE_CHECK.json',dict(nodes=g['nodes'],max_allnode_error=error,passed=True))
  del b,g,root,h,parts,totals,aux;gc.collect();torch.cuda.empty_cache()
 if firstmux:gradsteps.add(firstmux)
 table('loaded_batches.csv',stats);gradrows=[];vectors={}
 for update in sorted(gradsteps):
  b=loader.batch(update,'cuda');root,_=model.encode(b['graph']);parts,totals,aux=M.objective(root,b['loss']);forwards+=1;vv={}
  for name,loss in {**parts,**{'total_'+k:v for k,v in totals.items()}}.items():
   vals=torch.autograd.grad(loss,list(model.parameters()),retain_graph=True,allow_unused=True);backwards+=1;vv[name]=np.concatenate([(np.zeros(p.numel(),np.float32) if v is None else v.detach().cpu().numpy().ravel()) for p,v in zip(model.parameters(),vals)]);assert np.isfinite(vv[name]).all();vectors[f'step{update}_{name}']=vv[name]
  common=vv['different']+vv['variance_weighted']
  for group,expected in [('Z',common),('R',common+vv['CE_R']),('P',common+vv['CE_P'])]:assert np.linalg.norm(vv['total_'+group]-expected)/max(np.linalg.norm(vv['total_'+group]),1e-30)<2e-5
  gradrows.append(dict(batch=update,CE_R=float(parts['CE_R'].detach()),CE_P=float(parts['CE_P'].detach()),association_R_norm=float(np.linalg.norm(vv['CE_R'])),association_P_norm=float(np.linalg.norm(vv['CE_P'])),common_norm=float(np.linalg.norm(common)),association_RP_cos=F.cosine(vv['CE_R'],vv['CE_P']),total_RP_cos=F.cosine(vv['total_R'],vv['total_P']),total_R_norm=float(np.linalg.norm(vv['total_R'])),total_P_norm=float(np.linalg.norm(vv['total_P']))))
  assert np.linalg.norm(vv['CE_R'])>0 and np.linalg.norm(vv['CE_P'])>0 and all(p.grad is None for p in model.parameters());del b,root,parts,totals,aux;gc.collect();torch.cuda.empty_cache()
 table('gradient_summary.csv',gradrows);np.savez_compressed(O/'gradient_vectors.npz',**vectors)
 # Independent group clones from same frozen state,identical actualdata and correct loss choice.
 b=loader.batch(1,'cuda');outputs=[]
 for arm in ['Z','R','P']:
  m=M.fresh('cuda');m.load_state_dict(initial['model']);m.eval();digest=M.state_digest(m)
  with torch.no_grad():z,_=m.encode(b['graph']);parts,totals,_=M.objective(z,b['loss'])
  forwards+=1;outputs.append(z.cpu().numpy());assert digest==before==M.state_digest(m);assert abs(float(totals[arm])-stats[0]['loss_'+arm])<2e-5;del m
 assert all(np.allclose(outputs[0],x,atol=2e-5,rtol=2e-5) for x in outputs[1:])
 validation=read(C/'VAL_H3_NONFORCED.json');p=PanelLoader()
 for u in validation:
  a,q=p.unit(u,9000);assert len(q)==2*u['functions'] and len(a['root_index'])==2*u['functions']
 assert len(validation)==73 and M.state_digest(model)==before
 for path,hashval in protected.items():assert sha(R/path)==hashval,path
 write('COMPLETE.json',dict(passed=True,parameters=47360,actual_batches=32,per_group_budget=dict(unit_slots=64,queries=384,candidate_distances=1152,negatives=384),gradient_batches=sorted(gradsteps),validation_units_loaded=73,model_forwards=forwards,autograd_calls=backwards,weights_buffers_and_grad_fields_unchanged=True,optimizer_objects=0,training=0,SAT=0,test_reads=0,zero_negative_pairs_over_all_batches=sum(r['zero_negative_pairs'] for r in stats),flat_candidate_queries=sum(r['flat_candidate_queries'] for r in stats),claim='necessary loading/gradient checks only,NOT proof P can be fitted',protected_files_unchanged=True))
 print('REPAIRED_PREFLIGHT_COMPLETE',json.dumps(gradrows),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
