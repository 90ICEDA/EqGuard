"""Run each positive candidate pair in its own yosys process."""
import re,json,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FOLD=ROOT/'generate_trans/folds/hosts_bt31'
VIEW='s15850t100__injzeta_d1_s42__ys_id'; HOST=VIEW.split('__')[0]; INST='injzeta'
ORIG=FOLD/'orig'/f'{HOST}__{INST}_d1_s42.v'; TRANS=FOLD/'trans'/f'{VIEW}.v'; MAP=FOLD/'mappings'/f'{VIEW}.json'
def wsl(p): return '/mnt/c/'+p.as_posix().split('C:/',1)[1]
def module_name(p):
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*module\s+([\\A-Za-z_][\w\\.$]*)',ln)
  if m: return m.group(1).lstrip('\\')
def gates(p):
 d={}
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*([A-Za-z0-9_]+)\s+(\\?\S+)\s*\((.*)\)\s*;',ln)
  if not m: continue
  inst=m.group(2).lstrip('\\'); ports={}
  for pm in re.finditer(r'\.([A-Za-z0-9_]+)\s*\(\s*([^)]*?)\s*\)',m.group(3)): ports[pm.group(1)]=pm.group(2).strip().lstrip('\\')
  d[inst]=ports
 return d
def outnet(p):
 for k in ('Q','Y','QN'):
  if k in p: return p[k]
def main():
 meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]
 pos=[names[i] for i in np.where(f==VIEW)[0] if cm.get(str(i))==1]
 mp=json.load(open(MAP,encoding='utf-8'))['node_alignment']; rev={t:o for o,ts in mp.items() for t in ts}
 og=gates(ORIG); tg=gates(TRANS); om=module_name(ORIG); tm=module_name(TRANS)
 results=[]
 for k,p in enumerate(pos):
  oi=rev.get(p); tp=tg.get(p,{}); tnet=outnet(tp) if tp else p; op=og.get(oi,{}); onet=outnet(op)
  if not oi or not tnet or not onet:
   results.append(dict(trans=p,orig=oi,status='unknown',reason='missing net')); continue
  ys=ROOT/'tmp_sat_pair.ys'
  ys.write_text('\n'.join([f'read_verilog "{wsl(ORIG)}"',f'read_verilog "{wsl(TRANS)}"',f'select -module {om}',f'rename {onet} ZZSAT',f'select -module {tm}',f'rename {tnet} ZZSAT','select -clear',f'equiv_make {om} {tm} equiv','select -module equiv','equiv_simple -undef','equiv_induct -undef -seq 4','equiv_status']),encoding='ascii')
  pr=subprocess.run(['wsl','-e','bash','-lc',f'cd "/mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train" && yosys -s tmp_sat_pair.ys'],capture_output=True,text=True,encoding='utf-8',errors='replace')
  out=(pr.stdout or '')+(pr.stderr or '')
  st='success!' if re.search(r'Trying to prove \$equiv for \\ZZSAT:\s*success!',out) else ('failed' if re.search(r'Trying to prove \$equiv for \\ZZSAT:\s*failed',out) else 'unknown')
  reason='' if st!='unknown' else (out.strip().splitlines()[-1] if out.strip() else 'no log')
  results.append(dict(trans=p,orig=oi,orig_net=onet,trans_net=tnet,status=st,reason=reason))
 summary=dict(view=VIEW,positives=len(pos),proved=sum(r['status']=='success!' for r in results),failed=sum(r['status']=='failed' for r in results),unknown=sum(r['status']=='unknown' for r in results),results=results)
 (ROOT/'10.15/00_说明/SAT_POS_EACH_20261112.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False)); print(json.dumps(results,ensure_ascii=False,indent=1))
if __name__=='__main__': main()
