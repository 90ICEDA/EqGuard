"""Shared fold I/O and sampling for held-out v5 (gate and training use exactly these functions)."""
import hashlib
import json
from pathlib import Path

import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
V3 = R / '_p0pilot/heldout_recipe_v3_20261109'
V4 = R / '_p0pilot/heldout_recipe_v4_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')


def contract():
    return json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))


def views(split):
    return {v['view']: v for v in contract()['shared_inputs'][f'trans_{split}']['views']}


def fold_stats(rec):
    z = np.load(V4 / f'{rec}_train_map.npz')
    return z['mean'], z['std']


def norm(x, mean, std):
    o = np.array(x, np.float32, copy=True)
    o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10)
    return o


def load_trans(rec, split='train', extra=()):
    if extra:
        bad = [v for v in extra if rec in v]
        if bad:
            raise ValueError(f'held-out recipe view injected: {bad[0]}')
    z = np.load(V4 / f'{rec}_{split}_map.npz')
    mean, std = fold_stats(rec)
    return dict(x=norm(z['x'], mean, std), edge=z['edge'], y=z['y'], trusted=z['trusted'],
                physical=z['physical'], rows=z['rows'], old2new=z['old2new'], new2old=z['new2old'],
                mean=mean, std=std,
                pos=z['pos'] if 'pos' in z.files else None,
                common_pool=z['common_pool'] if 'common_pool' in z.files else None,
                h_pool=z['h_pool'] if 'h_pool' in z.files else None,
                steps=z['steps'] if 'steps' in z.files else None,
                cone_rows=z['cone_rows'] if 'cone_rows' in z.files else None,
                cone_label=z['cone_label'] if 'cone_label' in z.files else None,
                cone_ptr=z['cone_ptr'] if 'cone_ptr' in z.files else None)


def load_orig(split, mean, std):
    folder = B / 'inputs' / f'orig_{split}'
    x = np.load(folder / 'x39.npy')
    return dict(x=norm(x, mean, std), edge=np.load(folder / 'edge_index.npy'),
                y=np.load(folder / 'y.npy'))


def step_indices(rec, step):
    z = load_trans(rec, 'train')
    rng = np.random.default_rng(42 + step)
    common = rng.choice(z['common_pool'], 8192, replace=False)
    extra = rng.choice(z['h_pool'], 144, replace=False)
    return np.concatenate([z['pos'], common, extra]).astype(np.int64), (len(z['pos']), 8192, 144)


def sha_ids(ids):
    return hashlib.sha256(np.ascontiguousarray(ids).tobytes()).hexdigest()
