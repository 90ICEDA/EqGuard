"""Evaluate seed42 H+D and H+D+B best/last on the frozen panels."""
import csv, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch

RUN = Path(__file__).resolve().parent.parent / 'legacy_h_cone_20261115'
sys.path.insert(0, str(RUN))
from run import P, configure, load_module
from evaluate_pair import predict, source_average
sys.path.insert(0, str(P / 'native_hard_fpr_20261113'))
from freeze import DICT, inputs, rows, view_ids
sys.path.insert(0, str(P / 'c2_endpoint_replay_20261112'))
from replay import endpoint_metrics

OUT = Path(__file__).resolve().parent

def load_state(path, point):
    z=torch.load(path,map_location='cpu',weights_only=True)
    if point=='last': return z['model']
    return z

def main():
    prior=P/'native_hard_fpr_20261113'
    _,endpoints=load_module(P/'lcone_endpoint_overlap_20261112/audit.py','eval_panel').load()
    views=[r for r in rows(DICT) if r['kind']=='trojan' and r['key'] in ('trans_val','trans_test')]
    source={r['view']:r for r in views}
    data={s:inputs(s) for s in ('val','test')}
    positives={}
    for r in views:
        ids=view_ids(r); x=data[r['key'][6:]]
        positives[r['view']]=ids[x['trusted'][ids] & x['physical'][ids] & (x['y'][ids]==1)]
    positive={s:np.concatenate([positives[r['view']] for r in views if r['key']==f'trans_{s}']) for s in data}
    roles=defaultdict(list)
    for r in rows(P/'control_five_seed42_20261107/frozen_role_assignments.csv'):
        if r['key']=='trans_test': roles[r['role_class']].append(int(r['row']))
    roles={k:np.array(roles[k],dtype=np.int64) for k in ('trigger','payload','payload_select')}
    with np.load(prior/'PANEL.npz') as panel:
        mod,_=configure(42,cone=False)
        out=[]
        for arm,root in [('H_D',RUN/'seed42/H'),('H_D_B',OUT/'seed42/H')]:
            for point in ('best','last'):
                model=mod.Model().cuda().eval()
                path=root/('best.pt' if point=='best' else 'resume.pt')
                model.load_state_dict(load_state(path,point))
                vt,val_p=predict(mod,model,'trans','val')
                ts,test_p=predict(mod,model,'trans','test')
                rec=dict(seed=42,arm=arm,point=point,val_ap=mod.T.metrics(val_p,'trans','val',.5)[0]['trusted']['ap'],
                         test_ap=mod.T.metrics(test_p,'trans','test',.5)[0]['trusted']['ap'])
                for policy,ref,y in [('val95',vt,positive['val']),('test95',ts,positive['test'])]:
                    cut=float(np.sort(ref[y])[-int(np.ceil(.95*len(y)))])
                    rr=[]
                    for v in views:
                        if v['key']!='trans_test': continue
                        pp=positives[v['view']]
                        row=dict(source=v['source'],view=v['view'],recipe=v['recipe'],cut=cut,pos=len(pp),hit=int((ts[pp]>=cut).sum()))
                        for name,suf in [('native','__native'),('hard','')]:
                            ids=panel[v['view']+suf]; row[name+'_fpr']=None if len(ids)==0 else float((ts[ids]>=cut).mean())
                        for k,ii in roles.items():
                            mem=np.intersect1d(ii,pp); row[k+'_n']=len(mem); row[k+'_hit']=int((ts[mem]>=cut).sum())
                        rr.append(row)
                    rec[policy+'_recall']=sum(x['hit'] for x in rr)/243
                    rec[policy+'_native_fpr']=source_average(rr,'native_fpr')
                    rec[policy+'_hard_fpr']=source_average(rr,'hard_fpr')
                    for k in roles:
                        n=sum(x[k+'_n'] for x in rr); rec[policy+'_'+k]=sum(x[k+'_hit'] for x in rr)/n if n else None
                ep=[]
                for (view,kind),group in endpoints.items():
                    vv=source.get(view)
                    if not vv or vv['key']!='trans_test': continue
                    ep.append(dict(kind=kind,source=vv['source'],recipe=vv['recipe'],**endpoint_metrics(group,ts)))
                for kind in ('D','PO'):
                    g=[x for x in ep if x['kind']==kind]
                    rec[kind+'_512']=source_average(g,'recall_512')
                    rec[kind+'_top5']=source_average(g,'top_5')
                    rec[kind+'_unknown']=source_average(g,'allpos_unknown')
                    rec[kind+'_gates']=source_average(g,'allpos_gates')
                out.append(rec); print(rec,flush=True)
        OUT.joinpath('SUMMARY_B.csv').write_text('\n'.join([','.join(map(str,r.keys())) for r in out]),encoding='utf-8')
        (OUT/'SUMMARY_B.json').write_text(__import__('json').dumps(out,indent=2),encoding='utf-8')
if __name__=='__main__': main()
