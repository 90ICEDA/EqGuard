"""Sensitivity-only reproduction from compact node table; no graph/SAT load."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import matched_feature_audit as M

def main():
    out=Path(__file__).parent/'matched_feature_reviews/review_00000'
    d=pd.read_csv(out/'analysis_nodes.csv.gz',dtype={c:'category' for c in ['view','host','gate','role']})
    keys=M.LEVELS['view_gate_k'];support=pd.read_csv(out/'support.csv')
    s=support[(support.level=='view_gate_k')&support.supported.eq(True)][keys];s['k']=s['k'].astype(int)
    common=d.merge(s,on=keys,how='inner',validate='many_to_one')
    records=[]
    for lev,ks in M.LEVELS.items():
        a,_,_=M.evaluate(common,ks,lev);records+=a
    agg=M.aggregate(records,[(lev,lambda d,l=lev:d.level==l) for lev in M.LEVELS])
    pd.DataFrame(agg).to_csv(out/'same_cohort_aggregate.csv',index=False,encoding='utf-8-sig')
    original=pd.read_csv(out/'stratum_scores.csv');orig=original[original.level=='view_gate_k'];errors=[]
    for key,z in common.groupby(keys,observed=True):
        for col in ['change','max_change']:
            a=z.loc[z.y==1,col].to_numpy();b=np.sort(z.loc[z.y==0,col].to_numpy())
            value=float(np.mean((np.searchsorted(b,a,'left')+np.searchsorted(b,a,'right'))/(2*len(b))))
            q=orig[orig.score==col]
            for k,v in zip(keys,key):q=q[q[k]==v]
            assert len(q)==1;errors.append(abs(value-float(q.auc_high.iloc[0])))
    assert max(errors)<1e-12
    unsupported=support[(support.level=='view_gate_k')&support.positive.gt(0)&support.supported.eq(False)].copy()
    unsupported['host']=unsupported.view.str.split('__').str[0]
    unsupported.groupby(['host','gate','k'],dropna=False).agg(positive=('positive','sum'),strata=('positive','size')).reset_index().to_csv(out/'unmatched_positive_breakdown.csv',index=False,encoding='utf-8-sig')
    p=orig.pivot_table(index=keys,columns='score',values='auc_high',observed=True);w=orig[orig.score=='change'].set_index(keys).positive
    views=[]
    for v,z in p.groupby(level='view'):
        ww=w.loc[z.index].to_numpy();vals={c:float(np.average(z[c],weights=ww)) for c in M.SCORES}
        views.append(dict(view=v,host=v.split('__')[0],positive=int(ww.sum()),**vals))
    vd=pd.DataFrame(views);vd.to_csv(out/'strict_view_auc.csv',index=False,encoding='utf-8-sig')
    deltas={s:dict(mean_delta_vs_change=float((vd[s]-vd.change).mean()),views_better=int((vd[s]-vd.change>1e-8).sum()),views_tied=int((abs(vd[s]-vd.change)<=1e-8).sum()),views_worse=int((vd[s]-vd.change < -1e-8).sum())) for s in M.SCORES if s not in ['change','max_change']}
    checks=dict(same_cohort_positive=int(common.y.sum()),same_cohort_negative=int((common.y==0).sum()),independent_auc_checks=len(errors),max_auc_error=max(errors),combination_view_deltas=deltas)
    (out/'sensitivity_validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
