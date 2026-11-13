"""Export the exact union of all 259 frozen GLOBAL training views; no labels."""
import argparse
import json
from pathlib import Path
import numpy as np
import k4_runtime as R


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');a=p.parse_args()
    global_views=R.ROOT/'generate_trans/folds/hosts_bt31/views.json'
    expected=set(json.loads(global_views.read_text())['train_views'])
    supplement=R.PANEL/'train_controls_complement'
    main_merge=sorted((R.PANEL/'merges').glob('merge_*/merged_k4_alltrain.npz'))
    extra_merge=sorted((supplement/'merges').glob('merge_*/merged_k4_alltrain.npz'))
    if not main_merge or not extra_merge:raise SystemExit('Both main and complement complete merges are required')
    s22=R.TABLES/'sat_s15850_round22'
    old_views=[v['view'] for v in R.read_plan(s22/'plan.json')['views']
               if (s22/'views'/v['view']/'coverage.json').exists()]
    sources=[(R.TABLES/'sat_k4_rs232_round23/merged_rs232_k4.npz',
              [v['view'] for v in R.read_plan(R.TABLES/'sat_k4_rs232_round23/plan.json')['views']]),
             (s22/'merged_s15850.npz',old_views),
             (main_merge[-1],[v['view'] for v in R.read_plan(R.PANEL/'plan.json')['views']]),
             (extra_merge[-1],[v['view'] for v in R.read_plan(supplement/'plan.json')['views']])]
    actual=[v for _,views in sources for v in views]
    if len(set(actual))!=len(actual) or set(actual)!=expected:
        raise ValueError('Training view union is incomplete, overlapping or includes non-training views')
    ids=[];features=[];origins=[];bindings=[]
    for i,(path,views) in enumerate(sources):
        with np.load(path) as z:
            g=z['global_ids'];x=z['features']
            if x.shape!=(len(g),19) or not np.isfinite(x).all():raise ValueError('Feature contract')
            ids.append(g);features.append(x);origins.append(np.full(len(g),i,np.int8))
        bindings.append(dict(path=str(path.relative_to(R.ROOT)),sha=R.sha(path),views=len(views),nodes=len(g)))
    ids=np.concatenate(ids);features=np.concatenate(features);origins=np.concatenate(origins)
    if len(np.unique(ids))!=len(ids):raise ValueError('Overlapping global IDs')
    order=np.argsort(ids)
    summary=dict(global_training_views=len(expected),nodes=len(ids),covered=int(features[:,18].sum()),
        sources=bindings,global_views_sha=R.sha(global_views),labels_read=False,training_ready=False,
        note='SAT-only feature store. A fresh grouped training protocol and fair within-fold permutation remain required.')
    print(json.dumps(summary,ensure_ascii=False))
    if a.write:
        out=R.fresh_dir(R.PANEL/'full_training_exports','export')
        with (out/'all_training_k4.npz').open('xb') as f:
            np.savez_compressed(f,global_ids=ids[order],features=features[order],source_panel=origins[order])
        summary['export_sha']=R.sha(out/'all_training_k4.npz');R.write_new(out/'summary.json',summary)
        print(out)


if __name__=='__main__':main()
