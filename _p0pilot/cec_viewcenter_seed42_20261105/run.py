"""Single factor: per-view centering before pair distances (reuse frozen engine, no modification).

Change: for each update, the pooled cone representation z is centered per view
(z_i -= mean of that view's cones in this update) before the pair distance terms.
Only views with >=2 cones in the update are centered; the variance term still uses raw z.
Everything else inherited: 39v3, split 29/10, model, 50 pretrain + 200 finetune, dropout 0.2,
schedule/sampling, init, optimizer, seed 42, original MSE + hinge objective.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FROZEN = ROOT / '_p0pilot/cec_pretrain_ready_20261105'


def load_engine():
    spec = importlib.util.spec_from_file_location('cec_frozen_engine_vc', FROZEN / 'engine.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def copy_inputs():
    for name in ('schedule.json', 'function_inventory.json', 'RUN_CONTRACT.json'):
        dst = HERE / name
        if not dst.exists():
            shutil.copy2(FROZEN / name, dst)


_VIEWS = None


def view_of(cone_id):
    global _VIEWS
    if _VIEWS is None:
        cones = json.loads((ROOT / '_p0pilot/cec_joint_expand_20261105/final_cones.json').read_text(encoding='utf-8'))
        _VIEWS = {c['cone_id']: c['view'] for c in cones}
    return _VIEWS[cone_id]


def centered_terms(z, rows, byid, index, arm):
    if arm not in ['Z', 'R', 'P']:
        raise ValueError('Explicit Z/R/P arm required')
    cids = list(index.keys())
    views = [view_of(c) for c in cids]
    zc = z.clone()
    stats = []
    for v in sorted(set(views)):
        pos = [i for i, x in enumerate(views) if x == v]
        if len(pos) < 2:
            continue
        idx = torch.tensor(pos, device=z.device)
        mu = z[idx].mean(0, keepdim=True)
        zc[idx] = z[idx] - mu
        stats.append(float(mu.norm()))
    real, permuted, negative, weights = [], [], [], []
    for row in rows:
        a, b = byid[row['pair_a']], byid[row['pair_b']]
        la, ra, lb, rb = [index[c] for c in [a['left_cone'], a['right_cone'], b['left_cone'], b['right_cone']]]
        real.extend([(la, ra), (lb, rb)]); permuted.extend([(la, rb), (lb, ra)]); negative.extend([(la, lb), (ra, rb)])
        weights.extend([row['pair_weight']] * 2)
    w = z.new_tensor(weights, dtype=torch.float32)

    def distances(edges):
        ids = torch.tensor(edges, dtype=torch.long, device=zc.device)
        return (zc[ids[:, 0]].float() - zc[ids[:, 1]].float()).square().mean(1)

    real_mse, perm_mse, neg_mse = distances(real), distances(permuted), distances(negative)
    real_loss = (w * real_mse).sum(); perm_loss = (w * perm_mse).sum()
    positive = real_loss if arm == 'R' else perm_loss if arm == 'P' else real_loss * 0
    different = (w * F.relu(1 - torch.sqrt(neg_mse + 1e-12)).square()).sum()
    std = torch.sqrt(z.float().var(dim=0, unbiased=False) + 1e-4)
    variance = F.relu(.5 - std).mean()
    total = positive + different + .1 * variance
    return total, dict(eq_real=real_loss, eq_permuted=perm_loss, different=different, variance=variance,
                       representation_std=std.mean(),
                       view_centering_shift=z.new_tensor(sum(stats) / max(len(stats), 1)))


def main():
    execute = '--execute' in sys.argv
    arms = ['Z', 'R', 'P']
    for a in sys.argv[1:]:
        if a.startswith('--arms='):
            arms = a.split('=', 1)[1].split(',')
    copy_inputs()
    eng = load_engine()
    eng.O = HERE
    eng.terms = centered_terms
    contract = dict(
        status='PREPARED_SINGLE_FACTOR_VIEW_CENTERING',
        only_change='per-view centering of pooled cone representation before pair distances',
        unchanged=['39v3', 'split 29/10', 'model dual_mix_post_cat', '50 pretrain + 200 finetune', 'dropout 0.2',
                   'schedule/sampling', 'init', 'optimizer', 'seed 42', 'MSE + hinge objective'],
        centering='z_i -= mean(view(i)) computed over cones of that view within the update; views with <2 cones left raw',
        variance_term='computed on raw z (unchanged)',
        acceptance=['control x abc-aig block AUC >= 0.50 (was 0.22)',
                    'injection x id-opt block AUC >= 0.70 (was 0.76)',
                    'detection AP reported, not used for selection'],
        seeds=[42], new_sat_queries=0)
    if not execute:
        (HERE / 'CONTRACT_VIEWCENTER.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
        print('prepared; pass --execute to run', arms)
        return
    for arm in arms:
        eng.pretrain('main', 42, arm)
        eng.finetune('main', 42, arm)
        print('done', arm, flush=True)


if __name__ == '__main__':
    main()
