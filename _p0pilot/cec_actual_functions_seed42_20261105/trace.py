"""Trace executed R/P schedules to concrete root functions. No model or solver."""
from pathlib import Path
import collections,csv,hashlib,json,sys
import numpy as np
from sympy import Symbol,And,Or,Xor,Not,ITE,lambdify
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'));from audit import SCHEMA,read,sha
def table(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert not (O/'COMPLETE.json').exists();ps={p['pair_id']:p for p in read(J/'final_pairs.json')};cs={c['cone_id']:c for c in read(J/'final_cones.json')};rows=[r for r in read(PRE/'schedule.json') if r['mode']=='main' and r['seed']==42];uses=collections.Counter(r[k] for r in rows for k in ['pair_a','pair_b']);updates=collections.defaultdict(list);models={};info={}
 for r in rows:
  for k in ['pair_a','pair_b']:updates[r[k]].append(r['update'])
 def model(c):
  if c['view'] not in models:assert sha(R/c['raw_path'])==c['raw_sha'];models[c['view']]=next(iter(read(R/c['raw_path'])['modules'].values()))
  return models[c['view']]
 def side(cid):
  if cid in info:return info[cid]
  c=cs[cid];m=model(c);aliases=[n for n,v in m['netnames'].items() if v['bits']==[c['root_bit']]];obs=[]
  for n,p in m['ports'].items():
   if p['direction']=='output':obs +=[f'PO:{n}[{j}]' for j,b in enumerate(p['bits']) if b==c['root_bit']]
  for n,g in m['cells'].items():
   if 'DFF' in g['type'].upper() and g['connections'].get('D')==[c['root_bit']]:obs.append('D:'+n)
  preferred=next((n for n in aliases if n.startswith('Trojan') and n.endswith(('_t1','_t2','_p0','_p1','_p2','_p4'))),None)
  if preferred is None:preferred=next((n for n in aliases if n.startswith('Trojan') and any(s in n for s in ['HJ.S0','HJ.B','HJ.Y','HJ.IN3'])),None)
  if preferred is None:preferred=next((n for n in aliases if n.startswith(('iRECEIVER','iXMIT','uart_','rec_ready','CRC_OUT'))),aliases[0] if aliases else c['output_cell'])
  info[cid]=dict(view=c['view'],cell=c['output_cell'],pin=c['output_pin'],bit=c['root_bit'],name=preferred,aliases=';'.join(aliases),observers=';'.join(obs),gates=len(c['members']),inputs=len({tuple(l[:3]) for l in c['leaves']}));return info[cid]
 actual=[];pos=[]
 for pid,n in sorted(uses.items(),key=lambda z:(ps[z[0]]['source_object'],z[0])):
  p=ps[pid];a,b=[side(p[k]) for k in ['left_cone','right_cone']];positive=all(e['trusted'] and e['label']==1 for e in p['root_endpoints']);record=dict(pair_id=pid,source=p['source_object'],uses=n,updates=';'.join(map(str,sorted(updates[pid]))),positive_root_pair=positive,left_view=a['view'],left_function=a['name'],left_observers=a['observers'],left_aliases=a['aliases'],left_cell=a['cell'],left_pin=a['pin'],left_bit=a['bit'],left_gates=a['gates'],left_inputs=a['inputs'],right_view=b['view'],right_function=b['name'],right_observers=b['observers'],right_aliases=b['aliases'],right_cell=b['cell'],right_pin=b['pin'],right_bit=b['bit'],right_gates=b['gates'],right_inputs=b['inputs']);actual.append(record)
  if positive:pos.append(record)
 fake=[]
 for r in rows:
  a,b=ps[r['pair_a']],ps[r['pair_b']]
  for lhs,rhs in [(a,b),(b,a)]:
   x,y=side(lhs['left_cone']),side(rhs['right_cone']);fake.append(dict(update=r['update'],source=r['source'],block_id=r['block_id'],left_true_pair=lhs['pair_id'],right_true_pair=rhs['pair_id'],left_view=x['view'],left_function=x['name'],left_observers=x['observers'],right_view=y['view'],right_function=y['name'],right_observers=y['observers'],meaning='P pulls these certified-different root functions together'))
 # Small positive cones: show exact symbolic formulas with named PI/Q dictionary.
 formulas=[]
 for p in pos:
  cc=cs[ps[p['pair_id']]['left_cone']];m=model(cc);tokens=sorted({tuple(l[:3]) for l in cc['leaves']})
  if len(tokens)>10 or len(cc['members'])>60:continue
  syms={t:Symbol('x'+str(i)) for i,t in enumerate(tokens)};values={};drivers={}
  for name,port in m['ports'].items():
   if port['direction']=='input':
    for j,b in enumerate(port['bits']):
     if ('PI',name,j) in syms:values[b]=syms['PI',name,j]
  for name,g in m['cells'].items():
   if ('Q',name,0) in syms:
    for pin in ['Q','QN']:
     for b in g['connections'].get(pin,[]):values[b]=Not(syms['Q',name,0]) if pin=='QN' else syms['Q',name,0]
   if name in cc['members']:drivers[g['connections'][SCHEMA[g['type']][0]][0]]=g
  def ev(b):
   if not isinstance(b,int):assert b in ['0','1'];return b=='1'
   if b in values:return values[b]
   g=drivers[b];v=[ev(g['connections'][pin][0]) for pin in SCHEMA[g['type']][1]];t=g['type'];z=And(*v) if t in ['AND2X2','$and'] else Or(*v) if t in ['OR2X1','$or'] else Xor(*v) if t in ['XOR2X1','$xor'] else Not(v[0]) if t in ['INVX0','$not'] else ITE(v[2],v[1],v[0]);values[b]=z;return z
  expr=ev(cc['root_bit']);patterns=np.arange(1<<len(tokens));args=[((patterns>>i)&1).astype(bool) for i in range(len(tokens))];output=np.asarray(lambdify([syms[t] for t in tokens],expr,'numpy')(*args),dtype=bool);assert output.shape==patterns.shape;truthsha=hashlib.sha256(np.packbits(output,bitorder='little').tobytes()).hexdigest();saved=ps[p['pair_id']]['enum']
  if saved.get('truth_sha') and saved.get('inputs')==len(tokens):assert truthsha==saved['truth_sha']
  formulas.append(dict(pair_id=p['pair_id'],source=p['source'],function=p['left_function'],formula=str(expr),variables={str(syms[t]):list(t) for t in tokens},patterns=len(patterns),truth_sha=truthsha))
 summary=[]
 for src in sorted({p['source'] for p in actual}):
  rr=[p for p in actual if p['source']==src];summary.append(dict(source=src,unique_pairs=len(rr),pair_slots=sum(p['uses'] for p in rr),positive_pairs=sum(p['positive_root_pair'] for p in rr),positive_slots=sum(p['uses'] for p in rr if p['positive_root_pair'])))
 table('actual_R_functions_382.csv',actual);table('actual_P_pairs_500.csv',fake);table('actual_positive_functions_12.csv',pos);table('source_summary.csv',summary);(O/'small_positive_formulas.json').write_text(json.dumps(formulas,ensure_ascii=False,indent=2),encoding='utf-8');(O/'COMPLETE.json').write_text(json.dumps(dict(unique_real_pairs=len(actual),real_pair_slots=sum(uses.values()),positive_pairs=len(pos),positive_pair_slots=sum(p['uses'] for p in pos),sources=summary,formula_examples=len(formulas),training=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(formulas,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
