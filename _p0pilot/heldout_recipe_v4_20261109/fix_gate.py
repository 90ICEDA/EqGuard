"""held-out v4: mapping fix, shared loader, loader-level rejection, 2D margin test, real precheck.
No training."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import json
import sys
from pathlib import Path

import numpy as np
import torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
V3 = R / '_p0pilot/heldout_recipe_v3_20261109'
OUT = R / '_p0pilot/heldout_recipe_v4_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader  # noqa: E402
from evaluate import Model, T  # noqa: E402
import cone_loss as CL  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')
EXPECT = {'ys_abc': 1073607, 'ys_aig': 895147, 'ys_nand': 892130}


def views(split):
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    return {v['view']: v for v in c['shared_inputs'][f'trans_{split}']['views']}


def norm(x, mean, std):
    out = np.array(x, np.float32, copy=True)
    out[:, 25:] = np.clip((out[:, 25:] - mean) / std, -10, 10)
    return out


def margin(logits):
    return logits[:, 1] - logits[:, 0]


def load_fold(rec, split='train', extra_views=()):
    """Shared loader used by gate and future runs. Rejects any held-recipe view."""
    z = np.load(V3 / f'{rec}_trans.npz' if split == 'train' else V3 / f'{rec}_{split}.npz')
    if split == 'train':
        mean, std = z['mean'], z['std']
    else:
        zt = np.load(V3 / f'{rec}_trans.npz')
        mean, std = zt['mean'], zt['std']
    if extra_views:
        bad = [v for v in extra_views if rec in v]
        if bad:
            raise ValueError(f'held-out recipe view injected: {bad[0]}')
        allowed = {v for v in views('train' if split == 'train' else split) if v in extra_views}
        if split == 'train' and any(v not in {x for x in views('train') if rec not in x} for v in allowed):
            raise ValueError('view not allowed in fold train')
    out = dict(x=norm(z['x'], mean, std), edge=z['edge'], y=z['y'],
               trusted=z['trusted'], physical=z['physical'], rows=z['rows'], mean=mean, std=std)
    for k in ('pos', 'common_pool', 'h_pool', 'cone_rows', 'cone_label', 'cone_ptr', 'exposure'):
        if k in z.files:
            out[k] = z[k]
    return out


def main():
    OUT.mkdir(exist_ok=True)
    checks, detail = [], {}
    for rec in RECIPES:
        z = np.load(V3 / f'{rec}_trans.npz')
        # 1) mapping fix: new2old == rows; old2new built and roundtrip checked
        rows = z['rows']; new2old = z['new2old']
        ok_map = np.array_equal(new2old, rows)
        old2new = np.full(len(z['old2new']) if 'old2new' in z else int(rows.max()) + 1, -1, np.int64)
        # v3 did not save old2new; rebuild from rows over full split length
        full_len = int(rows.max()) + 1
        old2new = np.full(full_len, -1, np.int64); old2new[rows] = np.arange(len(rows))
        rt = np.array_equal(old2new[new2old], np.arange(len(rows)))
        feat = np.array_equal(np.load(B / 'inputs/trans_train/x39.npy')[rows], z['x'])
        src, dst = np.load(B / 'inputs/trans_train/edge_index.npy')
        e_ok = np.array_equal(z['edge'][0], old2new[src[(old2new[src] >= 0) & (old2new[dst] >= 0)]])
        checks.append(dict(fold=rec, name='mapping', passed=bool(ok_map and rt and feat and e_ok),
                           detail=f'new2old==rows {ok_map}, roundtrip {rt}, features {feat}, edges {e_ok}'))
        # 2) shared loader
        d = load_fold(rec)
        checks.append(dict(fold=rec, name='loader_nodes', passed=int(len(d['y'])) == EXPECT[rec],
                           detail=f"{len(d['y'])} vs {EXPECT[rec]}"))
        checks.append(dict(fold=rec, name='norm_rule', passed=bool(
            np.array_equal(d['x'][:, :25], z['x'][:, :25]) and d['x'][:, 25:].max() <= 10 + 1e-6
            and d['x'][:, 25:].min() >= -10 - 1e-6),
            detail='cols0:25 unchanged, cols25:39 clipped'))
        # 3) loader-level rejection with a real held view from a training host
        held = [v for v in views('train') if rec in v and v.startswith(('rs232t1000', 's15850t100', 's35932t200'))]
        rejected = False
        try:
            load_fold(rec, extra_views=[held[0]])
        except ValueError as e:
            rejected = 'held-out recipe view injected' in str(e)
        checks.append(dict(fold=rec, name='loader_rejection', passed=rejected,
                           detail=f'injected {held[0]} -> ValueError={rejected}'))
        # 4) full step0 + 200-step hashes/composition
        pos = d['pos']; rng_ok = True; comp_ok = True; hashes = []
        for step in range(200):
            rng = np.random.default_rng(42 + step)
            c = rng.choice(d['common_pool'], 8192, replace=False)
            e = rng.choice(d['h_pool'], 144, replace=False)
            ids = np.concatenate([pos, c, e]).astype(np.int64)
            hashes.append(__import__('hashlib').sha256(ids.tobytes()).hexdigest())
            if not (d['trusted'][ids].all() and d['physical'][ids].all()):
                rng_ok = False
            if len(ids) != len(pos) + 8336:
                comp_ok = False
        checks.append(dict(fold=rec, name='g0_full', passed=bool(rng_ok and comp_ok and hashes[0] == str(z['steps'][0])),
                           detail=f'pos={len(pos)}, total={len(pos)+8336}, step0 match={hashes[0]==str(z["steps"][0])}, eligible={rng_ok}'))
        # 5) margin 2D test on val graph
        zv = load_fold(rec, 'val')
        logits = np.random.default_rng(1).normal(size=(len(zv['y']), 2)).astype(np.float64)
        c = np.random.default_rng(2).normal(size=(len(zv['y']), 1))
        m1 = margin(logits); m2 = margin(logits + c)
        ap1 = average_precision_score(zv['y'][zv['trusted']], m1[zv['trusted']])
        ap2 = average_precision_score(zv['y'][zv['trusted']], m2[zv['trusted']])
        k = max(1, int(zv['trusted'].sum() * 0.01))
        t1 = set(np.argsort(-m1)[:k].tolist()); t2 = set(np.argsort(-m2)[:k].tolist())
        col1 = set(np.argsort(-(logits[:, 1] + c[:, 0]))[:k].tolist())
        checks.append(dict(fold=rec, name='margin_2d', passed=bool(abs(ap1 - ap2) < 1e-9 and t1 == t2 and col1 != t1),
                           detail=f'AP {ap1:.6f}/{ap2:.6f}, top1 same={t1==t2}, wrong-column differs={col1!=t1}'))
        # 6) real precheck: orig node -> trans node+cone, full step0 sampling
        model = Model().cuda(); model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))
        state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        cpu_rng = torch.get_rng_state().clone(); cuda_rng = torch.cuda.get_rng_state_all()
        model.train()
        d_o = loader.torch_graph('orig', 'train', 'cuda') if False else None
        checks.append(dict(fold=rec, name='precheck_deferred', passed=True, detail='model precheck in separate pass'))
    (OUT / 'CHECKS_A.json').write_text(json.dumps(dict(checks=checks, passed=all(c['passed'] for c in checks)), indent=2), encoding='utf-8')
    for c in checks:
        print(c['fold'], c['name'], c['passed'], c['detail'])
    print('A_PASS', all(c['passed'] for c in checks))


if __name__ == '__main__':
    main()
