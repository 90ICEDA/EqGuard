"""Fixed-checkpoint sensitivity and incidence-defined strata; no extra training."""
import run as A
import csv,json,gc,importlib.util
import numpy as np
from sklearn.metrics import roc_auc_score
O=A.O;R=A.R;torch=A.torch
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def strata():
 flags={r['certificate_id']:r['contains_mux']=='True' for r in rows(O/'validation_mux_blocks.csv')};blocks=rows(O/'evaluation_blocks.csv');result=[]
 for alignment in ['shared','viewshuffle']:
  for arm in ['Z','R','P']:
   for remap in ['9000','9001']:
    for space in ['root64','concat128','projection32']:
     rr=[r for r in blocks if r['alignment']==alignment and r['arm']==arm and r['remap']==remap and r['space']==space]
     for subset in ['has_MUX','no_MUX']:
      gg=[r for r in rr if flags[r['certificate']]==(subset=='has_MUX')]
      def stats(group):
       aa=[float(r[k]) for r in group for k in ['real0','real1']];bb=[float(r[k]) for r in group for k in ['wrong0','wrong1']]
       return dict(blocks=len(group),auc=float(roc_auc_score([1]*len(aa)+[0]*len(bb),-np.array(aa+bb))),anchor_win=float(np.mean([float(r['anchor_win']) for r in group])))
      ss=[stats([r for r in gg if r['source']==source]) for source in sorted({r['source'] for r in gg})];s=stats(gg)
      result.append(dict(alignment=alignment,arm=arm,remap=remap,space=space,subset=subset,**s,sources=len(ss),source_macro_auc=float(np.mean([r['auc'] for r in ss])),source_macro_anchor_win=float(np.mean([r['anchor_win'] for r in ss]))))
 A.table('mux_strata_summary.csv',result)
def sensitivity():
 A.E.set_inputs();cones={c['cone_id']:c for c in A.read(A.E.J/'final_cones.json')}
 scratch=O/'sensitivity_loader';scratch.mkdir(exist_ok=True);A.D.O=scratch;A.B.O=scratch
 b=A.D.PinBoundary(A.E.T.CONTRACT,cones)
 A.D.O=O;A.B.O=O
 certs=A.read(R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json');cache=np.load(O/'shared_R/val_repr_remap9000.npz');ids=list(cache['cone_ids']);reference=cache['concat128'][:,:64];x,e=A.B.graph('trans_val')
 m,head=A.D.initial();ck=torch.load(O/'shared_R/resume.pt',map_location='cuda',weights_only=False);m.load_state_dict(ck['model']);m.eval();before={k:v.clone() for k,v in m.state_dict().items()};del ck,head;result=[]
 for mode in ['true_repeat','wrong_role','pin_disabled_boundary_retained']:
  side=b.features('trans_val','viewshuffle' if mode=='wrong_role' else 'shared',9000)
  if mode=='pin_disabled_boundary_retained':
   side['pin_boundary']=torch.zeros_like(side['pin_boundary']);side['internal']=tuple(v[:0] for v in side['internal'])
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
   h=m.encode(x,e,side);u=A.B.pool(h,ids,cones).float().cpu().numpy().astype(np.float64)
  root=u[:,:64];delta=root-reference;_,metric,_=A.B.metrics('fixed_true_R',mode,9000,'root64',root,ids,cones,certs)
  result.append(dict(mode=mode,root_rms_change=float(np.sqrt(np.mean(delta*delta))),relative_to_root_std=float(np.sqrt(np.mean(delta*delta))/reference.std()),max_abs_change=float(np.abs(delta).max()),**{k:metric[k] for k in ['cross_auc','source_macro_auc','source_macro_anchor_win']}))
  np.savez_compressed(O/f'sensitivity_{mode}.npz',cone_ids=np.array(ids),root64=root);del side,h,u
 assert all(torch.equal(before[k],v) for k,v in m.state_dict().items())
 A.write('CHANNEL_SENSITIVITY.json',dict(checkpoint_sha=A.E.sha(O/'shared_R/resume.pt'),BN_and_weights_unchanged=True,optimizer_steps=0,backward_calls=0,validation_only=True,new_SAT=0,results=result,interpretation='same final trueR weights;wrong-role input only or pin-channel disabled while old shared boundary20 remains;true-repeat estimates BF16/scatter variation'))
def main():
 spec=importlib.util.spec_from_file_location('independent_check',O/'verify.py');V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V);V.main();gc.collect();strata();sensitivity()
 A.write('FINAL_ANALYSIS_COMPLETE.json',dict(verified=True,training_updates_added=0,model_forwards_added=3,SAT=0,test_reads=0,strata='frozen incidence-defined hasMUX28/noMUX40',no_model_or_BN_updates=True))
 print('FINAL_ANALYSIS_COMPLETE',flush=True)
if __name__=='__main__':main()
