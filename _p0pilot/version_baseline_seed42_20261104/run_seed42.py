"""Single-factor v2/v3 H baseline: reuse v2 seed42, train only v3 seed42 for 200 updates."""
from pathlib import Path
import json,hashlib,shutil,importlib.util,datetime
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;B=R/'_p0pilot/control_fair200_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 O.mkdir(exist_ok=True);assert read(V/'PREFLIGHT_COMPLETE.json')['all_six_splits_verified'];old=read(B/'seed42/H/EVALUATED.json');cfg=read(B/'seed42/H/config.json');binding=read(B/'seed42/H/binding.json');assert cfg['seed']==42 and cfg['updates']==200 and old['init_sha']==sha(B/'init_s42.pt');assert old['checkpoint_sha']==sha(B/'seed42/H/best.pt')
 for name in ['manifest.json','orig_base_mask.npy','trans_base_mask.npy','orig_C_slots.npy','orig_H_slots.npy','trans_C_slots.npy','trans_H_slots.npy','init_s42.pt']:
  target=O/name
  if target.exists():assert sha(target)==sha(B/name),name
  else:shutil.copyfile(B/name,target)
 # Frozen engine training/evaluation function bodies are reused; only metadata names and explicit feature binding change.
 source=(B/'run.py').read_text(encoding='utf-8');source=source.split('def main():')[0]
 changes={"architecture='dual_mix_post_cat 39v2 split29 hidden64 2+2+post1'":"architecture='dual_mix_post_cat 39v3 split29 hidden64 2+2+post1'","normalization='original frozen round32'":"normalization='v3 train-only column30 refit; other38 frozen'","seed=seed,arm=arm)":"seed=seed,arm=arm,feature_contract_sha=sha(O.parent/'control_boundary_v3_20261104/input_contract.json'),normalization_sha=sha(O.parent/'control_boundary_v3_20261104/normalization.npz'))"}
 for a,b in changes.items():assert source.count(a)==1,(a,source.count(a));source=source.replace(a,b)
 path=O/'frozen_engine_v3.py'
 if path.exists():assert path.read_text(encoding='utf-8')==source
 else:path.write_text(source,encoding='utf-8')
 spec=importlib.util.spec_from_file_location('seed42_v3_engine',path);engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine);T=engine.T;np=engine.np;torch=engine.torch
 assert 'ginvenv_gpu' in engine.sys.executable and torch.cuda.is_available();assert T.MASK_MODE=='old' and T.ENCODING=='39' and not T.EXTRA and T.EQ==0
 for file,key in [(R/'_p0pilot/control_best200_20261104/evaluate.py','model_source_sha'),(R/'_p0pilot/p2b_main_20261031/train_ab.py','loader_sha'),(R/'train_test2.2.py','loss_source_sha')]:assert sha(file)==binding[key],file
 c=read(V/'input_contract.json');parent=T.CONTRACT;oldnorm=T.NORM;newnorm=np.load(V/'normalization.npz');checks=[]
 for key,q in c['shared_inputs'].items():
  p=parent['shared_inputs'][key];assert q['nodes']==p['nodes'] and q['edges']==p['edges'] and q['views']==p['views']
  for name in ['edge_index','edge_roles','y','trusted','physical']:assert sha(R/q['folder']/(name+'.npy'))==sha(R/p['folder']/(name+'.npy'))
  new=np.load(R/q['folder']/'x39.npy',mmap_mode='r');oldx=np.load(R/p['folder']/'x39.npy',mmap_mode='r');assert np.array_equal(new[:,:30],oldx[:,:30]) and np.array_equal(new[:,31:],oldx[:,31:]);checks.append(dict(key=key,same_graph_labels_and_order=True,only_column30_changed=True))
 assert np.array_equal(np.delete(oldnorm['mean'],30),np.delete(newnorm['mean'],30)) and np.array_equal(np.delete(oldnorm['std'],30),np.delete(newnorm['std'],30))
 manifest=read(O/'manifest.json')
 for p,h in manifest['files'].items():assert sha(O/p)==h,p
 # Actual historical GPU loader retained: only input folders and the one-column normalization are overridden.
 T.CONTRACT=c;T.NORM=newnorm
 contract=dict(seed=42,arm='H',new_runs=1,updates=200,SAT=False,region_weights_changed=False,training_pool_changed=False,initialization_sha=sha(O/'init_s42.pt'),v2_result=str(B/'seed42/H/EVALUATED.json'),v2_result_sha=sha(B/'seed42/H/EVALUATED.json'),v2_checkpoint_sha=old['checkpoint_sha'],engine_parent_sha=sha(B/'run.py'),engine_sha=sha(path),engine_metadata_changes=changes,feature_contract_sha=sha(V/'input_contract.json'),normalization_sha=sha(V/'normalization.npz'),checks=checks,validation_selection='same trusted injection-view mean AP every5',python=engine.sys.executable,cuda=torch.cuda.get_device_name())
 write(O/'EXPERIMENT_CONTRACT.json',contract)
 result=engine.train(42,'H',manifest);assert result['init_sha']==old['init_sha'];write(O/'TRAINING_COMPLETE.json',dict(seed=42,new_runs=1,new_updates=200,SAT=0,v2_reused=True,v3=result,time=datetime.datetime.now().astimezone().isoformat()))
 print('V3 seed42 finished',result['selected'],flush=True)
if __name__=='__main__':main()
