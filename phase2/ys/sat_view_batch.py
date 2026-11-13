"""Batch: per-view positive gate SAT mapping + region labels (Trojan-name region)."""
import re,json,csv,sys,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FOLD=ROOT/'generate_trans/folds/hosts_bt31'; OUT=ROOT/'10.15'/'00_说明'
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
 for k in ('Q','Y','QN','CO'):
  if k in p: return p[k]
def one(view):
 mp_path=FOLD/'mappings'/f'{view}.json'
 if not mp_path.exists(): return None
 mp=json.load(open(mp_path,encoding='utf-8')); orig=FOLD/'orig'/mp['src_verilog']; trans=FOLD/'trans'/f'{view}.v'
 meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]
 pos=[names[i] for i in np.where(f==view)[0] if cm.get(str(i))==1]
 rev={t:o for o,ts in mp['node_alignment'].items() for t in ts}; og=gates(orig); tg=gates(trans); om=module_name(orig); tm=module_name(trans)
 rows=[]
 for p in pos:
  oi=rev.get(p); tp=tg.get(p,{}); tnet=outnet(tp) if tp else p; op=og.get(oi,{}); onet=outnet(op)
  st='unknown'; reason='missing'
  if oi and tnet and onet:
   ys=ROOT/'tmp_sat_one.ys'; ys.write_text('\n'.join([f'read_verilog "{wsl(orig)}"',f'read_verilog "{wsl(trans)}"',f'select -module {om}',f'rename {onet} ZZSAT',f'select -module {tm}',f'rename {tnet} ZZSAT','select -clear',f'equiv_make {om} {tm} equiv','select -module equiv','equiv_simple -undef','equiv_induct -undef -seq 4','equiv_status']),encoding='ascii')
   pr=subprocess.run(['wsl','-e','bash','-lc',f'cd "/mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train" && yosys -s tmp_sat_one.ys'],capture_output=True,text=True,encoding='utf-8',errors='replace'); out=(pr.stdout or '')+(pr.stderr or '')
   st='success!' if re.search(r'Trying to prove \$equiv for \\ZZSAT:\s*success!',out) else ('failed' if re.search(r'Trying to prove \$equiv for \\ZZSAT:\s*failed',out) else 'unknown'); reason='' if st!='unknown' else (out.strip().splitlines()[-1] if out.strip() else 'no log')
  rows.append(dict(view=view,trans_node=p,orig_gate=oi,orig_net=onet,trans_net=tnet,status=st,reason=reason,label=1 if st=='success!' else 'unknown'))
 allg=set(tg); tro=set(pos); outside=sorted(allg-tro)
 # region labels: Trojan-named gates positive; all others negative under name-region definition
 lab=[]
 for g in sorted(allg): lab.append(dict(view=view,gate=g,label=1 if g in tro else 0,region='trojan' if g in tro else 'normal'))
 res=dict(view=view,total_gates=len(allg),trojan_gates=len(tro),outside_gates=len(outside),proved=sum(r['status']=='success!' for r in rows),unknown=sum(r['status']=='unknown' for r in rows),failed=sum(r['status']=='failed' for r in rows),results=rows,labels=lab)
 return res
def main():
 views=[s.strip() for s in sys.argv[1:]] if len(sys.argv)>1 else ['s15850t100__injzeta_d1_s42__ys_id']
 for v in views:
  r=one(v)
  if not r: print('SKIP',v); continue
  p=OUT/f'SAT_REGION_{v}.json'; p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
  print('DONE',v,'gates',r['total_gates'],'trojan',r['trojan_gates'],'proved',r['proved'],'unknown',r['unknown'],flush=True)
if __name__=='__main__': main()
