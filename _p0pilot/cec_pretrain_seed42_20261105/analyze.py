"""Evaluate frozen checkpoints after all three arms; validation thresholds only."""
from pathlib import Path
import csv,collections,gc,importlib.util,json,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_pretrain_ready_20261105';J=R/'_p0pilot/cec_joint_expand_20261105'
sys.path.insert(0,str(PRE));import engine as E
torch=E.torch
def table(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def aggregate_pair_rows(rr,group_keys,metrics):
 out=[];keys=sorted({tuple(r[k] for k in group_keys) for r in rr})
 for key in keys:
  cc=[r for r in rr if all(r[k]==v for k,v in zip(group_keys,key))];sources=sorted({r['source'] for r in cc});row=dict(zip(group_keys,key));row.update(sources=len(sources),pairs=len(cc))
  for metric in metrics:
   per=[]
   for source in sources:
    ss=[r for r in cc if r['source']==source];weights=np.asarray([r['weight'] for r in ss]);weights/=weights.sum();per.append(float(np.dot(weights,[r[metric] for r in ss])))
   row[metric]=float(np.mean(per))
  out.append(row)
 return out
def embed_checkpoint(arm,split,cids):
 folder=PRE/'runs/main/seed42'/arm/'pretrain';saved=torch.load(folder/'resume.pt',map_location='cuda',weights_only=False);assert saved['completed']==50;model=E.EncoderModel().cuda();model.load_state_dict(saved['model']);head=E.Projection().cuda();head.load_state_dict(saved['projection']);model.eval();head.eval();data=E.T.load('trans',split,'A');cones={c['cone_id']:c for c in E.read(J/'final_cones.json')};result={}
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
  hidden=model.encode(data['x'],data['edge'])
  for start in range(0,len(cids),64):
   ids=cids[start:start+64];lengths=torch.tensor([len(cones[c]['graph_rows']) for c in ids],device='cuda');members=torch.tensor([i for c in ids for i in cones[c]['graph_rows']],device='cuda');segments=torch.repeat_interleave(torch.arange(len(ids),device='cuda'),lengths);sums=torch.zeros((len(ids),64),device='cuda').index_add(0,segments,hidden[members].float());means=(sums/lengths[:,None]).to(hidden.dtype);root=torch.tensor([cones[c]['root_row'] for c in ids],device='cuda');zz=head(torch.cat([hidden[root],means],1)).float().cpu().numpy();assert np.isfinite(zz).all()
   result.update({c:z for c,z in zip(ids,zz)})
 del saved,model,head,data,hidden;gc.collect();torch.cuda.empty_cache();return result
def main():
 if (O/'ANALYSIS_COMPLETE.json').exists():print('REUSE COMPLETED ANALYSIS');return
 assert E.read(O/'TRAINING_COMPLETE.json')['total_finetune_updates']==600;E.set_inputs();runs=PRE/'runs/main/seed42';scores_dir=O/'scores';scores_dir.mkdir(exist_ok=True);global_rows=[];pair_rows=[];functional=[];train_functional=[];histories=[];bindings={};pairs=E.read(J/'final_pairs.json');cones={c['cone_id']:c for c in E.read(J/'final_cones.json')};weights={r['pair_id']:float(r['weight']) for r in csv.DictReader((J/'weights.csv').open(encoding='utf-8-sig'))};sched=[r for r in E.read(PRE/'schedule.json') if r['mode']=='main' and r['seed']==42];inventory={r['pair_id']:r for r in E.read(PRE/'function_inventory.json')}
 for arm in ['Z','R','P']:
  fin=runs/arm/'finetune';complete=E.read(fin/'COMPLETE.json');assert complete['updates']==200 and E.sha(fin/'best.pt')==complete['checkpoint_sha'];pre=E.read(runs/arm/'pretrain/COMPLETE.json');assert pre['updates']==50 and pre['encoder_sha']==E.sha(runs/arm/'pretrain/encoder.pt');bindings[arm]=dict(finetune=complete,pretrain=pre)
  prehist=E.read(runs/arm/'pretrain/history.json');finehist=E.read(fin/'history.json');assert len(prehist)==50 and len(finehist)==200 and [r['update'] for r in prehist]==list(range(1,51)) and [r['update'] for r in finehist]==list(range(1,201));histories.append(dict(arm=arm,selected_update=complete['best']['epoch'],pretrain_last=prehist[-1],pretrain_std_min=min(r['representation_std'] for r in prehist),pretrain_std_max=max(r['representation_std'] for r in prehist)))
  model=E.EncoderModel().cuda();model.load_state_dict(torch.load(fin/'best.pt',map_location='cuda',weights_only=True));model.eval();all_scores={}
  for split in ['val','train','test']:
   path=scores_dir/f'{arm}_{split}.npy';bind=scores_dir/f'{arm}_{split}.json'
   if path.exists():
    b=E.read(bind);assert b['checkpoint_sha']==complete['checkpoint_sha'] and E.sha(path)==b['score_sha'];pred=np.load(path,mmap_mode='r')
   else:
    pred=np.load(fin/'selected_val_scores.npy') if split=='val' else E.predict(model,'trans',split);np.save(path,pred);E.write(bind,dict(checkpoint_sha=complete['checkpoint_sha'],score_sha=E.sha(path),split=split,arm=arm))
   assert np.isfinite(pred).all();all_scores[split]=pred
  del model;gc.collect();torch.cuda.empty_cache()
  labels=E.T.arrays('trans','val');vp=all_scores['val'];negative=vp[labels['trusted']&(labels['y']==0)];positive=vp[labels['trusted']&(labels['y']==1)];thresholds=dict(historical_fpr5=float(np.nextafter(np.quantile(negative,.95),np.inf)),val_recall80=float(np.quantile(positive,.2,method='lower')),val_recall90=float(np.quantile(positive,.1,method='lower')))
  for split in ['val','test']:
   for operation,threshold in thresholds.items():
    metrics=E.T.metrics(all_scores[split],'trans',split,threshold)[0]['trusted'];global_rows.append(dict(arm=arm,split=split,operation=operation,threshold=threshold,selected_update=complete['best']['epoch'],**metrics))
  for p in pairs:
   if not p['detection_stability_diagnostic_eligible']:continue
   split=p['split'];a,b=p['root_endpoints'];pa,pb=float(all_scores[split][a['row']]),float(all_scores[split][b['row']]);label=a['label'];threshold=thresholds['val_recall80'];qa,qb=pa>=threshold,pb>=threshold
   pair_rows.append(dict(arm=arm,split=split,source=p['source_object'],pair_id=p['pair_id'],label=label,weight=weights[p['pair_id']],probability_a=pa,probability_b=pb,MAE=abs(pa-pb),flip=int(qa!=qb),both_correct=int(qa==label and qb==label),both_wrong=int(qa!=label and qb!=label)))
  print('DETECTION_EVALUATED',arm,thresholds,flush=True)
  # Representation evaluation is a fixed-last50 checkpoint, never used for selection.
  valpairs=[p for p in pairs if p['split']=='val'];valcids=sorted({p[k] for p in valpairs for k in ['left_cone','right_cone']});vz=embed_checkpoint(arm,'val',valcids)
  source_scales={}
  for source in sorted({p['source_object'] for p in valpairs}):
   ids={p[k] for p in valpairs if p['source_object']==source for k in ['left_cone','right_cone']};values=np.stack([vz[c] for c in ids]);source_scales[source]=float(np.sqrt(values.var(0).mean()))
  for p in valpairs:
   a,b=vz[p['left_cone']],vz[p['right_cone']];label=p['root_endpoints'][0]['label'] if p['detection_stability_diagnostic_eligible'] else -1;rms=float(np.sqrt(np.mean((a-b)**2)));scale=source_scales[p['source_object']];functional.append(dict(arm=arm,split='val',source=p['source_object'],pair_id=p['pair_id'],label=label,weight=weights[p['pair_id']],rms=rms,source_std=scale,normalized_rms=rms/max(scale,1e-8),source_collapsed=scale<1e-6))
  matrix=np.stack([vz[c] for c in valcids]);center=matrix-matrix.mean(0);s=np.linalg.svd(center,compute_uv=False);energy=s*s;prob=energy/energy.sum();histories[-1]['validation_projection']=dict(std_mean=float(matrix.std(0).mean()),effective_rank=float(np.exp(-(prob[prob>0]*np.log(prob[prob>0])).sum())),unique_cones=len(matrix),source_scales=source_scales,source_collapsed_count=sum(s<1e-6 for s in source_scales.values()))
  traincids=sorted({p[k] for row in sched for p in [inventory[row['pair_a']],inventory[row['pair_b']]] for k in ['left_cone','right_cone']});tz=embed_checkpoint(arm,'train',traincids)
  for row in sched:
   a,b=inventory[row['pair_a']],inventory[row['pair_b']];la,ra,lb,rb=[tz[c] for c in [a['left_cone'],a['right_cone'],b['left_cone'],b['right_cone']]];rms=lambda x,y:float(np.sqrt(np.mean((x-y)**2)))
   train_functional.append(dict(arm=arm,source=row['source'],block_id=row['block_id'],update=row['update'],real_rms=(rms(la,ra)+rms(lb,rb))/2,permuted_rms=(rms(la,rb)+rms(lb,ra))/2,negative_rms=(rms(la,lb)+rms(ra,rb))/2))
  print('FUNCTIONAL_EVALUATED',arm,histories[-1]['validation_projection'],flush=True)
 expanded=[]
 for row in pair_rows:
  expanded.append(dict(row,stratum='all'));expanded.append(dict(row,stratum=str(row['label'])))
 paired=aggregate_pair_rows(expanded,['arm','split','stratum'],['MAE','flip','both_correct','both_wrong'])
 ff=[]
 for row in functional:ff.append(dict(row,stratum='all'));ff.append(dict(row,stratum=str(row['label'])))
 function_summary=aggregate_pair_rows(ff,['arm','split','stratum'],['rms','normalized_rms','source_std'])
 # Negative schedule exposure already gives every source50 slots; aggregate by source.
 train_summary=[]
 for arm in ['Z','R','P']:
  rr=[r for r in train_functional if r['arm']==arm];source_metrics=[]
  for src in sorted({r['source'] for r in rr}):
   ss=[r for r in rr if r['source']==src];source_metrics.append({k:float(np.mean([r[k] for r in ss])) for k in ['real_rms','permuted_rms','negative_rms']})
  train_summary.append(dict(arm=arm,**{k:float(np.mean([r[k] for r in source_metrics])) for k in ['real_rms','permuted_rms','negative_rms']}))
 table('detection_metrics.csv',global_rows);table('pair_predictions.csv',pair_rows);table('pair_diagnostic_summary.csv',paired);table('functional_val_pairs.csv',functional);table('functional_val_summary.csv',function_summary);table('functional_train_blocks.csv',train_functional);table('functional_train_summary.csv',train_summary)
 E.write(O/'ANALYSIS_COMPLETE.json',dict(seed=42,arms=['Z','R','P'],updates_per_arm=dict(pretrain=50,finetune=200),total_updates=750,new_SAT_queries=0,detection=global_rows,paired=paired,functional_validation=function_summary,functional_train=train_summary,histories=histories,bindings=bindings,test_detection_evaluated=True,test_paired_metrics=None,limits=['single seed exploratory','main P changes pair joint structure','train functional negatives are in-sample','validation functional negatives not constructed;paired similarity alone does not prove general function discrimination','test previously inspected and lacks certified pairs']))
 print('ANALYSIS_COMPLETE',flush=True)
if __name__=='__main__':main()
