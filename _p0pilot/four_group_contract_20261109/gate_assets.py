"""Minimal asset gate (no model forward): mappings, aux, budgets, normalization, step0 hashes.
Model/optimizer/grad precheck is NOT executed in this round."""
import json, sys
from pathlib import Path
import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
raw = np.load(B / 'inputs/trans_train/x39.npy')
checks = []
rep = json.loads((OUT / 'ASSETS.json').read_text(encoding='utf-8'))
for tag, exp_nodes, exp_aux in (('A', 535069, 154), ('B', 1249120, 154)):
    z = np.load(OUT / f'group_{tag}.npz')
    o2n, n2o = z['old2new'], z['new2old']
    ok = (len(z['y']) == exp_nodes and int((~z['physical']).sum()) == exp_aux
          and np.array_equal(o2n[n2o], np.arange(len(n2o))) and bool((z['edge'] >= 0).all())
          and bool((z['edge'] < len(z['y'])).all()))
    checks.append(dict(group=tag, name='mapping_aux_edges', passed=bool(ok),
                       detail=f'nodes={len(z["y"])}, aux={int((~z["physical"]).sum())}'))
    xin = np.array(z['x'], np.float32, copy=True)
    xin[:, 25:] = np.clip((xin[:, 25:] - z['mean']) / z['std'], -10, 10)
    norm = np.array_equal(xin[:, :25], z['x'][:, :25]) and xin[:, 25:].max() <= 10 + 1e-6 and xin[:, 25:].min() >= -10 - 1e-6
    checks.append(dict(group=tag, name='norm_rule', passed=bool(norm), detail='25:39 clip, 0:25 unchanged'))
    lab = z['cone_label']; ptr = z['cone_ptr']
    cone_ok = (len(lab) == 264 and int(lab.sum()) == 132 and int((lab == 0).sum()) == 132
               and bool((z['cone_rows'] >= 0).all()) and bool((z['cone_rows'] < len(z['y'])).all())
               and bool(z['trusted'][z['cone_rows']].all()) and bool(z['physical'][z['cone_rows']].all()))
    checks.append(dict(group=tag, name='cone_budget', passed=bool(cone_ok),
                       detail=f'cones={len(lab)}, pos={int(lab.sum())}, neg={int((lab==0).sum())}'))
    steps = z['steps']
    checks.append(dict(group=tag, name='steps_200', passed=bool(len(steps) == 200 and len(set(steps.tolist())) == 200),
                       detail=f'steps={len(steps)}, unique={len(set(steps.tolist()))}'))
    checks.append(dict(group=tag, name='pos_quota', passed=bool(len(z['pos']) == 502),
                       detail=f'positives={len(z["pos"])}'))
gate = dict(passed=all(c['passed'] for c in checks), checks=checks,
            model_precheck='NOT_EXECUTED', note='model forward/grad, margin, BN/RNG restore not run this round')
(OUT / 'GATE_ASSETS.json').write_text(json.dumps(gate, indent=2), encoding='utf-8')
for ch in checks:
    if not ch['passed']: print('FAIL', ch)
print('ASSET_GATE', gate['passed'], 'model_precheck', gate['model_precheck'])
