"""Merge verified round27 views including controls; no label/model loading."""
import argparse
import json
from pathlib import Path
import numpy as np
from k4_runtime import PANEL, ROOT, fresh_dir, read_plan, sha, validate_complete, write_new, view_base_path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write',action='store_true',help='Write a new versioned merge directory')
    p.add_argument('--allow-partial',action='store_true',help='Explicitly mark incomplete export')
    a=p.parse_args();plan=read_plan(PANEL/'plan.json');good=[];missing=[]
    for item in plan['views']:
        ok,detail=validate_complete(PANEL/'views'/item['view'])
        (good if ok else missing).append(dict(view=item['view'],detail=detail))
    status=dict(scope='round27 all planned train views including controls',expected=len(plan['views']),
        verified=len(good),missing=missing,complete=not missing,test_labels_read=False,
        training_ready=False,notes=['Permutation is split+role diagnostic only; not matched by gate/k.',
        'k4 describes local unrestricted native physical-Q functions, not sequential safety labels.'])
    print(json.dumps(status,ensure_ascii=False,indent=2))
    if not a.write:return
    if missing and not a.allow_partial:raise SystemExit('Refuse complete export: views are missing')
    if not good:raise SystemExit('No verified views')
    ids_all=[];features=[];views=[];families=[];bindings=[];columns=None
    for item in good:
        v=item['view'];folder=PANEL/'views'/v
        info=json.loads((folder/'coverage.json').read_text())
        if columns is None:columns=info['columns']
        if columns!=info['columns']:raise ValueError('Column contract mismatch')
        base=view_base_path(folder)
        with np.load(base) as z:
            ids=z['global_ids'];edges=z['edge_index']
            if edges.ndim!=2 or edges.shape[0]!=2:
                raise ValueError('Legacy edge shape; run --run --prepare-only first')
        real=np.load(folder/'real.npy');ids_all.append(ids);features.append(real)
        views.extend([v]*len(ids));families.extend([v.split('__')[1]]*len(ids))
        bindings.append(dict(view=v,effective_base=str(base.relative_to(ROOT)),base_sha=sha(base),
            real_sha=sha(folder/'real.npy'),coverage_sha=sha(folder/'coverage.json')))
    ids=np.concatenate(ids_all);x=np.concatenate(features);order=np.argsort(ids)
    if len(np.unique(ids))!=len(ids):raise ValueError('Duplicate global nodes')
    out=fresh_dir(PANEL/'merges','merge')
    with (out/'merged_k4_alltrain.npz').open('xb') as f:
        np.savez_compressed(f,global_ids=ids[order],features=x[order],
            view=np.asarray(views)[order],family=np.asarray(families)[order],columns=np.asarray(columns))
    status.update(rows=len(ids),covered=int(x[:,18].sum()),columns=columns,input_bindings=bindings,
        plan_sha=sha(PANEL/'plan.json'),feature_sha=sha(out/'merged_k4_alltrain.npz'))
    write_new(out/'summary.json',status)
    print('Wrote',out)


if __name__=='__main__':main()
