"""Label-blind function signatures and strict versus marginal shuffle support."""
from pathlib import Path
import sys,collections,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
J=R/'_p0pilot/cec_joint_expand_20261105'
sys.path.insert(0,str(J));from common import Store,read,sha,ident,SCHEMA
def main():
 assert not (O/'INVENTORY.json').exists()
 for p,h in read(J/'PUBLISHED.json')['files'].items():assert sha(R/p)==h,p
 store=Store();pairs=[p for p in read(J/'final_pairs.json') if p['split']=='train'];cones={c['cone_id']:c for c in read(J/'final_cones.json')};weights={r['pair_id']:r for r in __import__('csv').DictReader((J/'weights.csv').open(encoding='utf-8-sig'))};groups=collections.defaultdict(list);records=[]
 def sizebin(n):return (n-1).bit_length() if n>1 else 0
 for p in pairs:
  a,b=[cones[p[k]] for k in ['left_cone','right_cone']];ma,mb=store.raw(a['view']),store.raw(b['view']);av,bv=store.evaluators[a['view']][a['root_bit']],store.evaluators[b['view']][b['root_bit']];assert av==bv
  la,lb=[sorted({tuple(t[:3]) for t in c['leaves']}) for c in [a,b]];ta,tb=[m['cells'][c['output_cell']]['type'] for m,c in [(ma,a),(mb,b)]]
  base=[p['source_object'],p['context_id'],a['view'],b['view'],ta,tb,len(la),len(lb),sizebin(len(a['members'])),sizebin(len(b['members']))]
  strict=ident(base+[la,lb]);marginal=ident(base)
  z=dict(pair_id=p['pair_id'],source=p['source_object'],context_id=p['context_id'],left_cone=p['left_cone'],right_cone=p['right_cone'],mask_hex=hex(av),strict_group=strict,marginal_group=marginal,component=weights[p['pair_id']]['component'],left_tokens=[list(t) for t in la],right_tokens=[list(t) for t in lb],left_gate=ta,right_gate=tb,left_size_bin=sizebin(len(a['members'])),right_size_bin=sizebin(len(b['members'])))
  records.append(z);groups['strict',strict].append(z);groups['marginal',marginal].append(z)
 summary=[]
 for mode in ['strict','marginal']:
  for src in sorted({p['source_object'] for p in pairs}):
   rr=[r for (m,g),gg in groups.items() if m==mode for r in gg if r['source']==src and len({z['mask_hex'] for z in gg})>=2];ggs={r[mode+'_group'] for r in rr}
   summary.append(dict(mode=mode,source=src,eligible_pairs=len(rr),groups=len(ggs),distinct_observed_function_signatures=len({r['mask_hex'] for r in rr})))
 (O/'function_inventory.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');(O/'witness_contexts.json').write_text(json.dumps(store.contexts,ensure_ascii=False,indent=2),encoding='utf-8');(O/'INVENTORY.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,summary=summary,inputs=store.inputs),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
