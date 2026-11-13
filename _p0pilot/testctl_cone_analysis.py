"""Analyze test control negative cones: isolated high nodes / view-level alarms under N-B."""
import csv, json, collections
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
OLD=R/'_p0pilot/seed42_nc_ablation_20261109'; OUT=R/'_p0pilot/lcone_testctl_20261110'; OUT.mkdir(exist_ok=True)
z=np.load(FG/'run_B_N/best_testpred.npz'); s=z['scores']; rows=z['rows']; y=z['y']; tr=z['trusted']; ph=z['physical']
loc={r:i for i,r in enumerate(rows.tolist())}
pos=np.where(tr&ph&(y==1))[0]; neg=np.where(tr&ph&(y==0))[0]
thr=float(np.quantile(s[pos],0.05)); print('B95 threshold',thr)
cones=[]; view_nodes=collections.defaultdict(list)
with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if 'ctl' not in r['view'] or r['kind'] not in ('D','PO') or int(r['n_phys'])<2: continue
        mem=[]
        for x in r['phys_rows'].split('|'):
            if not x: continue
            i=loc.get(int(x))
            if i is not None and ph[i]: mem.append(i)
        if len(mem)<2: continue
        cones.append(dict(view=r['view'],kind=r['kind'],mem=np.array(mem)))
        view_nodes[r['view']].extend(mem)
print('control views',len(view_nodes),'cones',len(cones))
recs=[]
for c in cones:
    sc=s[c['mem']]; mx=float(sc.max()); mean=float(sc.mean()); sd=float(sc.std()+1e-6)
    ss=np.sort(sc); second=float(ss[-2]) if len(ss)>1 else mx
    recs.append(dict(view=c['view'],kind=c['kind'],size=len(sc),max=mx,second=second,gap=mx-second,zmax=(mx-mean)/sd,
                     n_high=int((sc>=thr).sum()),n_pos=int((sc>0).sum())))
ctrl_nodes=set().union(*[set(c['mem'].tolist()) for c in cones]) if cones else set()
ctrl_nodes={i for i in ctrl_nodes if y[i]==0 and ph[i]}
fp_nodes=[i for i in ctrl_nodes if s[i]>=thr]
view_stats={}
for v,mem in view_nodes.items():
    mem=np.array(sorted(set(mem))); sc=s[mem]
    view_stats[v]=dict(nodes=int(len(mem)),max=float(sc.max()),n_high=int((sc>=thr).sum()),fp_rate=float((sc>=thr).mean()))
alarm_views=sum(1 for v,x in view_stats.items() if x['n_high']>0)
hit=[x for x in recs if x['n_high']>0]
out=dict(threshold=thr,control_views=len(view_nodes),control_nodes=len(ctrl_nodes),fp_nodes=len(fp_nodes),node_fpr=round(len(fp_nodes)/max(1,len(ctrl_nodes)),4),
         control_cones=len(recs),hit_cones=len(hit),hit_frac=round(len(hit)/max(1,len(recs)),4),
         hit_one_high=sum(1 for x in hit if x['n_high']==1),hit_one_high_frac=round(sum(1 for x in hit if x['n_high']==1)/max(1,len(hit)),4),
         mean_size=round(float(np.mean([x['size'] for x in recs])),2),mean_max=round(float(np.mean([x['max'] for x in recs])),3),
         mean_zmax=round(float(np.mean([x['zmax'] for x in recs])),3),mean_gap=round(float(np.mean([x['gap'] for x in recs])),3),
         hit_mean_max=round(float(np.mean([x['max'] for x in hit])),3) if hit else None,
         hit_mean_size=round(float(np.mean([x['size'] for x in hit])),2) if hit else None,
         alarm_views=alarm_views,alarm_view_frac=round(alarm_views/max(1,len(view_stats)),4),
         top_cones=sorted(hit,key=lambda x:-x['max'])[:10],top_views=sorted(view_stats.items(),key=lambda kv:-kv[1]['max'])[:10])
(OUT/'TESTCTL_CONE_ANALYSIS.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False)[:2500])
