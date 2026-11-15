"""Evaluate historical H and H+D with common predictions and frozen panels."""
import csv
import gc
import sys
from collections import defaultdict
from statistics import mean, stdev

import numpy as np
import torch

from run import OUT, P, configure, load_module, predecessor, sha

sys.path.insert(0,str(P/'native_hard_fpr_20261113'))
from freeze import DICT, inputs, read, rows, view_ids

sys.path.insert(0,str(P/'c2_endpoint_replay_20261112'))
from replay import endpoint_metrics


def write(name, data):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def predict(mod, model, domain, split):
    d=mod.T.load(domain,split,'A')
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        l=model(d['x'],d['edge']).float()
        margin=(l[:,1]-l[:,0]).cpu().numpy()
        probability=torch.softmax(l,1)[:,1].cpu().numpy()
    return margin,probability


def source_average(result, key):
    groups=defaultdict(list)
    for r in result:
        if r[key] is not None:
            groups[r['source']].append(r[key])
    return mean(map(mean,groups.values())) if groups else None


def main(seeds):
    prior=P/'native_hard_fpr_20261113'
    assert sha(prior/'PANEL.npz')==read(prior/'FROZEN.json')['panel']
    _,endpoints=load_module(P/'lcone_endpoint_overlap_20261112/audit.py','legacy_panel').load()
    views=[r for r in rows(DICT) if r['kind']=='trojan' and r['key'] in ('trans_val','trans_test')]
    source={r['view']:r for r in views}
    data={s:inputs(s) for s in ('val','test')}
    positives={}
    for r in views:
        ids=view_ids(r)
        x=data[r['key'][6:]]
        positives[r['view']]=ids[x['trusted'][ids] & x['physical'][ids] & (x['y'][ids]==1)]
    positive={s:np.concatenate([positives[r['view']] for r in views if r['key']==f'trans_{s}']) for s in data}
    roles=defaultdict(list)
    for r in rows(P/'control_five_seed42_20261107/frozen_role_assignments.csv'):
        if r['key']=='trans_test':
            roles[r['role_class']].append(int(r['row']))
    roles={k:np.array(roles[k],dtype=np.int64) for k in ('trigger','payload','payload_select')}
    summary,node_rows,ep_rows,replay_checks=[],[],[],[]
    with np.load(prior/'PANEL.npz') as panel:
        for seed in seeds:
            mod,_=configure(seed,cone=False)
            for arm,root in [('H',predecessor(seed)),('H_D',OUT)]:
                run=root/f'seed{seed}/H'
                historical=read(run/'EVALUATED.json')
                model=mod.Model().cuda().eval()
                for point in ('best','last'):
                    ck=run/('best.pt' if point=='best' else 'resume.pt')
                    sd=torch.load(ck,map_location='cpu',weights_only=True)
                    if point=='last':
                        assert sd['completed']==200
                        sd=sd['model']
                    model.load_state_dict(sd,strict=True)
                    vt,val_p=predict(mod,model,'trans','val')
                    ts,test_p=predict(mod,model,'trans','test')
                    if point=='best':
                        for split,probs in [('val',val_p),('test',test_p)]:
                            saved=np.load(run/f'trans_{split}_scores.npy')
                            ap=mod.T.metrics(probs,'trans',split,.5)[0]['trusted']['ap']
                            ref=mod.T.metrics(saved,'trans',split,.5)[0]['trusted']['ap']
                            assert abs(ref-historical[split]['val_recall80']['trusted']['ap'])<1e-10
                            diff=np.abs(probs-saved)
                            replay_checks.append(dict(seed=seed,arm=arm,split=split,saved_ap=ref,replayed_ap=ap,
                                mean_absolute_score_diff=float(diff.mean()),max_absolute_score_diff=float(diff.max()),
                                fraction_gt_001=float((diff>.01).mean())))
                            print('REPLAY',replay_checks[-1],flush=True)
                    np.savez_compressed(OUT/f'{seed}_{arm}_{point}_margin.npz',val=vt,test=ts)
                    result=dict(seed=seed,arm=arm,point=point,checkpoint=sha(ck),
                              step=historical['selected']['epoch'] if point=='best' else 200,
                              val_ap=mod.T.metrics(val_p,'trans','val',.5)[0]['trusted']['ap'],
                              test_ap=mod.T.metrics(test_p,'trans','test',.5)[0]['trusted']['ap'])
                    result['val_ap_saved']=historical['val']['val_recall80']['trusted']['ap'] if point=='best' else None
                    result['test_ap_saved']=historical['test']['val_recall80']['trusted']['ap'] if point=='best' else None
                    for policy,ref,y in [('val95',vt,positive['val']),('test95',ts,positive['test'])]:
                        cut=float(np.sort(ref[y])[-int(np.ceil(.95*len(y)))])
                        record=[]
                        for v in views:
                            if v['key']!='trans_test':
                                continue
                            view=v['view']
                            pp=positives[view]
                            row=dict(seed=seed,arm=arm,point=point,policy=policy,source=v['source'],
                                view=view,recipe=v['recipe'],cut=cut,pos=len(pp),hit=int((ts[pp]>=cut).sum()))
                            for name,suffix in [('native','__native'),('hard','')]:
                                ids=panel[view+suffix]
                                flags=ts[ids]>=cut
                                row.update({f'{name}_n':len(ids),f'{name}_fp':int(flags.sum()),
                                    f'{name}_fpr':float(flags.mean()) if len(ids) else None})
                            for name,ii in roles.items():
                                members=np.intersect1d(ii,pp)
                                row[f'{name}_n'],row[f'{name}_hit']=len(members),int((ts[members]>=cut).sum())
                            record.append(row)
                        assert sum(x['pos'] for x in record)==243
                        node_rows.extend(record)
                        result.update({f'{policy}_recall':sum(x['hit'] for x in record)/243,
                                       f'{policy}_cut':cut,
                                       **{f'{policy}_{k}_fpr':source_average(record,k+'_fpr')
                                           for k in ('native','hard')}})
                        for k in roles:
                            n=sum(r[k+'_n'] for r in record)
                            result[f'{policy}_{k}']=sum(r[k+'_hit'] for r in record)/n
                    current=[]
                    for (view,kind),group in endpoints.items():
                        v=source[view]
                        current.append(dict(seed=seed,arm=arm,point=point,view=view,source=v['source'],
                                        recipe=v['recipe'],kind=kind,**endpoint_metrics(group,ts)))
                    for kind in ('D','PO'):
                        group=[x for x in current if x['kind']==kind]
                        for k in ('top_5','recall_512','gates_512','allpos_fp','allpos_unknown','allpos_gates'):
                            result[f'{kind}_{k}']=source_average(group,k)
                    ep_rows.extend(current)
                    summary.append(result)
                    print(seed,arm,point,result['test_ap'],result['test95_native_fpr'],result['D_recall_512'],flush=True)
                del model,sd
                gc.collect()
                torch.cuda.empty_cache()
    write('SUMMARY.csv',summary)
    write('BY_VIEW_NODE.csv',node_rows)
    write('BY_VIEW_ENDPOINT.csv',ep_rows)
    write('REPLAY_CHECKS.csv',replay_checks)
    ag=[]
    for point in ('best','last'):
        ap_keys=('test_ap_saved','val_ap_saved') if point=='best' else ()
        for metric in (*ap_keys,'test_ap','val_ap','test95_recall','test95_native_fpr','test95_hard_fpr','val95_recall',
                       'val95_native_fpr','test95_trigger','test95_payload','test95_payload_select',
                       'D_top_5','D_recall_512','PO_top_5','PO_recall_512','D_gates_512','PO_gates_512',
                       'D_allpos_fp','D_allpos_unknown','D_allpos_gates'):
            left,right=[[r[metric] for r in summary if r['arm']==arm and r['point']==point] for arm in ('H','H_D')]
            diffs=[b-a for a,b in zip(left,right)]
            ag.append(dict(point=point,metric=metric,H=mean(left),H_D=mean(right),delta=mean(diffs),
                           delta_sd=stdev(diffs) if len(diffs)>1 else None,
                           increased=sum(d>0 for d in diffs),decreased=sum(d<0 for d in diffs)))
    write('AGGREGATE.csv',ag)


if __name__=='__main__':
    main(list(map(int,sys.argv[1:] or [42,1,2])))
