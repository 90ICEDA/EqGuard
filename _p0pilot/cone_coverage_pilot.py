"""Pilot: build all DFF-D/PO cones for selected test views; measure union coverage vs current cache."""
import sys, json, csv, collections
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
PREP=R/'_p0pilot/seed42_supervised_prep_20261109'; E=R/'_p0pilot/endpoint_cone_build_20261109'
OLD=R/'_p0pilot/seed42_nc_ablation_20261109'; OUT=R/'_p0pilot/lcone_coverage_pilot_20261110'; OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(PREP)); sys.path.insert(0,str(E))
import Signed_common as S
import cone_builder as B

sel=['s38584t100__injalpha_d1_s42__ys_abc','s38584t100__injalpha_d1_s42__ys_aig','s38584t100__injalpha_d1_s42__ys_id','s38584t100__injalpha_d1_s42__ys_nand','s38584t100__injalpha_d1_s42__ys_opt']
c,arr,names,views=S.load_snapshot('test')
y=arr['y']; tr=arr['trusted']; ph=arr['physical']
def stats(cones):
    # cones: list (label, kind, members set)
    neg_nodes=set(); pos_nodes=set(); negcones=[]; poscones=[]
    for lab,kind,mem in cones:
        (negcones if lab==0 else poscones if lab==1 else []).append(mem)
        if lab==0: neg_nodes |= mem
        if lab==1: pos_nodes |= mem
    return neg_nodes,pos_nodes,negcones,poscones
# selected negative totals
neg_total=set(); pos_total=set()
for v in sel:
    lay=views[v]; a,b=lay['start'],lay['stop']
    neg_total |= set(np.where(tr[a:b]&ph[a:b]&(y[a:b]==0))[0]+a)
    pos_total |= set(np.where(tr[a:b]&ph[a:b]&(y[a:b]==1))[0]+a)
# current cache subset
cur=[]
with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if r['view'] not in sel or r['kind'] not in ('D','PO') or int(r['n_phys'])<2 or int(r['label'])<0: continue
        mem=set(int(x) for x in r['phys_rows'].split('|') if x)
        cur.append((int(r['label']),r['kind'],mem))
cur_neg,cur_pos,cur_nc,cur_pc=stats(cur)
# full build
full=[]
for v in sel:
    lay=views[v]; net=S.F/'trans'/(v+'.v')
    b=B.build(net); vr=S.view_rows(views,names,v); lo,hi=lay['start'],lay['stop']
    for cone in b['cones']:
        if cone['kind'] not in ('D','PO'): continue
        mem=set()
        for m in cone['members']:
            r=vr.get(m['cell'])
            if r is not None and lo<=r<hi: mem.add(r)
        if len(mem)<2: continue
        ys=[(int(y[r]),bool(tr[r])) for r in mem]
        pos=any(yy==1 and t for yy,t in ys)
        neg=(not pos) and all(yy==0 and t for yy,t in ys)
        lab=1 if pos else 0 if neg else -1
        full.append((lab,cone['kind'],mem))
full_neg,full_pos,full_nc,full_pc=stats(full)
def summ(name,neg_nodes,pos_nodes,negcones,poscones):
    # positive multi-member: count positive members per positive cone
    mult=[]
    for mem in poscones:
        k=sum(1 for r in mem if y[r]==1 and tr[r]); mult.append(k)
    return dict(name=name,
        cones=len(negcones)+len(poscones), neg_cones=len(negcones), pos_cones=len(poscones),
        neg_nodes_covered=len(neg_nodes), neg_total=len(neg_total), neg_cov=round(len(neg_nodes)/len(neg_total),4),
        pos_nodes_covered=len(pos_nodes), pos_total=len(pos_total), pos_cov=round(len(pos_nodes)/len(pos_total),4),
        neg_mean_members=round(float(np.mean([len(m) for m in negcones])),2) if negcones else None,
        pos_mean_members=round(float(np.mean([len(m) for m in poscones])),2) if poscones else None,
        pos_multige2=round(float(np.mean([k>=2 for k in mult])),4) if mult else None,
        pos_multige5=round(float(np.mean([k>=5 for k in mult])),4) if mult else None)
out=dict(selected_views=sel,current=summ('current_cache_subset',cur_neg,cur_pos,cur_nc,cur_pc),full=summ('all_endpoints',full_neg,full_pos,full_nc,full_pc))
cur_any=set().union(*[m for _,_,m in cur]) if cur else set(); full_any=set().union(*[m for _,_,m in full]) if full else set()
out['current']['neg_any_cov']=round(len(cur_any & neg_total)/len(neg_total),4)
out['full']['neg_any_cov']=round(len(full_any & neg_total)/len(neg_total),4)
cur_pos_hit=set().union(*[m for l,_,m in cur if l==1]) & pos_total if cur else set(); full_pos_hit=set().union(*[m for l,_,m in full if l==1]) & pos_total if full else set()
out['current']['pos_hit']=len(cur_pos_hit); out['current']['pos_hit_cov']=round(len(cur_pos_hit)/len(pos_total),4)
out['full']['pos_hit']=len(full_pos_hit); out['full']['pos_hit_cov']=round(len(full_pos_hit)/len(pos_total),4)
out['full']['total_cones']=len(full); out['full']['label_counts']={str(k):sum(1 for l,_,_ in full if l==k) for k in (-1,0,1)}
out['current']['total_cones']=len(cur); out['current']['label_counts']={str(k):sum(1 for l,_,_ in cur if l==k) for k in (-1,0,1)}
(OUT/'COVERAGE_PILOT.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False)[:2000])
