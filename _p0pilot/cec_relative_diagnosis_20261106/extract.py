"""Read-only final/initial representation extraction for in-sample diagnostics."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,importlib.util,json,re,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_relative_seed42_20261106';C=R/'_p0pilot/cec_relative_contract_20261106'
s=importlib.util.spec_from_file_location('frozen_relative_run',OLD/'run.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
torch=A.torch;E=A.E;D=A.D;B=A.B
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def write(n,x):E.write(O/n,x)
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert not (O/'EXTRACTION_COMPLETE.json').exists()
 verified=read(OLD/'VERIFIED.json');assert verified['passed'];i=A.Interface();used={r['triple_id'] for r in i.schedule};sources=sorted({r['source'] for r in i.schedule})
 tt=[t for t in i.triples.values() if t['triple_id'] in used];unused=[]
 for source in sources:
  rr=[t for t in i.triples.values() if t['split']=='train' and t['source']==source and t['triple_id'] not in used]
  unused+=sorted(rr,key=lambda t:ident(['unused_readout_v1',t['triple_id']]))[:25]
 val=read(C/'evaluation_panel.json');panels={'train_used':tt,'train_unused_same_source':unused,'val':val};write('panels.json',panels)
 frozen=dict(read(OLD/'EXECUTION_CONTRACT.json')['frozen_files'])
 for n in ['INITIAL_STATE.pt','VERIFIED.json','PRIMARY_RESULT.json','evaluation_summary.csv','evaluation_by_source.csv']:
  frozen[str((OLD/n).relative_to(R))]=sha(OLD/n)
 for arm in A.ARMS:
  for n in ['resume.pt','history.json']:frozen[str((OLD/arm/n).relative_to(R))]=sha(OLD/arm/n)
  p=OLD/f'val_{arm}_remap9000.npz';frozen[str(p.relative_to(R))]=sha(p)
 p=R/'_p0pilot/cec_cause_audit_20261106/panel_cone_depths.json';frozen[str(p.relative_to(R))]=sha(p)
 for p in [Path(__file__),C/'triple_pool.json',C/'schedule_seed42.json',C/'evaluation_panel.json']:frozen[str(p.relative_to(R))]=sha(p)
 for p,h in frozen.items():assert sha(R/p)==h,p
 write('ANALYSIS_CONTRACT.json',dict(panels={k:dict(triples=len(v),sources=len({t['source'] for t in v})) for k,v in panels.items()},inference='all5 final train graph,tag9000;reuse finalval;initial checkpoint train+val tag9000',unused='up to25 fixed-hash unselected triples per active source;disjoint functions but same graph and source,not independent graph holdout',statistics='source-equal covariance PCA;within-source centering;descriptive WLS variance accounting,Spearman and metadata distance baselines;no learned detector or optimizer',models_and_SAT_updates=0,frozen_files=frozen))
 # Save endpoint metadata with no scores/labels used in its construction.
 depths=read(R/'_p0pilot/cec_cause_audit_20261106/panel_cone_depths.json');raw={};metadata={};pool_sources={}
 for pname,rr in panels.items():
  for t in rr:
   for j,cid in enumerate(t['cones']):
    c=i.cones[cid]
    if c['view'] not in raw:
     p=R/c['raw_path'];assert sha(p)==c['raw_sha'];raw[c['view']]=next(iter(read(p)['modules'].values()))
    gate=raw[c['view']]['cells'][c['output_cell']]['type'];tokens=sorted({tuple(t[:3]) for t in c['leaves']})
    m=dict(cone_id=cid,split=c['split'],source=t['source'],host=re.match(r'^(rs232|s\d+)',t['source']).group(),view=c['view'],recipe=c['view'].split('__')[-1],root_row=c['root_row'],members=len(c['members']),depth=depths[cid]['gate_depth'],mux=depths[cid]['mux'],cut=len(tokens),gate=gate,logical_op=D.SCHEMA[gate][1],role=['A','A','B','B','C','C'][j],panel=pname,leaf_tokens=json.dumps(tokens,ensure_ascii=False))
    if cid in metadata:assert metadata[cid]==m
    metadata[cid]=m
 table('cone_metadata.csv',list(metadata.values()));del raw;gc.collect()
 E.set_inputs();scratch=O/'pin_loader';scratch.mkdir(exist_ok=True);D.O=scratch;B.O=scratch;b=D.PinBoundary(E.T.CONTRACT,i.cones);forward_count=0;states=[]
 for domain in ['train','val']:
  rr=tt+unused if domain=='train' else val;ids=sorted({c for t in rr for c in t['cones']});x,e=B.graph('trans_'+domain);side=b.features('trans_'+domain,'shared',9000);sp=A.pool_spec(ids,i.cones)
  for arm in (['INIT']+A.ARMS if domain=='train' else ['INIT']):
   m,head=D.initial()
   if arm=='INIT':ck=torch.load(OLD/'INITIAL_STATE.pt',map_location='cuda',weights_only=False)
   else:ck=torch.load(OLD/arm/'resume.pt',map_location='cuda',weights_only=False);assert ck['completed']==50
   m.load_state_dict(ck['model']);head.load_state_dict(ck['projection']);del ck;m.eval();head.eval();before=A.state_digest(m,head)
   with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):h=m.encode(x,e,side);u=A.pool(h,sp);z=head(u)
   assert A.state_digest(m,head)==before
   np.savez_compressed(O/f'{domain}_{arm}_remap9000.npz',cone_ids=np.array(ids),concat128=u.float().cpu().numpy(),projection32=z.float().cpu().numpy());forward_count+=1;states.append(dict(domain=domain,arm=arm,weights_and_BN_unchanged=True))
   print('EXTRACTED',domain,arm,len(ids),flush=True);del m,head,h,u,z;gc.collect();torch.cuda.empty_cache()
  del x,e,side,sp;gc.collect();torch.cuda.empty_cache()
 for p,h in frozen.items():assert sha(R/p)==h,p
 write('EXTRACTION_COMPLETE.json',dict(model_forwards=forward_count,backwards=0,optimizer_updates=0,SAT=0,test_reads=0,states=states,old_files_unchanged=True,peak_gpu_bytes=torch.cuda.max_memory_allocated()))
 print('EXTRACTION_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
