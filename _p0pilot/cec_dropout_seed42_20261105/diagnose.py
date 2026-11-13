"""Reuse old witnesses; eval-only source-balanced function separation before/after fine tuning."""
from pathlib import Path
import collections,csv,gc,json,sys
import numpy as np
from sklearn.metrics import roc_auc_score
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_mechanism_seed42_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
sys.path.insert(0,str(PRE));import engine as E
torch=E.torch

def main():
 assert (O/'ANALYSIS_COMPLETE.json').exists();E.set_inputs();plan=E.read(OLD/'PREPARED.json');cones={c['cone_id']:c for c in E.read(E.J/'final_cones.json')};cert=E.read(OLD/'validation_negative_certificates.json');pairs=E.read(E.J/'final_pairs.json');rows=[]
 ids=plan['val_cones'];ix={c:i for i,c in enumerate(ids)}
 def metrics(x,version,arm,stage,space):
  records=[]
  for s in sorted({c['source'] for c in cert}):
   same=[];different=[]
   for c in cert:
    if c['source']!=s:continue
    a,ar,b,br=[x[ix[cid]].astype(float) for cid in c['cones']];rms=lambda a,b:float(np.sqrt(np.mean((a-b)**2)))
    same.extend([rms(a,ar),rms(b,br)]);different.extend([rms(a,b),rms(ar,br)])
   records.append(dict(auc=roc_auc_score([1]*len(same)+[0]*len(different),-np.r_[same,different]),same_rms=np.mean(same),different_rms=np.mean(different)))
  source={p[k]:p['source_object'] for p in pairs if p['split']=='val' for k in ['left_cone','right_cone']};ss=[source[c] for c in ids];n=collections.Counter(ss);w=np.array([1/len(n)/n[s] for s in ss]);center=x-w@x;ev=np.maximum(np.linalg.eigvalsh(center.T@(w[:,None]*center)),0);prob=ev/ev.sum() if ev.sum()>0 else ev;rank=np.exp(-np.sum(prob[prob>0]*np.log(prob[prob>0]))) if ev.sum()>0 else 0
  rows.append(dict(dropout=version,arm=arm,stage=stage,space=space,validation_negative_sources=len(records),validation_negative_blocks=len(cert),same_vs_different_auc=float(np.mean([r['auc'] for r in records])),same_rms=float(np.mean([r['same_rms'] for r in records])),different_rms=float(np.mean([r['different_rms'] for r in records])),source_balanced_effective_rank=float(rank)))
 def project(u,h):return np.maximum(u@h['0.weight'].T+h['0.bias'],0)@h['2.weight'].T+h['2.bias']
 data=E.T.load('trans','val','A');forward=0
 for arm in ['Z','R','P']:
  pre=torch.load(O/f'runs/main/seed42/{arm}/pretrain/resume.pt',map_location='cpu',weights_only=False);head=E.Projection().cuda();head.load_state_dict(pre['projection']);head.eval()
  for stage in ['pre','best']:
   state=pre['model'] if stage=='pre' else torch.load(O/f'runs/main/seed42/{arm}/finetune/best.pt',map_location='cpu',weights_only=True)
   model=E.EncoderModel().cuda();model.load_state_dict(state);model.eval();chunks=[]
   with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
    h=model.encode(data['x'],data['edge']);forward+=1
    for start in range(0,len(ids),64):
     ci=ids[start:start+64];lens=torch.tensor([len(cones[c]['graph_rows']) for c in ci],device='cuda');flat=torch.tensor([i for c in ci for i in cones[c]['graph_rows']],device='cuda');seg=torch.repeat_interleave(torch.arange(len(ci),device='cuda'),lens);sums=torch.zeros(len(ci),64,device='cuda').index_add(0,seg,h[flat].float());roots=torch.tensor([cones[c]['root_row'] for c in ci],device='cuda');chunks.append(torch.cat([h[roots],(sums/lens[:,None]).to(h.dtype)],1).float().cpu().numpy())
   u=np.concatenate(chunks);np.save(O/f'{arm}_{stage}_val_concat128.npy',u);newhead={k:v.detach().cpu().numpy() for k,v in pre['projection'].items()};oldhead=dict(np.load(OLD/f'head_{arm}.npz'));old=np.load(OLD/f'embeddings/{arm}_{stage}/val_eval_running.npy')
   for version,arr,hp in [('0.2',old,oldhead),('0',u,newhead)]:
    for space,x in [('root64',arr[:,:64]),('concat128',arr),('projection32',project(arr,hp))]:metrics(x,version,arm,stage,space)
   del model,h;gc.collect();torch.cuda.empty_cache()
  del pre,head;print('DIAGNOSED',arm,flush=True)
 with (O/'mechanism_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 E.write(O/'MECHANISM_COMPLETE.json',dict(eval_only=True,forward_calls=forward,new_SAT=0,new_training=0,validation_witness_sha=E.sha(OLD/'validation_negative_certificates.json'),rows=rows))
if __name__=='__main__':main()
