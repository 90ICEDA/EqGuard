"""Frozen recoding/transfer diagnosis; no optimizer or SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,importlib.util,json,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
OLD=R/'_p0pilot/cec_repaired_zrp_seed42_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106';P=R/'_p0pilot/cec_boundary_panel_expand_20261107'
sys.path.insert(0,str(PRE));import model_interface as M
sys.path.insert(0,str(P));from panel_loader import PanelLoader
torch=M.torch
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=module('retained_metrics',OLD/'analyze.py');Q=module('retained_query_metrics',R/'_p0pilot/cec_freeq_encoding_audit_20261107/cache_analysis.py')
def read(p):return M.read(p)
def sha(p):return M.sha(p)
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if rr:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert not (O/'COMPLETE.json').exists();assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert read(OLD/'VERIFIED.json')['passed']
 protected=dict(read(OLD/'EXECUTION_CONTRACT.json')['protected_files'])
 for n,h in read(OLD/'OUTPUT_MANIFEST.json').items():assert sha(OLD/n)==h,n;protected[str((OLD/n).relative_to(R))]=h
 for p in [OLD/'VERIFIED.json',OLD/'PUBLISHED.json',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 write('AUDIT_CONTRACT.json',dict(scope='posthoc frozen diagnostics,not new primary or independent seeds',reuse_tags=[9000,9001],extra_tags=[9002,9003,9004,9005],extra_scope='all4frozen states,train7/val73,same panels;report every tag',hypotheses='code margin fluctuations vs R-P change;within source and flow MUX;training support and per-source transfer;no causal host-isolation claim',training=0,SAT=0,finetune=0,test_reads=0,protected_files=protected))
 torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 pp=read(OLD/'EVALUATION_PANELS.json');panels={'train':pp['train_frozen_pool'],'val':pp['val_boundary_all']};loader=PanelLoader();states=['INIT','Z','R','P'];forwards=0;start=time.perf_counter();emb={}
 for domain,uu in panels.items():
  for tag in [9000,9001]:
   for arm in states:
    with np.load(OLD/f'{domain}_{arm}_tag{tag}.npz') as z:emb[domain,arm,tag]=(z['cone_ids'].tolist(),z['root64'].copy())
 for tag in [9002,9003,9004,9005]:
  for arm in states:
   model=M.fresh('cuda');ck=torch.load(OLD/('INITIAL_STATE.pt' if arm=='INIT' else arm+'/resume.pt'),map_location='cuda',weights_only=False);model.load_state_dict(ck['model']);model.eval();before=M.state_digest(model)
   for domain,uu in panels.items():
    ids=sorted({c for u in uu for c in u['cones']});chunks=[]
    for off in range(0,len(ids),48):
     arrays=loader.arrays(ids[off:off+48],tag);g=M.pack(arrays,'cuda')
     with torch.inference_mode():z,audit=model.encode(g)
     assert torch.isfinite(z).all() and audit['consumed_nodes']==g['nodes'] and audit['consumed_pin_edges']==g['edges'];chunks.append(z.cpu().numpy());forwards+=1
     del g,z
    x=np.concatenate(chunks);emb[domain,arm,tag]=(ids,x);np.savez_compressed(O/f'{domain}_{arm}_tag{tag}.npz',cone_ids=np.array(ids),root64=x)
   assert M.state_digest(model)==before;del model,ck;gc.collect();torch.cuda.empty_cache()
  print('FROZEN_TAG_COMPLETE',tag,flush=True)
 # Every arm/domain/tag metric and query is retained; unit weights avoid 3candidate dominance.
 summary=[];unitrows=[];queries={};sourcegroups=[]
 for domain,uu in panels.items():
  for tag in range(9000,9006):
   for arm in states:
    ids,x=emb[domain,arm,tag];rr=A.unit_records(uu,ids,x);q=Q.query_records(uu,ids,x);queries[domain,arm,tag]={Q.qkey(r):r for r in q}
    for r in rr:r['flow']=next(u['flow'] for u in uu if u['unit_id']==r['unit_id'])
    groups={'all':rr}
    for source in sorted({r['source'] for r in rr}):
     for mux in [None,False,True]:
      ss=[r for r in rr if r['source']==source and (mux is None or r['has_mux']==mux)]
      if ss:groups[source+('/MUX' if mux else '/nonMUX' if mux is False else '/all')]=ss
    for flow in sorted({r['flow'] for r in rr}):groups['flow/'+flow]=[r for r in rr if r['flow']==flow]
    for mux in [False,True]:
     ss=[r for r in rr if r['has_mux']==mux]
     if ss:groups['MUX' if mux else 'nonMUX']=ss
    for group,rs in groups.items():
     sm,_,_=A.stats(rs);summary.append(dict(domain=domain,tag=tag,arm=arm,group=group,**sm))
    for r in rr:unitrows.append(dict(domain=domain,tag=tag,arm=arm,**{k:v for k,v in r.items() if k not in ['real_distances','wrong_distances']}))
 table('six_code_metrics.csv',summary);table('unit_metrics.csv',unitrows)
 sensitivity=[];contrasts=[];scale=[]
 for domain,uu in panels.items():
  for arm in states:
   a,b=queries[domain,arm,9000],queries[domain,arm,9001];keys=list(a);w=np.array([a[k]['weight'] for k in keys]);delta=np.array([b[k]['margin']-a[k]['margin'] for k in keys]);flip=np.array([a[k]['win']!=b[k]['win'] for k in keys]);sensitivity.append(dict(domain=domain,arm=arm,directional_comparisons=len(keys),weighted_flip_rate=float(w@flip),margin_shift_RMS=float(np.sqrt(w@(delta**2)))))
  for source in sorted({u['source'] for u in uu}):
   for mux in [None,False,True]:
    us=[u for u in uu if u['source']==source and (mux is None or u['has_mux']==mux)]
    if not us:continue
    ids={u['unit_id'] for u in us}
    def wins(arm,tag):return float(np.mean([r['win'] for r in unitrows if r['domain']==domain and r['arm']==arm and r['tag']==tag and r['unit_id'] in ids]))
    contrasts.append(dict(domain=domain,source=source,mux='all' if mux is None else str(mux),units=len(us),R0=wins('R',9000),R1=wins('R',9001),P0=wins('P',9000),P1=wins('P',9001),RminusP0=wins('R',9000)-wins('P',9000),RminusP1=wins('R',9001)-wins('P',9001),unit_macro_gap_shift_contribution=(wins('R',9001)-wins('P',9001)-wins('R',9000)+wins('P',9000))*len(us)/len(uu)))
  keys=list(queries[domain,'R',9000]);q0=queries[domain,'R',9000];w=np.array([q0[k]['weight'] for k in keys]);code=np.array([queries[domain,'R',9001][k]['margin']-q0[k]['margin'] for k in keys]);model=np.array([q0[k]['margin']-queries[domain,'P',9000][k]['margin'] for k in keys]);den=float(np.sqrt(w@(model**2)));scale.append(dict(domain=domain,R_code_margin_shift_RMS=float(np.sqrt(w@(code**2))),RminusP_margin_RMS=den,ratio=float(np.sqrt(w@(code**2)))/den))
 table('encoding_sensitivity.csv',sensitivity);table('source_MUX_gap_decomposition.csv',contrasts);table('code_vs_training_effect_scale.csv',scale)
 # Actual cone characteristics; support comparisons describe confounding,not causation.
 features=[];support=[]
 for domain,uu in panels.items():
  for u in uu:
   gs=[loader.graphs[c] for c in u['cones']];gate=[sum(o>=4 for o in g['op']) for g in gs];depth=[max(g['level']) for g in gs];boundary=[sum(o<2 for o in g['op']) for g in gs];qcount=[sum(o==1 for o in g['op']) for g in gs];mux=[sum(o==8 for o in g['op']) for g in gs];side=[sum(mux[side::2]) for side in [0,1]]
   features.append(dict(domain=domain,unit_id=u['unit_id'],source=u['source'],flow=u['flow'],functions=u['functions'],has_mux=any(mux),mux_sides=sum(v>0 for v in side),max_gates=max(gate),max_depth=max(depth),max_boundary=max(boundary),Q_fraction=float(sum(qcount)/max(sum(boundary),1)),max_mux=max(mux),gate_asymmetry=float(np.mean([abs(gate[i]-gate[i+1])/max(gate[i],gate[i+1],1) for i in range(0,len(gs),2)]))))
  for source in sorted({u['source'] for u in uu}):
   us=[u for u in uu if u['source']==source];fs=[r for r in features if r['domain']==domain and r['source']==source];support.append(dict(domain=domain,source=source,units=len(us),function_classes=len({(u['context_id'],s) for u in us for s in u['function_signatures']}),flows=';'.join(sorted({u['flow'] for u in us})),MUX_units=sum(r['has_mux'] for r in fs),MUX_one_side=sum(r['mux_sides']==1 for r in fs),gate_median=float(np.median([r['max_gates'] for r in fs])),depth_median=float(np.median([r['max_depth'] for r in fs])),boundary_median=float(np.median([r['max_boundary'] for r in fs]))))
 table('unit_support_features.csv',features);table('source_support.csv',support)
 # Compare matched source+flow MUX/nonMUX,never pool with easy injalpha source.
 matched=[]
 for tag in range(9000,9006):
  for arm in states:
   rr=[r for r in unitrows if r['domain']=='val' and r['tag']==tag and r['arm']==arm]
   for source,flow in sorted({(r['source'],r['flow']) for r in rr}):
    for mux in [False,True]:
     ss=[r for r in rr if r['source']==source and r['flow']==flow and r['has_mux']==mux]
     if ss:matched.append(dict(tag=tag,arm=arm,source=source,flow=flow,MUX=mux,units=len(ss),win=float(np.mean([r['win'] for r in ss]))))
 table('within_source_flow_MUX.csv',matched)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(passed=True,extra_model_forwards=forwards,autograd_calls=0,optimizer_objects=0,training=0,SAT=0,test_reads=0,weights_and_old_files_unchanged=True,seconds=time.perf_counter()-start,claim='frozen recoding intervention;support associations not causal host/MUX attribution'))
 print('FROZEN_TRANSFER_AUDIT_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
