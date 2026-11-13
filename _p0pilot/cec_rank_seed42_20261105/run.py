"""Single-factor experiment: within-source relative ranking objective for CEC pretraining.

Reuses the frozen engine (no modification). The ONLY change is the pair objective:
  absolute  : positive = weighted MSE(real or permuted); different = relu(1-RMS)^2 on negatives
  ranking   : within each source, require d_pos + m <= d_contrast  (m = 0.1 RMS)
Arms: R positive=real pairing; P positive=permuted pairing; Z no association (variance only).
Everything else is inherited: 39v3, split 29/10, model, 50 pretrain + 200 finetune,
dropout 0.2, schedule, init, optimizer, seed 42.
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
    spec = importlib.util.spec_from_file_location('cec_frozen_engine', FROZEN / 'engine.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def copy_inputs():
    for name in ('schedule.json', 'function_inventory.json', 'RUN_CONTRACT.json'):
        src = FROZEN / name
        dst = HERE / name
        if not dst.exists():
            shutil.copy2(src, dst)


MARGIN = 0.1


def rank_terms(z, rows, byid, index, arm):
    if arm not in ['Z', 'R', 'P']:
        raise ValueError('Explicit Z/R/P arm required')
    real, permuted, negative, weights, sources = [], [], [], [], []
    for row in rows:
        a, b = byid[row['pair_a']], byid[row['pair_b']]
        la, ra, lb, rb = [index[c] for c in [a['left_cone'], a['right_cone'], b['left_cone'], b['right_cone']]]
        real.extend([(la, ra), (lb, rb)])
        permuted.extend([(la, rb), (lb, ra)])
        negative.extend([(la, lb), (ra, rb)])
        weights.extend([row['pair_weight']] * 2)
        sources.extend([row['source']] * 2)

    w = z.new_tensor(weights, dtype=torch.float32)

    def rms(edges):
        ids = torch.tensor(edges, dtype=torch.long, device=z.device)
        diff = (z[ids[:, 0]].float() - z[ids[:, 1]].float()).square().mean(1)
        return torch.sqrt(diff + 1e-12)

    d_real, d_perm, d_neg = rms(real), rms(permuted), rms(negative)

    per_source = []
    if arm in ('R', 'P'):
        for s in sorted(set(sources)):
            idx = [i for i, x in enumerate(sources) if x == s]
            wi = w[idx]
            pos = d_real[idx] if arm == 'R' else d_perm[idx]
            others = [d_perm[idx]] if arm == 'R' else [d_real[idx]]
            others.append(d_neg[idx])
            loss = sum(F.relu(pos + MARGIN - o) for o in others)
            per_source.append((loss * wi).sum() / wi.sum().clamp_min(1e-6))
        positive = torch.stack(per_source).mean() if per_source else d_real.sum() * 0
    else:
        positive = d_real.sum() * 0

    std = torch.sqrt(z.float().var(dim=0, unbiased=False) + 1e-4)
    variance = F.relu(.5 - std).mean()
    total = positive + .1 * variance
    return total, dict(rank=positive, variance=variance, representation_std=std.mean(),
                       d_real=d_real.mean(), d_perm=d_perm.mean(), d_neg=d_neg.mean(),
                       margin_real_perm=(d_real - d_perm).mean(), margin_real_neg=(d_real - d_neg).mean())


def main():
    execute = '--execute' in sys.argv
    arms = ['Z', 'R', 'P']
    for a in sys.argv[1:]:
        if a.startswith('--arms='):
            arms = a.split('=', 1)[1].split(',')
    copy_inputs()
    eng = load_engine()
    eng.O = HERE
    eng.terms = rank_terms
    contract = dict(
        status='PREPARED_SINGLE_FACTOR_RANKING',
        only_change='pair objective: absolute MSE+hinge(1-RMS)^2 -> within-source ranking margin (d_pos + 0.1 <= d_contrast)',
        unchanged=['39v3 features', 'split 29/10', 'model dual_mix_post_cat', '50 pretrain + 200 finetune',
                   'dropout 0.2', 'schedule/sampling', 'init', 'optimizer', 'seed 42'],
        z_definition='no association term; variance term only (documented as no-association control)',
        margin=MARGIN, seeds=[42], new_sat_queries=0, test_policy='no test selection; test evaluated once at the end')
    if not execute:
        (HERE / 'CONTRACT_RANK.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
        print('prepared; contract written. pass --execute to run', arms)
        return
    for arm in arms:
        eng.pretrain('main', 42, arm)
        eng.finetune('main', 42, arm)
        print('done', arm, flush=True)


if __name__ == '__main__':
    main()
