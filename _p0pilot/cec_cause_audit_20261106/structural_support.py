"""Check whether existing small proved pairs admit structurally matched negatives."""
from pathlib import Path
import collections,csv,hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
 pairs=read(J/'final_pairs.json');cones={c['cone_id']:c for c in read(J/'final_cones.json')};depth=read(O/'panel_cone_depths.json');contexts=read(R/'_p0pilot/cec_pretrain_ready_20261105/witness_contexts.json');contexts.update(read(R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json'))
 env={k:{tuple(t['token']):int(t['mask_hex'],16) for t in v['input_masks']} for k,v in contexts.items()};raws={};MASK=(1<<128)-1
 def get(c,ctx):
  view=c['view']
  if view not in raws:
   p=R/c['raw_path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==c['raw_sha'];m=next(iter(read(p)['modules'].values()));leaf={};drv={}
   for n,p in m['ports'].items():
    if p['direction']=='input':
     for j,b in enumerate(p['bits']):leaf[b]=('PI',n,j,0)
   schema={'AND2X2':('Q',['IN1','IN2']),'OR2X1':('Q',['IN1','IN2']),'XOR2X1':('Q',['IN1','IN2']),'INVX0':('QN',['IN']),'MX2X1_RS':('Y',['A','B','S0']),'$and':('Y',['A','B']),'$or':('Y',['A','B']),'$xor':('Y',['A','B']),'$not':('Y',['A']),'$mux':('Y',['A','B','S'])}
   for n,g in m['cells'].items():
    if 'DFF' in g['type'].upper():
     for pin in ['Q','QN']:
      for b in g['connections'].get(pin,[]):leaf[b]=('Q',n,0,int(pin=='QN'))
    else:drv[g['connections'][schema[g['type']][0]][0]]=g
   raws[view]=(m,leaf,drv,schema,{})
  m,leaf,drv,schema,cache=raws[view]
  def ev(b):
   if not isinstance(b,int):assert b in ['0','1'];return MASK if b=='1' else 0
   if b in cache:return cache[b]
   if b in leaf:t=leaf[b];v=env[ctx][t[:3]]^(MASK if t[3] else 0)
   else:
    g=drv[b];a=[ev(g['connections'][pin][0]) for pin in schema[g['type']][1]];typ=g['type']
    if typ in ['AND2X2','$and']:v=a[0]&a[1]
    elif typ in ['OR2X1','$or']:v=a[0]|a[1]
    elif typ in ['XOR2X1','$xor']:v=a[0]^a[1]
    elif typ in ['INVX0','$not']:v=MASK^a[0]
    else:v=(a[2]&a[1])|((MASK^a[2])&a[0])
   cache[b]=v;return v
  return ev(c['root_bit']),m['cells'][c['output_cell']]['type']
 groups=collections.defaultdict(list)
 for p in pairs:
  cc=[cones[p[k]] for k in ['left_cone','right_cone']]
  if max(len(c['members']) for c in cc)>16:continue
  tier='shallow_small' if max(depth[c['cone_id']]['gate_depth'] for c in cc)<=4 else 'small_depth_control'
  (a,ga),(b,gb)=[get(c,p['context_id']) for c in cc];assert a==b
  bounds=[tuple(sorted({tuple(t[:3]) for t in c['leaves']})) for c in cc]
  sizes=[(len(c['members'])-1).bit_length() for c in cc]
  for matching in ['gate_cut','gate_cut_size','strict']:
   key=[p['split'],p['source_object'],tier,matching,p['context_id'],cc[0]['view'],cc[1]['view'],ga,gb,len(bounds[0]),len(bounds[1])]
   if matching in ['gate_cut_size','strict']:key+=sizes
   if matching=='strict':key+=bounds
   groups[tuple(key)].append((p['pair_id'],a))
 result=[]
 for split,source in sorted({(p['split'],p['source_object']) for p in pairs}):
  for tier in ['shallow_small','small_depth_control']:
   for matching in ['gate_cut','gate_cut_size','strict']:
    gg=[v for k,v in groups.items() if k[:4]==(split,source,tier,matching)];eligible=[v for v in gg if len({a for _,a in v})>=2]
    result.append(dict(split=split,source=source,tier=tier,matching=matching,groups_with_certifiable_difference=len(eligible),eligible_pairs=sum(len(v) for v in eligible),conservative_observed_functions=sum(len({a for _,a in v}) for v in eligible)))
 with (O/'existing_structural_support.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
 print(json.dumps([x for x in result if x['eligible_pairs'] and (x['matching']=='strict' or x['split']=='val')],ensure_ascii=False),flush=True)
if __name__=='__main__':main()
