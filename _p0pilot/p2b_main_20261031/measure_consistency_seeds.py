"""Consistency metrics across seeds: baseline vs L_eq 0.5."""
import os, sys, json, gc
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from torch.nn import Sequential, Linear, BatchNorm1d, ReLU
from torch_geometric.nn import GINConv

ROOT = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from models.gin_net import GINDual

P2 = ROOT / '_p0pilot/round32_20261029'
CONTRACT = json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))
NORM = np.load(P2 / 'normalization.npz')
MAPD = H.parent / 'label_expand_20261031' / 'p2_mapping'
PROC = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
DEVICE = 'cuda'


class DualMixPost(GINDual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.mix = Linear(39, 39)
        self.post = GINConv(Sequential(Linear(64, 64), BatchNorm1d(64), ReLU(), Linear(64, 64)))

    def forward(self, x, edge_index):
        x = x + F.relu(self.mix(x))
        hs = self._run(self.enc_s, x[:, :self.split], edge_index)
        hf = self._run(self.enc_f, x[:, self.split:], edge_index)
        h = self.fuse(torch.cat([hs, hf], dim=1))
        h = F.dropout(F.relu(self.post(h, edge_index)), p=0.2, training=self.training)
        return self.classifier(h)


def load_x(split):
    folder = ROOT / CONTRACT['shared_inputs'][f'trans_{split}']['folder']
    x = torch.tensor(np.load(folder / 'x39.npy'), device=DEVICE)
    structural = ((x[:, 25:] - torch.tensor(NORM['mean'][25:], device=DEVICE)) / torch.tensor(NORM['std'][25:], device=DEVICE)).clamp(-10, 10)
    x = torch.cat((x[:, :25], structural), 1)
    edge = torch.tensor(np.load(folder / 'edge_index.npy'), device=DEVICE)
    return x, edge, np.load(folder / 'y.npy'), np.load(folder / 'trusted.npy')


def predict(model, split):
    x, edge, _, _ = load_x(split)
    model.eval()
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
        out = model(x, edge)
    p = torch.softmax(out.float(), 1)[:, 1].cpu().numpy()
    del out; gc.collect(); torch.cuda.empty_cache()
    return p


def pair_rows(split):
    z = np.load(PROC / 'satrel_node_pairs_all.npz')
    a, b, k = z['a'], z['b'], z['kind']
    gid = np.load(MAPD / f'x39row_to_global_{split}.npy')
    inv = np.full(int(gid.max()) + 1, -1, np.int64); inv[gid] = np.arange(len(gid))
    m = k == 0
    ra, rb = inv[a[m]], inv[b[m]]
    ok = (ra >= 0) & (rb >= 0)
    return ra[ok], rb[ok]


def main():
    out = {}
    for tag, pat in (('base', 'dual_mix_post_cat_s{s}'), ('eq0.5', 'dual_mix_post_cat_s{s}_eq0.5')):
        for s in (42, 1, 2):
            rd = pat.format(s=s)
            p = H / 'runs_ablate' / rd
            if not p.exists():
                continue
            sel = json.loads((p / 'SELECTED.json').read_text())
            torch.manual_seed(s)
            m = DualMixPost(39, 64, 2, num_layers=2, split=29, fusion='concat').cuda()
            m.load_state_dict(torch.load(ROOT / sel['path'], map_location=DEVICE, weights_only=True))
            v = predict(m, 'val')
            _, _, yv, trv = load_x('val')
            th = float(np.nextafter(np.quantile(v[trv & (yv == 0)], .95), np.inf))
            rec = dict(seed=s, val_ap=round(sel['score'], 4), epoch=sel.get('epoch'))
            for split, pv in (('val', v), ('test', predict(m, 'test'))):
                ra, rb = pair_rows(split)
                d = np.abs(pv[ra] - pv[rb])
                rec[split] = dict(mae=round(float(d.mean()), 4), med=round(float(np.median(d)), 4),
                                  flip=round(float(np.mean((pv[ra] >= th) != (pv[rb] >= th))), 4))
            out[f'{tag}_s{s}'] = rec
            print(tag, s, json.dumps(rec), flush=True)
            del m; gc.collect(); torch.cuda.empty_cache()
    (H / 'consistency_metrics_seeds.json').write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
