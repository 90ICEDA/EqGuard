"""Merge the five s15850 injection-view extractions into one audit table."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'
P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
FEATURES = json.loads((ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15/target18_manifest.json').read_text(encoding='utf-8'))['columns']


def main():
    plan = json.loads((T / 'plan.json').read_text(encoding='utf-8'))
    views = [x for x in plan['views'] if '__inj' in x['view']]
    frames = []
    per_view = []
    for item in views:
        d = T / 'views' / item['view']
        rec_path = d / (item['view'] + '.records.json')
        real_path = d / 'real.npy'
        base_path = d / 'base_inputs.npz'
        assert rec_path.exists() and real_path.exists() and base_path.exists(), d
        rec = json.loads(rec_path.read_text(encoding='utf-8'))
        real = np.load(real_path)
        base = np.load(base_path)
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
                covered=bool(real[i, 18]), label=None,
                **{c: float(real[i, j]) for j, c in enumerate(FEATURES) if c != 'covered'}))
        f = pd.DataFrame(rows)
        frames.append(f)
        per_view.append(dict(view=item['view'], family=item['family'],
                             nodes=len(f), eligible=int((f.status == 'eligible').sum()),
                             covered=int(f.covered.sum()),
                             unique_profiles=int(f.loc[f.covered, FEATURES].drop_duplicates().shape[0]),
                             nonlocal_nodes=int(sum(bool(r.get('nonlocal_cut')) for r in rec if r.get('status') == 'eligible'))))
        print('[VIEW]', item['view'], len(f), 'covered', int(f.covered.sum()))
    df = pd.concat(frames, ignore_index=True)
    g = torch.load(P / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    y = g.y[torch.tensor(df.global_node.to_numpy())].numpy().astype(int)
    df['label'] = y
    assert df.global_node.is_unique
    out = T / 'merged_s15850.csv'
    df.to_csv(out, index=False, encoding='utf-8-sig')
    np.savez_compressed(T / 'merged_s15850.npz', features=df[FEATURES].to_numpy(np.float32),
                        global_ids=df.global_node.to_numpy(), labels=df.label.to_numpy(),
                        view=df.view.to_numpy(), family=df.family.to_numpy())
    (T / 'merged_summary.json').write_text(json.dumps(dict(
        status='merged_five_injection_views_no_controls',
        views=per_view, rows=len(df), positives=int(df.label.sum()),
        covered=int(df.covered.sum()), positives_covered=int((df.label.eq(1) & df.covered).sum()),
        notes=['No control views were extracted in this first bounded pass.',
               'All features are the 18D summary plus covered; no labels used for view selection.',
               'Features are zero on unexpanded/ineligible nodes.']), ensure_ascii=False, indent=2), encoding='utf-8')
    print(df.groupby(['family', 'label']).size())


if __name__ == '__main__':
    main()
