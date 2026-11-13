"""Offline evaluation only of15committed last200 checkpoints;no optimizer/SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import csv,gc,hashlib,importlib.util,json,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;BASE=R/'_p0pilot/control_five_seed42_20261107';L=R/'_p0pilot/control_loader_po_20261105'
sys.path.insert(0,str(L));from supervision_loader import FiveGroupLoader,read,sha
s=importlib.util.spec_from_file_location('frozen_detector_runtime',BASE/'run.py');E=importlib.util.module_from_spec(s);s.loader.exec_module(E);torch=E.torch;T=E.T;Model=E.Model
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(m):
 h=hashlib.sha256()
 for n,t in sorted(m.state_dict().items()):h.update((n+str(t.dtype)+str(tuple(t.shape))).encode());h.update(t.detach().cpu().contiguous().numpy().tobytes())
 return h.hexdigest()
def main():
 assert not (O/'INFERENCE_COMPLETE.json').exists() and 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert read(O/'LINEAGE_VERIFIED.json')['passed'];torch.set_num_threads(2);loader=FiveGroupLoader();T.arrays=loader.arrays;T.CONTRACT=loader.feature_contract;T.NORM=loader.normalization;assert not T.EXTRA and T.EQ==0;protected=dict(loader.checked_files);audit=[];repeats=[];forwards=0;start=time.perf_counter()
 for p in [Path(__file__),BASE/'run.py',BASE/'analyze.py',R/'models/gin_net.py',O/'lineage.py',O/'LINEAGE_VERIFIED.json']:protected[str(p.relative_to(R))]=sha(p)
 contract=dict(scope='fixedlast200 offline inference,not newtraining',seeds=[42,1,2],arms=E.ARMS,source_updates_each=200,selection='fixed200 for all15,not test/val selected',features='unchanged39v3',thresholds='recalibrate using SAME frozen transval quantile formulas at fixedcheckpoint;AP thresholdfree',source_selected_retained=True,model_updates=0,optimizer_objects=0,SAT=0,protected_inputs=protected)
 write(O/'INFERENCE_CONTRACT.json',contract)
 for seed in [42,1,2]:
  old=R/f'_p0pilot/control_five_seed{seed}_20261107';out=O/f'seed{seed}';out.mkdir(exist_ok=True);assert read(old/'VERIFIED.json')['passed'];source_manifest=read(old/'OUTPUT_MANIFEST.json')
  for name,h in source_manifest.items():assert sha(old/name)==h,name;protected[str((old/name).relative_to(R))]=h
  for arm in E.ARMS:
   ck=torch.load(old/arm/'resume.pt',map_location='cpu',weights_only=False);assert ck['completed']==200 and ck['arm']==arm and [r['update'] for r in ck['history']]==list(range(1,201));dest=out/arm;dest.mkdir(exist_ok=True);T.seed(seed);m=Model().cuda();m.load_state_dict(ck['model']);m.eval();assert sum(p.numel() for p in m.parameters())==46620;before=digest(m)
   if (dest/'EVALUATED.json').exists():
    ev=read(dest/'EVALUATED.json');assert ev['checkpoint_sha']==sha(old/arm/'resume.pt') and ev['state_digest']==before and ev['source_completed_updates']==200 and ev['model_updates']==0
    for key,h in ev['prediction_sha'].items():
     path=dest/(key+'_scores.npy');assert sha(path)==h;a=loader.arrays(*key.split('_'));p=np.load(path,mmap_mode='r');assert len(p)==len(a['y']) and np.isfinite(p).all();audit.append(dict(seed=seed,arm=arm,key=key,rows=len(p),scores_sha=h,state_unchanged=True))
    print('REUSE_VERIFIED',seed,arm,flush=True);del m,ck;gc.collect();torch.cuda.empty_cache();continue
   files={};cached={}
   for dm in ['orig','trans']:
    for split in ['train','val','test']:
     p=E.predict(m,loader,dm,split);forwards+=1;path=dest/(dm+'_'+split+'_scores.npy');np.save(path,p);files[dm+'_'+split]=sha(path);audit.append(dict(seed=seed,arm=arm,key=dm+'_'+split,rows=len(p),scores_sha=sha(path),state_unchanged=digest(m)==before))
     if (dm,split)==('trans','val'):cached['val']=p.copy()
     del p
   assert digest(m)==before and all(p.grad is None for p in m.parameters());p=cached['val'];a=loader.arrays('trans','val');positive=p[a['trusted']&(a['y']==1)];negative=p[a['trusted']&(a['y']==0)];thresholds=dict(historical_fpr5=float(np.nextafter(np.quantile(negative,.95),np.inf)),val_recall80=float(np.quantile(positive,.2,method='lower')),val_recall90=float(np.quantile(positive,.1,method='lower')));score=T.metrics(p,'trans','val',.5)[0]['trusted']['ap'];ev=dict(seed=seed,arm=arm,source_completed_updates=200,model_updates=0,optimizer_objects=0,selection='fixedlast200',selected=dict(epoch=200,score=score),thresholds=thresholds,source_checkpoint=str((old/arm/'resume.pt').relative_to(R)),checkpoint_sha=sha(old/arm/'resume.pt'),state_digest=before,prediction_sha=files,SAT=0,EQ=0);write(dest/'EVALUATED.json',ev);print('INFERRED',seed,arm,'last200',flush=True);del m,ck,cached;gc.collect();torch.cuda.empty_cache()
  # Reuse the exact frozen evaluator,with explicit inference-only guard and correct nested root.
  text=(BASE/'analyze.py').read_text(encoding='utf-8');assert "R=Path(__file__).resolve().parents[2]" in text and "assert read(O/'TRAINING_COMPLETE.json')['actual_updates']==1000" in text;text=text.replace('R=Path(__file__).resolve().parents[2]','R=Path(__file__).resolve().parents[3]').replace("assert read(O/'TRAINING_COMPLETE.json')['actual_updates']==1000","assert read(O/'INFERENCE_COMPLETE.json')['model_updates']==0").replace('single_seed=True,updates=1000','single_seed=True,updates=0,source_updates_each=200')
  path=out/'analyze.py'
  if path.exists():assert path.read_text(encoding='utf-8')==text
  else:path.write_text(text,encoding='utf-8')
  write(out/'INFERENCE_COMPLETE.json',dict(model_updates=0,source_updates_each=200,SAT=0,EQ=0));protected[str(path.relative_to(R))]=sha(path)
 for p,h in protected.items():assert sha(R/p)==h,p
 with (O/'INFERENCE_AUDIT.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
 write(O/'SELECTED_REPRODUCTION.json',read(O/'NUMERICAL_REPRODUCTION.json'));write(O/'PROTECTED_INPUTS.json',protected);write(O/'INFERENCE_COMPLETE.json',dict(passed=True,current_invocation_forwards=forwards,successful_last200_forwards_including_reused=90,selected_control_forwards_in_separate_numerical_audit=9,source_models=15,model_updates=0,optimizer_objects=0,SAT=0,EQ=0,states_and_old_files_unchanged=True,seconds=time.perf_counter()-start));print('ALL15_FIXED200_INFERENCE_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
