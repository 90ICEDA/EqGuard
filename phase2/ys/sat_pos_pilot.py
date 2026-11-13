"""Pilot: all trans positives in one view -> orig candidates via mapping -> yosys SAT equivalence."""
import re,json,sys,subprocess,time
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
FOLD=ROOT/'generate_trans/folds/hosts_bt31'
VIEW='s15850t100__injzeta_d1_s42__ys_id'
HOST=VIEW.split('__')[0]
INST='injzeta'
ORIG=FOLD/'orig'/f'{HOST}__{INST}_d1_s42.v'
TRANS=FOLD/'trans'/f'{VIEW}.v'
MAP=FOLD/'mappings'/f'{VIEW}.json'
OUT=ROOT/'10.15/00_说明/SAT_POS_PILOT_20261112.json'
def module_name(p):
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*module\s+([\\A-Za-z_][\w\\.$]*)',ln)
  if m: return m.group(1).lstrip('\\')
 return p.stem
def gates(p):
 d={}
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*([A-Za-z0-9_]+)\s+(\\?\S+)\s*\((.*)\)\s*;',ln)
  if not m: continue
  inst=m.group(2).lstrip('\\'); body=m.group(3); ports={}
  for pm in re.finditer(r'\.([A-Za-z0-9_]+)\s*\(\s*([^)]*?)\s*\)',body):
   ports[pm.group(1)]=pm.group(2).strip().lstrip('\\')
  d[inst]=ports
 return d
def outnet(ports):
 for k in ('Q','Y','QN'):
  if k in ports: return ports[k]
 return None
def main():
 meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]
 idx=np.where(f==VIEW)[0]; pos=[names[i] for i in idx if cm.get(str(i))==1]
 mapping=json.load(open(MAP,encoding='utf-8'))['node_alignment']; rev={t:o for o,ts in mapping.items() for t in ts}
 og=gates(ORIG); tg=gates(TRANS); om=module_name(ORIG); tm=module_name(TRANS)
 pairs=[]; unmatched=[]
 for p in pos:
  oi=rev.get(p)
  if not oi: unmatched.append((p,None,'no mapping')); continue
  # trans net: if p is a gate instance, use its output; else p is a net
  tp=tg.get(p,{})
  tnet=outnet(tp) if tp else p
  op=og.get(oi,{})
  onet=outnet(op)
  if not tnet or not onet: unmatched.append((p,oi,f'no net t={tnet} o={onet}')); continue
  pairs.append((p,oi,onet,tnet))
 # build renames; unique orig/trans nets get unique alias
 def wsl(p):
  s=p.as_posix()
  return '/mnt/c/'+s.split('C:/',1)[1] if 'C:/' in s else s
 lines=[f'read_verilog "{wsl(ORIG)}"',f'read_verilog "{wsl(TRANS)}"',f'select -module {om}']
 used_o=set(); used_t=set()
 for i,(p,oi,onet,tnet) in enumerate(pairs):
  alias=f'ZZSAT{i}'
  if onet not in used_o:
   lines.append(f'rename {onet} {alias}'); used_o.add(onet)
  lines.append(f'select -module {tm}')
  if tnet not in used_t:
   lines.append(f'rename {tnet} {alias}'); used_t.add(tnet)
  lines.append(f'select -module {om}')
 lines += [f'equiv_make {om} {tm} equiv','select -module equiv','equiv_simple -undef','equiv_induct -undef -seq 4','equiv_status']
 ys=ROOT/'tmp_sat_all.ys'; ys.write_text('\n'.join(lines),encoding='ascii')
 p=subprocess.run(['wsl','-e','bash','-lc',f'cd "/mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train" && yosys -s tmp_sat_all.ys'],capture_output=True,text=True,encoding='utf-8',errors='replace')
 out=(p.stdout or '')+(p.stderr or '')
 proved={}
 for m in re.finditer(r'Trying to prove \$equiv for \\(\S+?):\s*(success!|failed)',out):
  proved[m.group(1)]=m.group(2)
 res=[]
 for i,(p0,oi,onet,tnet) in enumerate(pairs):
  res.append(dict(trans=p0,orig=oi,orig_net=onet,trans_net=tnet,status=proved.get(f'ZZSAT{i}','unknown')))
 summary=dict(view=VIEW,positives=len(pos),pairs=len(pairs),unmatched=unmatched,results=res,returncode=p.returncode,proved=sum(r['status']=='success!' for r in res),failed=sum(r['status']=='failed' for r in res),unknown=sum(r['status']=='unknown' for r in res),log_tail=out[-2000:])
 OUT.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in summary.items() if k!='log_tail'},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
