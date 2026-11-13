"""Same fixed shared-R checkpoint: side-channel sensitivity, no optimization."""
import run as A
import numpy as np,json,gc
def main():
 A.E.set_inputs();cones={c['cone_id']:c for c in A.read(A.E.J/'final_cones.json')};b=A.Boundary(A.E.T.CONTRACT,cones)
 certs=A.read(A.R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json');saved=np.load(A.O/'shared_R/val_repr_remap9000.npz');ids=list(saved['cone_ids']);reference=saved['concat128'][:,:64];x,e=A.graph('trans_val')
 m,head=A.initial();ck=A.torch.load(A.O/'shared_R/resume.pt',map_location='cuda',weights_only=False);m.load_state_dict(ck['model']);m.eval();before={k:v.clone() for k,v in m.state_dict().items()};del ck,head
 result=[]
 for mode in ['shared','viewshuffle','disabled']:
  side=None if mode=='disabled' else b.features('trans_val',mode,9000)
  with A.torch.inference_mode(),A.torch.autocast('cuda',dtype=A.torch.bfloat16):
   h=m.encode(x,e,side);u=A.pool(h,ids,cones).float().cpu().numpy().astype(np.float64)
  root=u[:,:64];d=root-reference
  _,metric,_=A.metrics('same_checkpoint',mode,9000,'root64',root,ids,cones,certs)
  result.append(dict(mode=mode,root_rms_change=float(np.sqrt(np.mean(d*d))),relative_to_root_std=float(np.sqrt(np.mean(d*d))/reference.std()),max_abs_change=float(np.abs(d).max()),**{k:metric[k] for k in ['cross_auc','source_macro_auc','source_macro_anchor_win']}))
  np.savez_compressed(A.O/f'shared_R_sensitivity_{mode}.npz',cone_ids=np.array(ids),root64=root);del h,u,side
 assert all(A.torch.equal(before[k],v) for k,v in m.state_dict().items())
 A.write('CHANNEL_SENSITIVITY.json',dict(checkpoint_sha=A.E.sha(A.O/'shared_R/resume.pt'),validation_only=True,optimizer_steps=0,backward_calls=0,BN_and_weights_unchanged=True,results=result,scope='fixed sharedR checkpoint,posthoc diagnostic;not additional trained controls;baseline GPU BF16/scatter repeat variation measured by shared repeat'))
 print(json.dumps(result))
if __name__=='__main__':main()
