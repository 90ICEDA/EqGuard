"""B-mini-PO structural endpoint GT for rs232 injalpha/injdelta, abc/nand, keep/keepnone."""
import sys,json,csv
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); A=R/'_p0pilot/b_mini_po_20261111'; A.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'_p0pilot/seed42_supervised_prep_20261109')); sys.path.insert(0,str(R/'_p0pilot/endpoint_cone_build_20261109'))
import Signed_common as S, cone_builder as B
sources={'injalpha':R/'generate_trans/hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v','injdelta':R/'generate_trans/hosts_bt2/rs232t1000/rs232t1000__injdelta_d1_s42.v'}
targets={}
for src in ('injalpha','injdelta'):
 for rec in ('ys_abc','ys_nand'):
  for sch in ('keepcur','keepnone'):
   targets[(src,rec,sch)]=R/f'generate_trans/keepab_panel_20_stage2a/conv/rs232t1000/rs232t1000__{src}_d1_s42__{sch}__{rec}.v'
def dffs(g):
 out={}
 for cell,(typ,conns) in g['pins'].items():
  if 'DFF' in typ.upper():
   d=dict(conns); out[cell]=d
 return out
def pos_ports(src):
 b=B.build(src); out=set()
 for c in b['cones']:
  if c['kind']=='PO' and any(m['cell'].startswith('Trojan') for m in c['members']): out.add(c['endpoint'])
 return out
rows=[]; summ={}
for src,sp in sources.items():
 gs=S.raw_network(sp,S.lib_pins); ds=dffs(gs); ps=pos_ports(sp)
 pis,pos=B.declared_ports(sp.read_text(encoding='utf-8',errors='ignore'))
 pos=set(pos); pos=set(x.strip().lstrip('\\') for x in pos)
 # strip bus expansion already
 for rec in ('ys_abc','ys_nand'):
  for sch in ('keepcur','keepnone'):
   tp=targets[(src,rec,sch)]; gt=S.raw_network(tp,S.lib_pins); dt=dffs(gt)
   tpis,tpos=B.declared_ports(tp.read_text(encoding='utf-8',errors='ignore')); tpos=set(x.strip().lstrip('\\') for x in tpos)
   # DFF endpoints
   for cell,conns in ds.items():
    if cell not in dt:
     for typy in ('DFF_D','DFF_Q'): rows.append(dict(source=src,recipe=rec,scheme=sch,type=typy,endpoint=cell,status='unknown',label='unknown',reason='dff_missing'))
     continue
    for typy,pin in (('DFF_D','D'),('DFF_Q','Q')):
     net=conns.get(pin); tnet=dt[cell].get(pin)
     status='mapped' if net and tnet else 'unknown'; lab='negative_structural' if status=='mapped' else 'unknown'
     rows.append(dict(source=src,recipe=rec,scheme=sch,type=typy,endpoint=cell,status=status,label=lab,source_net=net,target_net=tnet,reason=''))
   # PO endpoints
   for port in sorted(pos):
    # declared port name may include bus; match exact
    if port in tpos:
     lab='positive_structural' if port in ps else 'negative_structural'; status='mapped'
    else:
     lab='unknown'; status='unknown'
    rows.append(dict(source=src,recipe=rec,scheme=sch,type='PO',endpoint=port,status=status,label=lab,source_net=port,target_net=port,reason='' if status=='mapped' else 'po_missing'))
   # summary
   sel=[x for x in rows if x['source']==src and x['recipe']==rec and x['scheme']==sch]
   summ[f'{src}|{rec}|{sch}']={k:sum(1 for x in sel if x['label']==k) for k in ('positive_structural','negative_structural','unknown')}
   summ[f'{src}|{rec}|{sch}']['total']=len(sel)
with (A/'B_MINI_GT.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
json.dump(summ,open(A/'B_MINI_GT_SUMMARY.json','w'),indent=2)
print(json.dumps(summ,ensure_ascii=False,indent=2))
