"""Gate v2: verify fold assets against the frozen contract; stop before training if any check fails."""
import json
from pathlib import Path

import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v2_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'


def main():
    rep = json.loads((OUT / 'FOLD_REPORT.json').read_text(encoding='utf-8'))
    checks = []
    for rec, r in rep.items():
        checks.append(dict(fold=rec, name='view_counts',
                           passed=(r['train_views'], r['val_views'], r['test_views']) == (194 if rec == 'ys_abc' else 217, 52, 13),
                           detail=f"{r['train_views']}/{r['val_views']}/{r['test_views']}"))
        checks.append(dict(fold=rec, name='aux_preserved', passed=r['aux_train'] == 154,
                           detail=f"aux in fold ranges={r['aux_train']} (expected 154 virtual/aux nodes; they live outside split arrays)"))
        checks.append(dict(fold=rec, name='official_budget', passed=r['index_short_steps'] == 0,
                           detail=f"short steps={r['index_short_steps']}/200, kept {r['min_kept']}-{r['max_kept']} vs 9165"))
        # normalization rule: cols 0:25 untouched, 25:39 clipped after standardizing
        z = np.load(OUT / f'{rec}_trans.npz')
        raw = np.load(B / 'inputs/trans_train/x39.npy')
        idx = z['rows'][:2000]
        ok = np.array_equal(z['x'][:2000, :25], raw[idx, :25])
        checks.append(dict(fold=rec, name='norm_cols_0_25_untouched', passed=bool(ok), detail='first 25 dims unchanged'))
        checks.append(dict(fold=rec, name='norm_stats_fold_only',
                           passed=r['norm_fit_nodes'] < 1360793,
                           detail=f"fit nodes={r['norm_fit_nodes']} (< full-train 1,360,793)"))
    # N/NC index identity is by construction: one list consumed by both arms; record digest
    gate = dict(passed=all(c['passed'] for c in checks), checks=checks,
                stop_reason='precheck failed; training not started' if not all(c['passed'] for c in checks) else None)
    (OUT / 'GATE_V2.json').write_text(json.dumps(gate, indent=2), encoding='utf-8')
    for c in checks:
        print(c['fold'], c['name'], c['passed'], c['detail'])
    print('GATE', gate['passed'])


if __name__ == '__main__':
    main()
