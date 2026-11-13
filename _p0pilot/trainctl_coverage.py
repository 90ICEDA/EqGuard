"""Add train-control trusted-negative cones; measure negative coverage (train; val hypothetical)."""
import csv, json, collections
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
PREP=R/'_p0pilot/seed42_supervised_prep_20261109'; V2=R/'_p0pilot/lcone_v2c_20261110'
B=R/'_p0pilot/control_boundary_v3_20261104'; OUT=R/'_p0pilot/lcone_trainctl_20261110'; OUT.mkdir(exist_ok=True)
c=json.loads((B/'input_contract.json').read_text(encoding='utf-8'))
g=np.load(FG/'group_B.npz'); y=g['y']; oldtr=g['trusted']; ph=g['physical']; rows=g['rows']; loc={r:i for i,r in enumerate(rows.tolist())}
tr2full=np.load(R/'_p0pilot/label_expand_20261031/trust_trans_v2_trainctl.npy'); tr2=tr2full[rows]
# ctl local mask from train views
ctl_names=set()
for v in c['shared_inputs']['trans_train']['views']:
    if 'ctl' in v['view']: ctl_names.add(v['view'])
ctl=np.zeros(len(y),bool)
for v in c['shared_inputs']['trans_train']['views']:
    if v['view'] in ctl_names:
        a,b=v['start'],v['stop']; ids=rows[(rows>=a)&(rows<b)]; idx=np.array([loc[int(x)] for x in ids],dtype=np.int64); ctl[idx]=True
print('ctl nodes',int(ctl.sum()),'views',len(ctl_names),'oldtr',int((oldtr&ph).sum()),'tr2',int((tr2&ph).sum()))
# cache train D
cache=[]
with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if r['split']!='train' or r['kind']!='D' or int(r['n_phys'])<2: continue
        mem=[]
        for x in r['phys_rows'].split('|'):
            if not x: continue
            i=loc.get(int(x))
            if i is not None: mem.append(i)
        if len(mem)>=2: cache.append(dict(view=r['view'],members=np.array(mem,np.int64),label=int(r['label'])))
print('cache cones',len(cache),'ctl cones',sum(1 for x in cache if 'ctl' in x['view']))
# coverage sets
neg_nonctl=set(np.where(oldtr&ph&(y==0)&(~ctl))[0].tolist())
neg_all_old=set(np.where(oldtr&ph&(y==0))[0].tolist())
neg_v2=set(np.where(tr2&ph&(y==0))[0].tolist())
def members_where(cones, pred):
    s=set()
    for x in cones:
        if pred(x): s.update(x['members'].tolist())
    return s
cur=np.load(V2/'cones_v2c_all_D.npz'); curmem=[]; curneg=set()
for i in range(len(cur['label'])):
    mem=cur['rows'][cur['ptr'][i]:cur['ptr'][i+1]]
    if cur['label'][i]==0: curneg.update(mem.tolist()); curmem.append(mem)
oldneg=members_where(cache,lambda x:x['label']==0)
# ctl relabel with tr2
ctlneg=set(); ctlcones=[]
for x in cache:
    if 'ctl' not in x['view']: continue
    mem=x['members']; t=tr2[mem]; yy=y[mem]
    pos=bool(((yy==1)&t).any()); neg=(not pos) and bool(len(mem)) and bool((t).all()) and bool((yy==0).all())
    if pos or neg:
        ctlcones.append((1 if pos else 0,len(mem)))
        if neg: ctlneg.update(mem.tolist())
out=dict(
 train_views=len(c['shared_inputs']['trans_train']['views']), ctl_views=len(ctl_names), ctl_nodes=int(ctl.sum()),
 old_trust=int((oldtr&ph).sum()), new_trust=int((tr2&ph).sum()),
 neg_total_nonctl=len(neg_nonctl), neg_total_old=len(neg_all_old), neg_total_v2=len(neg_v2),
 current_v2c_neg_covered=len(curneg & neg_nonctl), current_v2c_cov=round(len(curneg&neg_nonctl)/len(neg_nonctl),4),
 all_old_neg_cones_covered=len(oldneg & neg_nonctl), all_old_cov=round(len(oldneg&neg_nonctl)/len(neg_nonctl),4),
 ctl_neg_cones=sum(1 for l,s in ctlcones if l==0), ctl_pos_cones=sum(1 for l,s in ctlcones if l==1),
 ctl_neg_mean_members=round(float(np.mean([s for l,s in ctlcones if l==0])),2) if any(l==0 for l,s in ctlcones) else None,
 ctl_neg_covered=len(ctlneg & neg_v2), ctl_neg_cov_v2=round(len(ctlneg&neg_v2)/len(neg_v2),4),
 combined_neg_covered=len((curneg|ctlneg) & neg_v2), combined_cov_v2=round(len((curneg|ctlneg)&neg_v2)/len(neg_v2),4)
)
# val hypothetical: all ctl val views trusted negative; use CONE_CACHE_V2 val? check
valcache=[]
with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if r['split']!='val' or r['kind']!='D' or int(r['n_phys'])<2: continue
        mem=[int(x) for x in r['phys_rows'].split('|') if x]
        if len(mem)>=2: valcache.append(dict(view=r['view'],members=np.array(mem),label=int(r['label'])))
print('valcache',len(valcache),'val ctl',sum(1 for x in valcache if 'ctl' in x['view']))
# val arrays
z=np.load(R/'_p0pilot/control_boundary_v3_20261104/inputs/trans_val/y.npy') if False else None
# use contract folder
import numpy as np
folder=B/'inputs/trans_val'; vy=np.load(folder/'y.npy'); vtr=np.load(folder/'trusted.npy'); vph=np.load(folder/'physical.npy')
vctl_names=set(v['view'] for v in c['shared_inputs']['trans_val']['views'] if 'ctl' in v['view'])
vctl=np.zeros(len(vy),bool)
for v in c['shared_inputs']['trans_val']['views']:
    if v['view'] in vctl_names: vctl[v['start']:v['stop']]=True
vneg=set(np.where(vtr&vph&(vy==0))[0].tolist()); vneg_ctl=set(np.where(vtr&vph&(vy==0)&vctl)[0].tolist()); vneg_non=set(np.where(vtr&vph&(vy==0)&(~vctl))[0].tolist())
vold=set(); vctl_neg=set()
for x in valcache:
    mem=x['members']
    if x['label']==0: vold.update(mem.tolist())
    if 'ctl' in x['view'] and vctl[mem].all() and (vy[mem]==0).all(): vctl_neg.update(mem.tolist())
out['val']=dict(neg_total=len(vneg),neg_nonctl=len(vneg_non),neg_ctl=len(vneg_ctl),old_neg_cones_covered=len(vold&vneg),old_cov=round(len(vold&vneg)/len(vneg),4),
                ctl_neg_cones_covered=len(vctl_neg&vneg),ctl_cov=round(len(vctl_neg&vneg)/len(vneg),4),combined_cov=round(len((vold|vctl_neg)&vneg)/len(vneg),4))
(OUT/'TRAINCTL_COVERAGE.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
