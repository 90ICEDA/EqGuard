"""Freeze post-hoc diagnostic cohorts. No labels/scores used to choose negatives."""
from pathlib import Path
import collections,json,sys
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105';RUN=R/'_p0pilot/cec_pretrain_seed42_20261105'
sys.path.insert(0,str(J));from common import Store,read,sha,ident,SCHEMA,N
def forbidden(*a,**k):raise RuntimeError('No SAT or new structure export allowed')
N.P0.run_yosys=forbidden
def main():
 assert not (O/'PREPARED.json').exists()
 frozen={}
 for path,h in read(RUN/'PUBLISHED.json')['files'].items():assert sha(R/path)==h,path;frozen[path]=h
 store=Store();pairs=read(J/'final_pairs.json');cones={c['cone_id']:c for c in read(J/'final_cones.json')};buckets=collections.defaultdict(list)
 for p in pairs:
  if p['split']!='val':continue
  a,b=[cones[p[k]] for k in ['left_cone','right_cone']];store.raw(a['view']);store.raw(b['view']);av,bv=store.evaluators[a['view']][a['root_bit']],store.evaluators[b['view']][b['root_bit']];assert av==bv
  buckets[p['source_object'],p['context_id'],a['view'],b['view']].append((p,av))
 candidates=collections.defaultdict(dict)
 for key,rr in buckets.items():
  rr=sorted(rr,key=lambda t:ident(['validation_neg_locator_v1',t[0]['pair_id']]))
  for j,(a,amask) in enumerate(rr):
   for offset in range(1,min(len(rr),17)):
    b,bmask=rr[(j+offset)%len(rr)]
    if amask==bmask:continue
    x,y=sorted([a['pair_id'],b['pair_id']]);cid=ident(['validation_function_different_v1',x,y]);diff=amask^bmask;pattern=(diff&-diff).bit_length()-1
    candidates[key[0]][cid]=dict(certificate_id=cid,source=key[0],context_id=key[1],pair_a=a['pair_id'],pair_b=b['pair_id'],cones=[a['left_cone'],a['right_cone'],b['left_cone'],b['right_cone']],pattern=pattern,expected_outputs=[(amask>>pattern)&1]*2+[(bmask>>pattern)&1]*2)
    break
 chosen=[cc for source,vals in sorted(candidates.items()) for cid,cc in sorted(vals.items(),key=lambda kv:ident(['validation_negative_select_v1',kv[0]]))[:8]]
 # Independent scalar replay of one witness per candidate certificate.
 models={}
 for cert in chosen:
  env={tuple(x['token']):(int(x['mask_hex'],16)>>cert['pattern'])&1 for x in store.contexts[cert['context_id']]['input_masks']};outputs=[]
  for cid in cert['cones']:
   c=cones[cid];view=c['view']
   if view not in models:
    m=store.raw(view);leaf={};drivers={}
    for n,p in m['ports'].items():
     if p['direction']=='input':
      for j,b in enumerate(p['bits']):leaf[b]=('PI',n,j,0)
    for n,g in m['cells'].items():
     if 'DFF' in g['type'].upper():
      for pin in ['Q','QN']:
       for b in g['connections'].get(pin,[]):leaf[b]=('Q',n,0,int(pin=='QN'))
     else:drivers[g['connections'][SCHEMA[g['type']][0]][0]]=g
    models[view]=(leaf,drivers)
   leaf,drivers=models[view];cache={}
   def ev(b):
    if not isinstance(b,int):assert b in ['0','1'];return int(b)
    if b in cache:return cache[b]
    if b in leaf:t=leaf[b];z=env[t[:3]]^t[3]
    else:
     g=drivers[b];v=[ev(g['connections'][p][0]) for p in SCHEMA[g['type']][1]];t=g['type'];z=v[0]&v[1] if t in ['AND2X2','$and'] else v[0]|v[1] if t in ['OR2X1','$or'] else v[0]^v[1] if t in ['XOR2X1','$xor'] else 1-v[0] if t in ['INVX0','$not'] else v[1] if v[2] else v[0]
    cache[b]=z;return z
   outputs.append(ev(c['root_bit']))
  assert outputs==cert['expected_outputs'] and outputs[0]!=outputs[2];cert['independent_scalar_verified']=True;cert['selection']='existing val pair pool;fixed hash;max8/source;no labels/prediction filter;posthoc diagnostic only'
 for name,z in [('validation_negative_certificates.json',chosen),('validation_witness_contexts.json',store.contexts)]: (O/name).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8')
 schedule=read(PRE/'schedule.json');trainrows=[r for r in schedule if r['mode']=='main' and r['seed']==42];strict=[r for r in schedule if r['mode']=='strict' and r['seed']==42];inventory={r['pair_id']:r for r in read(PRE/'function_inventory.json')};tcids=sorted({p[k] for row in trainrows+strict for p in [inventory[row['pair_a']],inventory[row['pair_b']]] for k in ['left_cone','right_cone']});vcids=sorted({p[k] for p in pairs if p['split']=='val' for k in ['left_cone','right_cone']})
 plan=dict(training_updates=0,backward_calls=0,new_SAT_queries=0,seed=42,train_cones=tcids,val_cones=vcids,validation_negative_certificates=len(chosen),validation_negative_sources=len(candidates),posthoc=True,stages=['initial','pretrain50','finetune_best','finetune200'],heads=['initial_projection','trained_projection'],BN_swap=['pre_params+fine_BN','fine_params+pre_BN'],noise_modes=['eval_running','dropout_running101','dropout_running202','clean_batchBN','dropout_batchBN101','dropout_batchBN202'],no_test_forward=True,training_selection_unchanged=True,frozen=frozen,inputs=store.inputs)
 (O/'PREPARED.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in plan.items() if k not in ['frozen','inputs','train_cones','val_cones']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
