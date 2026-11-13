"""Validate the rs232 k=4/k=6 extraction artifacts without fitting anything."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'


def check(name):
    T = BASE / name
    df = pd.read_csv(T / ('merged_rs232_' + name.split('_')[1] + '.csv'))
    plan = json.loads((T / 'plan.json').read_text(encoding='utf-8'))
    views = [x['view'] for x in plan['views']]
    cov = [json.loads((T / 'views' / v / 'coverage.json').read_text(encoding='utf-8')) for v in views]
    rec_lengths = []
    for v in views:
        rec = json.loads((T / 'views' / v / (v + '.records.json')).read_text(encoding='utf-8'))
        b = np.load(T / 'views' / v / 'base_inputs.npz')
        rec_lengths.append(len(rec) == len(b['global_ids']))
    out = dict(table=name, views=len(views), rows=len(df),
               unique_global=int(df.global_node.nunique()),
               covered=int(df.covered.sum()), positives=int(df.label.sum()),
               positives_covered=int((df.label.eq(1) & df.covered).sum()),
               sat_queries=int(sum(c['actual_sat_queries'] for c in cov)),
               all_views_have_coverage=all((T / 'views' / v / 'coverage.json').exists() for v in views),
               all_view_lengths_match=bool(all(rec_lengths)),
               feature_nan=int(df[[c for c in df.columns if c not in ('view', 'family', 'cell', 'driver_type', 'target_role', 'status')]].isna().sum().sum()),
               label_values=sorted(map(int, df.label.unique())),
               k_values=sorted(map(int, df.k.unique())),
               positives_by_k=df[df.label.eq(1)].groupby('k').size().to_dict(),
               family_count=int(df.family.nunique()))
    if '_k6_' in name:
        out['k_over_range'] = [float(df.k_over_8.min()), float(df.k_over_8.max())]
    else:
        out['k_over_range'] = [float(df.k_over_4.min()), float(df.k_over_4.max())]
    return out


res = [check('sat_k4_rs232_round23'), check('sat_k6_rs232_round23')]
# Cross-check labels and covered mask are aligned by global node.
d4 = pd.read_csv(BASE / 'sat_k4_rs232_round23/merged_rs232_k4.csv').set_index('global_node')
d6 = pd.read_csv(BASE / 'sat_k6_rs232_round23/merged_rs232_k6.csv').set_index('global_node')
same_index = bool(d4.index.equals(d6.index))
same_labels = bool((d4.label == d6.label).all())
same_cover = bool((d4.covered == d6.covered).all())
summary = dict(status='validation_only_no_training', comparisons=res,
               cross_check=dict(same_index=same_index, same_labels=same_labels,
                                same_covered=same_cover,
                                k4_rows=len(d4), k6_rows=len(d6)))
(BASE / 'sat_k4_rs232_round23/validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
(BASE / 'sat_k6_rs232_round23/validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
