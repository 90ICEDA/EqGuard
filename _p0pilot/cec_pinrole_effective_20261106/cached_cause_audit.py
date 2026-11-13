"""Read cached histories/embeddings/certificates only; no torch, training or SAT."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
from sklearn.metrics import roc_auc_score

O=Path(__file__).resolve().parent
R=O.parents[1]
A=R/'_p0pilot/cec_cause_audit_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(name,data):
 with (A/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def main():
 A.mkdir(exist_ok=True)
 paths=list(O.glob('shared_*/history.json'))+list(O.glob('shared_*/val_repr_remap9000.npz'))
 invpath=R/'_p0pilot/cec_fair_audit_20261105/boundary_cone_inventory.csv'
 trpath=R/'_p0pilot/cec_pretrain_ready_20261105/negative_certificates.json'
 vapath=R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json'
 paths += [invpath,trpath,vapath,O/'evaluation_summary.csv']
 digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 before={str(p.relative_to(R)):digest(p) for p in paths}
 losses=[]
 for arm in ['Z','R','P']:
  h=read(O/f'shared_{arm}/history.json')
  for name,hh in [('first10',h[:10]),('last10',h[-10:])]:
   v={k:float(np.mean([x[k] for x in hh])) for k in ['eq_real','eq_permuted','different','variance','representation_std']}
   active=0 if arm=='Z' else v['eq_real' if arm=='R' else 'eq_permuted']
   losses.append(dict(arm=arm,window=name,**v,weighted_variance=.1*v['variance'],association_value_share=active/(active+v['different']+.1*v['variance'])))
 save('loss_values.csv',losses)
 inv={x['cone_id']:x for x in rows(invpath)}
 panel=[]
 for split,certs in [('train',read(trpath)),('val',read(vapath))]:
  seen=set()
  for c in certs:
   key=(c['source'],tuple(sorted(c['cones'])))
   if key in seen:continue
   seen.add(key)
   ii=[inv[k] for k in c['cones']]
   panel.append(dict(split=split,source=c['source'],certificate=c.get('certificate_id',c.get('block_id')),all_four_within3hop=all(int(x['members_outside_3hop'])==0 for x in ii),max_members=max(int(x['members']) for x in ii),has_mux=any(int(x['mux_cells']) for x in ii)))
 save('certificate_panel.csv',panel)
 coverage=[]
 for split in ['train','val']:
  for size in [8,16,32,64]:
   for shallow in [False,True]:
    rr=[x for x in panel if x['split']==split and x['max_members']<=size and (not shallow or x['all_four_within3hop'])]
    coverage.append(dict(split=split,max_members_limit=size,require_all_four_within3hop=shallow,blocks=len(rr),sources=len({x['source'] for x in rr}),mux_blocks=sum(x['has_mux'] for x in rr)))
 save('panel_coverage.csv',coverage)
 certs=read(vapath);metrics=[]
 for arm in ['Z','R','P']:
  with np.load(O/f'shared_{arm}/val_repr_remap9000.npz') as z:
   index={k:i for i,k in enumerate(z['cone_ids'].tolist())}
   spaces={'root64':z['concat128'][:,:64],'mean64':z['concat128'][:,64:],'concat128':z['concat128'],'projection32':z['projection32']}
   for space,xx in spaces.items():
    pos=[];neg=[];wins=[]
    for c in certs:
     a,b,d,e=[xx[index[k]].astype(np.float64) for k in c['cones']]
     dist=lambda v,w:float(np.sqrt(np.mean((v-w)**2)))
     pp=[dist(a,b),dist(d,e)];nn=[dist(a,e),dist(d,b)]
     pos+=pp;neg+=nn;wins.extend([float(p<n)+.5*float(p==n) for p,n in zip(pp,nn)])
    metrics.append(dict(arm=arm,space=space,blocks=len(certs),cross_auc=roc_auc_score([1]*len(pos)+[0]*len(neg),-np.array(pos+neg)),anchor_win=np.mean(wins)))
 save('readout_metrics.csv',metrics)
 # Independent recomputation must match previously published results.
 published=rows(O/'evaluation_summary.csv')
 for x in metrics:
  if x['space']=='mean64':continue
  p=next(v for v in published if v['alignment']=='shared' and v['arm']==x['arm'] and v['remap']=='9000' and v['space']==x['space'])
  assert abs(x['cross_auc']-float(p['cross_auc']))<1e-12,(x,p)
 assert all(digest(R/p)==h for p,h in before.items())
 result=dict(input_sha256=before,old_files_unchanged=True,training_updates=0,model_forwards=0,SAT=0,test_reads=0,loss_interpretation='Value shares only;not gradient contribution or optimization causality',panel_interpretation='Deduplicate exact source/four-endpoint sets;not independent Boolean-function classes;train certificate inventory is not the sampled 382-pair schedule;size thresholds exploratory, not outcome-selected')
 (A/'VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(losses=losses,coverage=coverage,metrics=metrics),ensure_ascii=False))
if __name__=='__main__':main()
