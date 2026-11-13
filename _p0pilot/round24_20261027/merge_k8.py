"""Merge the four-view k=8 panel into one audit table."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k8_rs232_round24'
P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
sys.path.insert(0, str(Path(__file__).parent))
from sat_boundary_semantics_k8 import COLS  # noqa: E402
FEATURES = COLS + ['covered']


def main():
    plan = json.loads((T / 'plan.json').read_text(encoding='utf-8'))
    frames = []
    per_view = []
    for item in plan['views']:
        d = T / 'views' / item['view']
        rec_path = d / (item['view'] + '.records.json')
        real_path = d / 'real.npy'
        base_path = d / 'base_inputs.npz'
        cov_path = d / 'coverage.json'
        assert rec_path.exists() and real_path.exists() and base_path.exists() and cov_path.exists(), d
        rec = json.loads(rec_path.read_text(encoding='utf-8'))
        real = np.load(real_path)
        base = np.load(base_path)
        cov = json.loads(cov_path.read_text(encoding='utf-8'))
        ids = base['global_ids']
        assert len(rec) == len(real) == len(ids)
        rows = []
        for r in rec:
            i = int(r['local_node'])
            rows.append(dict(
                global_node=int(ids[i]), local_node=i, view=r['view'],
                family=r['family'], split=r['split'], cell=r['cell'],
                driver_type=r.get('driver_type'), target_role=r.get('target_role'),
                k=int(r.get('k', 0)), status=r.get('status'),
                nonlocal_cut=bool(r.get('nonlocal_cut')),
                covered=bool(real[i, 18]), label=None,
                **{c: float(real[i, j]) for j, c in enumerate(COLS)}))
        f = pd.DataFrame(rows)
        frames.append(f)
        per_view.append(dict(view=item['view'], family=item['family'],
                             nodes=len(f), eligible=int((f.status == 'eligible').sum()),
                             covered=int(f.covered.sum()),
                             coverage=float(f.covered.mean()) if len(f) else 0.0,
                             unique_profiles=int(f.loc[f.covered, FEATURES].drop_duplicates().shape[0]),
                             nonlocal_nodes=int(f.nonlocal_cut.sum()),
                             sat_queries=int(cov['actual_sat_queries'])))
        print('[VIEW]', item['view'], len(f), 'covered', int(f.covered.sum()), flush=True)
    df = pd.concat(frames, ignore_index=True)
    g = torch.load(P / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    y = g.y[torch.tensor(df.global_node.to_numpy())].numpy().astype(int)
    df['label'] = y
    assert df.global_node.is_unique
    out = T / 'merged_rs232_k8.csv'
    df.to_csv(out, index=False, encoding='utf-8-sig')
    np.savez_compressed(T / 'merged_rs232_k8.npz',
                        features=df[FEATURES].to_numpy(np.float32),
                        global_ids=df.global_node.to_numpy(), labels=df.label.to_numpy(),
                        view=df.view.to_numpy(), family=df.family.to_numpy())
    summary = dict(
        status='merged_4_view_panel_rs232_train_k8_no_controls',
        schema='k8; k_over_8; 18D SAT summary + covered',
        views=per_view, n_views=len(per_view), rows=len(df),
        positives=int(df.label.sum()), covered=int(df.covered.sum()),
        positives_covered=int((df.label.eq(1) & df.covered).sum()),
        sat_queries=int(sum(x['sat_queries'] for x in per_view)),
        coverage=float(df.covered.mean()),
        positives_by_view=df[df.label.eq(1)].view.value_counts().to_dict(),
        notes=['No model training and no test labels read.',
               'Four pre-registered rs232 injection views; all train views.',
               'Features are zero on unexpanded/ineligible nodes.',
               'k=8 uses an 8-bit pattern bus and k_over_8 denominator.'])
    (T / 'merged_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(rows=len(df), positives=int(df.label.sum()), covered=int(df.covered.sum()),
                          positives_covered=int((df.label.eq(1) & df.covered).sum()),
                          sat_queries=summary['sat_queries'], coverage=summary['coverage']),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
