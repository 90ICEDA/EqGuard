"""One fixed S_R validation repeat to calibrate BF16/scatter sensitivity, no training."""
import run as A
import numpy as np
O=A.O;torch=A.torch
def main():
 A.E.set_inputs();i=A.Interface();scratch=O/'repeat_loader';scratch.mkdir(exist_ok=True);A.D.O=scratch;A.B.O=scratch;b=A.D.PinBoundary(A.E.T.CONTRACT,i.cones)
 with np.load(O/'val_S_R_remap9000.npz') as f:ids=f['cone_ids'].tolist();reference=f['concat128'].astype(np.float64)
 x,e=A.B.graph('trans_val');m,head=A.D.initial();ck=torch.load(O/'S_R/resume.pt',map_location='cuda',weights_only=False);m.load_state_dict(ck['model']);head.load_state_dict(ck['projection']);del ck;m.eval();head.eval();before=A.state_digest(m,head);side=b.features('trans_val','shared',9000)
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):h=m.encode(x,e,side);u=A.pool(h,A.pool_spec(ids,i.cones));z=head(u)
 arr=u.float().cpu().numpy().astype(np.float64);delta=arr[:,:64]-reference[:,:64];assert A.state_digest(m,head)==before
 np.savez_compressed(O/'sensitivity_S_R_correct_repeat.npz',cone_ids=np.array(ids),concat128=arr,projection32=z.float().cpu().numpy())
 A.write('REPEAT_REFERENCE.json',dict(evaluation_forwards_added=1,optimizer_updates_added=0,SAT=0,test_reads=0,checkpoint_SHA=A.sha(O/'S_R/resume.pt'),model_BN_unchanged=True,root_RMS_change=float(np.sqrt(np.mean(delta**2))),relative_to_root_std=float(np.sqrt(np.mean(delta**2))/(reference[:,:64].std()+1e-30)),purpose='calibrate role intervention versus same-correct BF16/scatter repeat;not new validation selection'))
 print('REPEAT_REFERENCE_COMPLETE',flush=True)
if __name__=='__main__':main()
