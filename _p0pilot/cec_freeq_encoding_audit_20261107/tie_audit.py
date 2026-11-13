"""Root-encoder hardties from identical unfolded typed expressions,not newSAT."""
from pathlib import Path
import collections,csv,gzip,hashlib,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_freeq_zrp_seed42_20261107';P=R/'_p0pilot/cec_boundary_panel_expand_20261107';C=R/'_p0pilot/cec_po_contract_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def ident(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 pp=read(OLD/'EVALUATION_PANELS.json');panels={'train21':pp['train_frozen_pool'],'valH3': [u for u in pp['val_boundary_all'] if u['tier']=='H3']};local=read(R/'_p0pilot/cec_hard_validation_20261106/local_graphs.json');gg=dict(zip(local['cone_ids'],local['graphs']));ctx=dict(zip(local['cone_ids'],local['contexts']))
 with gzip.open(P/'local_graphs.json.gz','rt',encoding='utf-8') as f:z=json.load(f)
 gg.update(zip(z['cone_ids'],z['graphs']));ctx.update(zip(z['cone_ids'],z['contexts']));maps={m['context_key']:{t['slot']:(t['kind'],t['audit_name'],t['bit']) for t in m['tokens']} for m in read(R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json')};finger={}
 for cid in {c for us in panels.values() for u in us for c in u['cones']}:
  g=gg[cid];inc=collections.defaultdict(list)
  for s,d,role,phase in g['edge']:inc[d].append((s,role,phase))
  h=[]
  for j,op in enumerate(g['op']):
   if op in [0,1]:value=('leaf',maps[ctx[cid]][g['slot'][j]])
   elif op in [2,3]:value=('constant',op-2)
   else:
    children=[(role,h[s],phase) for s,role,phase in inc[j]]
    # COMM may reorder,NOT/MUX ordered by distinct role;keep repeated pin entries.
    value=('operation',op,sorted(children))
   h.append(ident(value))
  finger[cid]=h[g['root']]
 rows=[];group=[];maxdelta=0
 for panel,us in panels.items():
  domain='train' if panel=='train21' else 'val';caches={}
  for arm in ['INIT','Z','R','P']:
   for tag in [9000,9001]:
    z=np.load(OLD/f'{domain}_{arm}_tag{tag}.npz');caches[arm,tag]=(dict(zip(z['cone_ids'].tolist(),z['root64'])),)
  for u in us:
   for j,pid in enumerate(u['pair_ids']):
    a,b=u['cones'][2*j:2*j+2];equal=finger[a]==finger[b];record=dict(panel=panel,unit_id=u['unit_id'],pair_id=pid,source=u['source'],context_id=u['context_id'],has_mux=u.get('has_mux',False),identical_typed_unfolded_expression=equal)
    for arm in ['INIT','Z','R','P']:
     for tag in [9000,9001]:
      cache=caches[arm,tag][0];d=float(np.sqrt(np.mean((cache[a].astype(float)-cache[b].astype(float))**2)));record[f'{arm}_{tag}_trueRMS']=d
      if equal:maxdelta=max(maxdelta,d);assert d<2e-5,(pid,arm,tag,d)
    rows.append(record)
   # Different functions cannot have the same exact typed expression.
   for side in [0,1]:assert len({finger[c] for c in u['cones'][side::2]})==u['functions']
  for source in sorted({u['source'] for u in us}):
   rr=[r for r in rows if r['panel']==panel and r['source']==source];group.append(dict(panel=panel,source=source,pairs=len(rr),root_encoder_hardties=sum(r['identical_typed_unfolded_expression'] for r in rr),fraction=float(np.mean([r['identical_typed_unfolded_expression'] for r in rr]))))
 table('root_encoder_hardties.csv',rows);table('root_encoder_hardties_by_source.csv',group)
 bypair={r['pair_id']:r['identical_typed_unfolded_expression'] for r in rows if r['panel']=='train21'};schedule=read(C/'SCHEDULE_SEED42.json');blocked=total=0;weightblocked=0.
 for step in schedule:
  for u in step['units']:
   for pid in next(t for t in panels['train21'] if t['unit_id']==u['unit_id'])['pair_ids']:
    total+=2;blocked+=2*int(bypair[pid]);weightblocked+=2*u['query_weight']*int(bypair[pid])
 write('HARDTIE_SUMMARY.json',dict(meaning='sufficient equality of recursive encoder computation for ANY shared weights,up toFP32 summation;not mere graphsize similarity andnot newCEC',train_pairs=len([r for r in rows if r['panel']=='train21']),train_root_hardties=sum(r['panel']=='train21' and r['identical_typed_unfolded_expression'] for r in rows),val_pairs=len([r for r in rows if r['panel']=='valH3']),val_root_hardties=sum(r['panel']=='valH3' and r['identical_typed_unfolded_expression'] for r in rows),actual_scheduled_anchor_queries=total,P_wrong_target_cannot_strictly_beat_zero_distance_true_queries=blocked,budget_weighted_blocked_fraction=weightblocked/32,observed_max_true_pair_RMS_under_hardtie=maxdelta,interpretation='P target cannot rank strictlyabove an identicallyencoded truecandidate;canonlytie bycollapsing wrong distance,opposed bycommon withinview negative. Contrast-index graph maybe conflictfree while encoder ties make wrongtargets unrealizable. This limits interpreting R-P aslearned benefit;R-Z remains needed.',training=0,SAT=0,model_forwards=0))
 print('ROOT_HARDTIE_AUDIT_COMPLETE',blocked,total,flush=True)
if __name__=='__main__':main()
