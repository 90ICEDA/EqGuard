"""Fixed historical39d model inference on the frozen105-unit hard panel."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,importlib.util,json,sys,time,traceback
import numpy as np
from sklearn.metrics import roc_auc_score
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
H=R/'_p0pilot/cec_hard_boundary_20261106';OLD=R/'_p0pilot/cec_relative_seed42_20261106';DIAG=R/'_p0pilot/cec_relative_diagnosis_20261106'
s=importlib.util.spec_from_file_location('frozen_relative',OLD/'run.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
torch=A.torch;E=A.E;B=A.B;D=A.D
ARMS=['INIT',*A.ARMS]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):E.write(O/n,v)
def table(n,rows):
 if not rows:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def cache_read(p,ids):
 if not p.exists():return None,0
 with np.load(p) as z:
  ix={c:j for j,c in enumerate(z['cone_ids'].tolist())};overlap=len(set(ids)&set(ix))
  if overlap!=len(ids):return None,overlap
  ix=[ix[c] for c in ids];return {k:z[k][ix].copy() for k in ['concat128','projection32']},overlap
def extract(units,cones):
 E.set_inputs();scratch=O/'pin_loader';scratch.mkdir(exist_ok=True);D.O=scratch;B.O=scratch
 b=None;counts=[];nforwards=0;repeat=None
 for domain in ['train','val']:
  ids=sorted({c for u in units if u['split']==domain for c in u['cones']});x=e=side=sp=None
  for arm in ARMS:
   out=O/f'{domain}_{arm}.npz'
   prior=(DIAG/f'{domain}_{arm}_remap9000.npz') if domain=='train' or arm=='INIT' else (OLD/f'val_{arm}_remap9000.npz')
   cached,overlap=cache_read(prior,ids)
   if out.exists():
    cached,_=cache_read(out,ids);assert cached is not None;counts.append(dict(split=domain,arm=arm,cones=len(ids),prior_overlap=overlap,mode='reuse_this_round_verified_output',forward=0));continue
   if cached is not None:
    np.savez_compressed(out,cone_ids=np.array(ids),**cached);counts.append(dict(split=domain,arm=arm,cones=len(ids),prior_overlap=overlap,mode='reuse_old_full_coverage',forward=0));continue
   if b is None:b=D.PinBoundary(E.T.CONTRACT,cones)
   if x is None:
    x,e=B.graph('trans_'+domain);side=b.features('trans_'+domain,'shared',9000);sp=A.pool_spec(ids,cones)
   m,head=D.initial();ck=torch.load(OLD/'INITIAL_STATE.pt' if arm=='INIT' else OLD/arm/'resume.pt',map_location='cuda',weights_only=False)
   if arm!='INIT':assert ck['completed']==50
   m.load_state_dict(ck['model']);head.load_state_dict(ck['projection']);del ck;m.eval();head.eval()
   assert not m.training and not head.training;before=A.state_digest(m,head)
   def forward():
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):hh=m.encode(x,e,side);uu=A.pool(hh,sp);zz=head(uu)
    assert torch.isfinite(uu).all() and torch.isfinite(zz).all()
    return dict(concat128=uu.float().cpu().numpy(),projection32=zz.float().cpu().numpy())
   result=forward();nforwards+=1;np.savez_compressed(out,cone_ids=np.array(ids),**result)
   if domain=='val' and arm=='S_R':
    repeated=forward();nforwards+=1;np.savez_compressed(O/'val_S_R_repeat.npz',cone_ids=np.array(ids),**repeated)
    repeat=dict(root_rms_delta=float(np.sqrt(np.mean((result['concat128'][:,:64]-repeated['concat128'][:,:64])**2))),root_max_abs_delta=float(np.max(np.abs(result['concat128'][:,:64]-repeated['concat128'][:,:64]))))
   assert A.state_digest(m,head)==before
   counts.append(dict(split=domain,arm=arm,cones=len(ids),prior_overlap=overlap,mode='frozen_full_graph_forward',forward=1,))
   print('EXTRACTED',domain,arm,len(ids),flush=True);del m,head;gc.collect();torch.cuda.empty_cache()
  del x,e,side,sp;gc.collect();torch.cuda.empty_cache()
 table('inference_audit.csv',counts)
 write('EXTRACTION_COMPLETE.json',dict(new_model_forwards=nforwards,repeat=repeat,weights_and_BN_unchanged=True,optimizer_updates=0,backwards=0,SAT=0,test_reads=0,interface_used='historical fullgraph39v3+original pin/boundary adapters;new25d schema NOT connected',sampling='all105 frozen units,no score-based selection'))

def metric_details(units,ids,x,arm,space,split):
 ix={c:j for j,c in enumerate(ids)};details=[]
 for u in units:
  n=u['functions'];vv=np.asarray([x[ix[c]] for c in u['cones']],dtype=np.float64)
  for fun in range(n):
   for side in [0,1]:
    a=2*fun+side;cc=[2*j+1-side for j in range(n)];dist=np.sqrt(np.mean((vv[a]-vv[cc])**2,1));real=float(dist[fun]);bad=[float(dist[j]) for j in range(n) if j!=fun];mi=float(dist.min());top=float(real==mi)/int(np.sum(dist==mi))
    for j in range(n):
     if j==fun:continue
     wrong=float(dist[j]);details.append(dict(split=split,arm=arm,space=space,unit_id=u['unit_id'],source=u['source'],tier=u['tier'],functions=n,has_mux=u['has_mux'],shallow_small=u['shallow_small'],anchor_function=fun,anchor_side=side,wrong_function=j,true_rms=real,wrong_rms=wrong,margin=wrong-real,win=float(real<wrong)+.5*float(real==wrong),top1=top,within_1e6=float(abs(wrong-real)<=1e-6),prior_pair_count=u['prior_supervised_pair_count']))
 return details
def summarize(rr):
 per_unit=collections.defaultdict(list)
 for r in rr:per_unit[r['unit_id']].append(r)
 uu=[dict(source=z[0]['source'],win=float(np.mean([r['win'] for r in z])),top1=float(np.mean([r['top1'] for r in z])),margin=float(np.mean([r['margin'] for r in z])),near=float(np.mean([r['within_1e6'] for r in z]))) for z in per_unit.values()]
 sources=sorted({r['source'] for r in rr});stats=[]
 for source in sources:
  sr=[r for r in rr if r['source']==source];su=[u for u in uu if u['source']==source];cnt=collections.Counter(r['unit_id'] for r in sr)
  w=np.array([1/cnt[r['unit_id']] for r in sr]);a=np.array([r['true_rms'] for r in sr]);b=np.array([r['wrong_rms'] for r in sr]);auc=roc_auc_score([1]*len(a)+[0]*len(b),-np.r_[a,b],sample_weight=np.r_[w,w])
  stats.append(dict(source=source,units=len(su),queries=len(sr),pairwise_win=float(np.mean([u['win'] for u in su])),function_auc=float(auc),top1=float(np.mean([u['top1'] for u in su])),mean_margin=float(np.mean([u['margin'] for u in su])),near_tie_rate=float(np.mean([u['near'] for u in su]))))
 out=dict(units=len(uu),sources=len(sources),pairwise_win=float(np.mean([r['pairwise_win'] for r in stats])),function_auc=float(np.mean([r['function_auc'] for r in stats])),top1=float(np.mean([r['top1'] for r in stats])),mean_margin=float(np.mean([r['mean_margin'] for r in stats])),near_tie_rate=float(np.mean([r['near_tie_rate'] for r in stats])))
 return out,stats
def analyze(units):
 metrics=[];source=[];details=[];baseline=[]
 for split in ['train','val']:
  panel=[u for u in units if u['split']==split]
  for arm in ARMS:
   z=np.load(O/f'{split}_{arm}.npz');ids=z['cone_ids'].tolist();spaces={'root64':z['concat128'][:,:64],'mean64':z['concat128'][:,64:],'concat128':z['concat128'],'projection32':z['projection32']}
   for name,x in spaces.items():
    rr=metric_details(panel,ids,x,arm,name,split);details+=rr
    conditions={'all_pairwise':lambda r:True,'triples_only':lambda r:r['functions']==3,'pairs_only':lambda r:r['functions']==2,'T3_same_boundary':lambda r:r['tier']=='T3_same_boundary','T2_extended':lambda r:r['tier']=='T2_extended_profile','MUX':lambda r:r['has_mux'],'nonMUX':lambda r:not r['has_mux'],'shallow_small':lambda r:r['shallow_small'],'prior_pairs_zero':lambda r:r['prior_pair_count']==0,'prior_pairs_nonzero':lambda r:r['prior_pair_count']>0}
    for group,fn in conditions.items():
     ss=[r for r in rr if fn(r)]
     if not ss:continue
     summary,by=summarize(ss);metrics.append(dict(split=split,arm=arm,space=name,group=group,**summary));source.extend(dict(split=split,arm=arm,space=name,group=group,**r) for r in by)
  # Only the exact matched keys are a guaranteed tie, not every graph statistic.
  baseline.append(dict(split=split,units=len(panel),sources=len({u['source'] for u in panel}),base_and_selected_tier_matched_distance_win=.5,matched_key_function_auc=.5,triple_matched_key_top1=1/3))
 table('function_metrics.csv',metrics);table('metrics_by_source.csv',source);table('query_details.csv',details);table('matched_key_baseline.csv',baseline)
 # Independent replay of current S_R forward numerical variation on same inputs.
 if (O/'val_S_R_repeat.npz').exists():
  z=np.load(O/'val_S_R_repeat.npz');rr=metric_details([u for u in units if u['split']=='val'],z['cone_ids'].tolist(),z['concat128'][:,:64],'S_R_repeat','root64','val');m,_=summarize(rr);write('REPEAT_METRICS.json',m)
 write('ANALYSIS_COMPLETE.json',dict(passed=True,units=105,splits={'train':73,'val':32},query_design='eachfunction x bothdirections x eachwrong;equal unit then source;reciprocal queries NOT independent samples',primary_space='root64',primary_group='triples_only',chance=dict(pairwise=.5,AUC=.5,triplet_top1=1/3),panel_status='posthoc diagnostic,not new confirmatory validation;val2sources1host',new_training=0,new_SAT=0,test_reads=0))
 print('ANALYSIS_COMPLETE',flush=True)
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert read(O/'INTERFACE_VERIFIED.json')['passed']
 protected=read(O/'INTERFACE_VERIFIED.json')['protected_files']
 for p,h in protected.items():assert sha(R/p)==h,p
 units=read(H/'hard_panel.json');cones={c['cone_id']:c for c in read(A.E.J/'final_cones.json')}
 # Freeze these script versions before outputs; no optimizer constructed anywhere in this script.
 write('EVALUATION_CONTRACT.json',dict(panel_sha=sha(H/'hard_panel.json'),validation_sha=sha(O/'INTERFACE_VERIFIED.json'),script_sha=sha(Path(__file__)),arms=ARMS,seed=42,checkpoints='original initialization and fixedlast50,no new checkpoint selection',primary='root64,three-function subset,allfunction/bidirectional source-macro pairwise win;AUC andtop1secondary',role_boundary='unchanged original shared feature loader,tag9000',no25d_to39d_conversion=True,training=0,SAT=0,test_reads=0))
 extract(units,cones);analyze(units)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('MODELS_UNCHANGED.json',dict(passed=True,files=len(protected),all_frozen_SHA_unchanged=True))
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'evaluation_failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
