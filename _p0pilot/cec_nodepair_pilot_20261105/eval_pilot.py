"""Evaluate the node-pair cone pilot: held-out proved vs differ root-distance AUC (read-only)."""
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRE = ROOT / '_p0pilot/cec_pretrain_ready_20261105'
PROC = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
P2 = ROOT / '_p0pilot/round32_20261029'
MAPD = ROOT / '_p0pilot/label_expand_20261031/p2_mapping'

sys.path.insert(0, str(PRE))
import engine as E  # noqa: E402

HOPS, CAP, MIN_CONE = 4, 200, 8


def build_lists():
    gid_tr = np.load(MAPD / 'x39row_to_global_train.npy')
    inv = np.full(int(gid_tr.max()) + 1, -1, np.int64); inv[gid_tr] = np.arange(len(gid_tr))
    folder = ROOT / json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))['shared_inputs']['trans_train']['folder']
    e = np.load(folder / 'edge_index.npy').astype(np.int64); src, dst = e[0], e[1]
    n = int(max(src.max(), dst.max())) + 1
    order_e = np.argsort(dst, kind='stable'); ds, ss = dst[order_e], src[order_e]
    ind = np.zeros(n + 1, np.int64); np.add.at(ind, ds + 1, 1); ind = np.cumsum(ind)

    def cone(root):
        seen = {root}; frontier = [root]
        for _ in range(HOPS):
            nxt = []
            for u in frontier:
                for v in ss[ind[u]:ind[u + 1]]:
                    if v not in seen:
                        seen.add(v); nxt.append(v)
                        if len(seen) >= CAP:
                            return sorted(seen)
            frontier = nxt
        return sorted(seen)

    def load(npz):
        z = np.load(PROC / npz); a, b = z['a'], z['b']
        ra, rb = inv[a], inv[b]; ok = (ra >= 0) & (rb >= 0)
        return ra[ok], rb[ok]

    def take(rows_a, rows_b, limit):
        idx = rng.permutation(len(rows_a)); out = []; used = set()
        for i in idx:
            a, b = int(rows_a[i]), int(rows_b[i])
            if a in used or b in used:
                continue
            ca, cb = cone(a), cone(b)
            if min(len(ca), len(cb)) < MIN_CONE:
                continue
            used.add(a); used.add(b); out.append((a, b))
            if len(out) >= limit:
                break
        return out

    ra, rb = load('satrel_node_pairs.npz')
    da, db = load('satrel_node_pairs_differ.npz')
    rng = np.random.default_rng(42)
    proved = take(ra, rb, 4000)
    differ = take(da, db, 4000)
    return proved[1000:], differ[1000:]


def main():
    proved, differ = build_lists()
    print('held-out proved', len(proved), 'differ', len(differ), flush=True)
    E.set_inputs()
    data = E.T.load('trans', 'train', 'A')
    states = {'init': torch.load(E.H / 'init_s42.pt', map_location='cpu', weights_only=True)}
    for arm in ['Z', 'R', 'P']:
        p = HERE / f'runs/main/seed42/{arm}/pretrain/resume.pt'
        if p.exists():
            sd = torch.load(p, map_location='cpu', weights_only=False)
            states[arm] = {k: v for k, v in sd['model'].items() if not k.startswith('classifier.')}
    out = {}
    for tag, sd in states.items():
        model = E.EncoderModel().cuda()
        missing = model.load_state_dict(sd, strict=False)
        model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            h = model.encode(data['x'], data['edge']).float()
        a = np.array([p[0] for p in proved]); b = np.array([p[1] for p in proved])
        da = np.array([p[0] for p in differ]); db = np.array([p[1] for p in differ])
        d_proved = (h[a] - h[b]).square().mean(1).sqrt().cpu().numpy()
        d_differ = (h[da] - h[db]).square().mean(1).sqrt().cpu().numpy()
        auc = float(roc_auc_score([1] * len(d_proved) + [0] * len(d_differ), -np.r_[d_proved, d_differ]))
        out[tag] = dict(auc=round(auc, 4), proved_rms=round(float(d_proved.mean()), 4),
                        differ_rms=round(float(d_differ.mean()), 4), missing=len(missing.missing_keys))
        print(tag, out[tag], flush=True)
        del model, h
        torch.cuda.empty_cache()
    (HERE / 'eval_pilot.json').write_text(json.dumps(out, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
