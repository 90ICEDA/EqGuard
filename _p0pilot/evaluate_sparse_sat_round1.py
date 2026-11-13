"""Reuse grouped evaluation and record matched semantic/normalization contrasts."""
from pathlib import Path
import numpy as np
import pandas as pd
import audit_metrics_20261025 as evaluator
from build_sparse_sat_round1 import ROOT,OUT


def main():
    sources={'B39':ROOT/'_devcfg/gnn_v31a_A2_s42.npz'}
    for name in ['real_bounded','perm_bounded','zero_bounded','real_legacy']:
        sources[name]=ROOT/f'_devcfg/gnn_sparseR1_{name}_s42.npz'
    for name in ['real','perm','zero']:
        path=ROOT/f'_devcfg/gnn_sparseR1_frozen_{name}_s42.npz'
        if path.exists():
            sources['frozen_'+name]=path
    evaluator.main(sources=sources,output_dir=OUT,
                   threshold_reference={'frozen_perm':'frozen_real','frozen_zero':'frozen_real'})
    d=pd.read_csv(OUT/'model_view_metrics.csv')
    pairs=[]
    comparisons=[('real_bounded','perm_bounded','semantic_vs_permuted'),
                 ('real_bounded','zero_bounded','SAT_vs_zero'),
                 ('real_bounded','real_legacy','bounded_vs_legacy'),
                 ('frozen_real','frozen_perm','frozen_semantic_vs_permuted'),
                 ('frozen_real','frozen_zero','frozen_SAT_vs_zero')]
    summary=[]
    for left,right,label in comparisons:
        if left not in set(d.model) or right not in set(d.model):
            continue
        a=d[d.model==left].set_index(['scope','view'])
        b=d[d.model==right].set_index(['scope','view'])
        both=a.join(b,lsuffix='_left',rsuffix='_right',how='inner')
        frame=pd.DataFrame(index=both.index)
        for metric in ['AP','recall_1pct','recall_5pct']:
            frame['delta_'+metric]=both[metric+'_left']-both[metric+'_right']
        frame=frame.reset_index()
        frame['comparison']=label
        pairs.append(frame)
        for scope,g in frame.groupby('scope'):
            vals=g.delta_AP.dropna().to_numpy()
            summary.append(dict(comparison=label,scope=scope,positive_views=len(vals),
                                mean_delta_AP=float(vals.mean()),median_delta_AP=float(np.median(vals)),
                                AP_wins=int((vals>1e-12).sum()),AP_losses=int((vals< -1e-12).sum()),
                                AP_ties=int((np.abs(vals)<=1e-12).sum()),
                                mean_delta_recall_1pct=float(g.delta_recall_1pct.mean()),
                                mean_delta_recall_5pct=float(g.delta_recall_5pct.mean())))
    if pairs:
        pd.concat(pairs,ignore_index=True).to_csv(OUT/'matched_view_deltas.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(summary).to_csv(OUT/'matched_comparison_summary.csv',index=False,encoding='utf-8-sig')
        print(pd.DataFrame(summary).to_string(index=False),flush=True)


if __name__=='__main__':
    main()
