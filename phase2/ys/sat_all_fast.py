"""All positive views: alias all positive pairs per view, one equiv_induct per view."""
import re,json,sys,subprocess
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
def aliases(path, pairs, netidx):
 s=path.read_text(encoding='utf-8',errors='replace'); adds=[]
 for i,(onet,tnet) in enumerate(pairs):
  net=onet if netidx==0 else tnet; adds.append(f'wire ZZSAT_{i}; assign ZZSAT_{i} = {net};')
 i=s.rfind('endmodule'); return s[:i]+'\n'.join(adds)+'\n'+s[i:]
def one(view):
 mp_path=FOLD/'mappings'/f'{view}.json'
 if not mp_path.exists(): return None
 mp=json.load(open(mp_path,encoding='utf-8')); orig=FOLD/'orig'/mp['src_verilog']; trans=FOLD/'trans'/f'{view}.v'
 meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]
 pos=[names[i] for i in np.where(f==view)[0] if cm.get(str(i))==1]
 rev={t:o for o,ts in mp['node_alignment'].items() for t in ts}; og=gates(orig); tg=gates(trans); om=module_name(orig); tm=module_name(trans)
 pairs=[]; metarows=[]
 for p in pos:
  oi=rev.get(p); tp=tg.get(p,{}); tnet=outnet(tp) if tp else p; op=og.get(oi,{}); onet=outnet(op)
  if oi and tnet and onet: pairs.append((onet,tnet)); metarows.append((p,oi,onet,tnet))
  else: metarows.append((p,oi,onet,tnet))
 tmp=ROOT/'tmp_allfast'; tmp.mkdir(exist_ok=True)
 (tmp/'orig.v').write_text(aliases(orig,pairs,0),encoding='utf-8'); (tmp/'trans.v').write_text(aliases(trans,pairs,1),encoding='utf-8')
 ys=ROOT/'tmp_allfast.ys'; ys.write_text('\n'.join([f'read_verilog "{wsl(tmp/"orig.v")}"',f'read_verilog "{wsl(tmp/"trans.v")}"',f'equiv_make {om} {tm} equiv','select -module equiv','equiv_simple -undef','equiv_induct -undef -seq 4','equiv_status']),encoding='ascii')
 pr=subprocess.run(['wsl','-e','bash','-lc',f'cd "/mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train" && yosys -s tmp_allfast.ys'],capture_output=True,text=True,encoding='utf-8',errors='replace'); out=(pr.stdout or '')+(pr.stderr or '')
 proof={int(m.group(1)):m.group(2) for m in re.finditer(r'Trying to prove \$equiv for \\ZZSAT_(\d+):\s*(success!|failed)',out)}
 results=[]
 for i,(p,oi,onet,tnet) in enumerate(metarows):
  st=proof.get(i,'unknown'); results.append(dict(view=view,trans_node=p,orig_gate=oi,orig_net=onet,trans_net=tnet,status=st,label=1 if st=='success!' else 'unknown'))
 allg=set(tg); tro=set(pos); labels=[dict(view=view,gate=g,label=1 if g in tro else 0,region='trojan' if g in tro else 'normal') for g in sorted(allg)]
 return dict(view=view,total_gates=len(allg),trojan_gates=len(tro),outside_gates=len(allg-tro),proved=sum(r['status']=='success!' for r in results),unknown=sum(r['status']=='unknown' for r in results),failed=sum(r['status']=='failed' for r in results),results=results,labels=labels)
def main():
 views=open(ROOT/'sat_views.txt',encoding='utf-8').read().split() if len(sys.argv)<2 else sys.argv[1:]
 for v in views:
  r=one(v)
  if not r: print('SKIP',v,flush=True); continue
  (OUT/f'SAT_ALL_{v}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
  print('DONE',v,r['trojan_gates'],r['proved'],r['unknown'],flush=True)
if __name__=='__main__': main()
