"""Why is the dual branch worse? Seed-42 ablations on the old (provenance) mask.

Variants:
  single2        depth control (2 serial GIN layers)
  dual_concat    fusion = concat instead of gate
  dual_post      gate fusion + one extra GIN layer after fusion (restores radius 3)
  dual_randsplit random column permutation before split29 (semantic-split control)
Baselines single4 / dual_gate are reused from runs_oldmask/seed42 if present.

Outputs runs_ablate/<variant>/... and ablate_report.json (incl. gate statistics).
"""
import os
os.environ['P2B_MASK'] = 'old'
import sys, json, time, gc
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from torch.nn import Sequential, Linear, BatchNorm1d, ReLU
from torch_geometric.nn import GINConv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train_ab as T
DIM = (21 if getattr(T, "ENCODING", "39") == "prim" else 39) + int(getattr(T, "EXTRA_DIM", 0))
SPLIT = int(os.environ.get('P2B_SPLIT', 7 if DIM == 21 else 29))
from models.gin_net import GINNodeClassifier, GINDual

H = HERE
DEVICE = 'cuda'


class DualPost(GINDual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.post = GINConv(Sequential(Linear(64, 64), BatchNorm1d(64), ReLU(), Linear(64, 64)))

    def forward(self, x, edge_index):
        hs = self._run(self.enc_s, x[:, :self.split], edge_index)
        hf = self._run(self.enc_f, x[:, self.split:], edge_index)
        g = torch.sigmoid(self.fuse(torch.cat([hs, hf], dim=1)))
        h = g * hs + (1 - g) * hf
        h = F.dropout(F.relu(self.post(h, edge_index)), p=0.2, training=self.training)
        return self.classifier(h)


class DualPost2(DualPost):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.post2 = GINConv(Sequential(Linear(64, 64), BatchNorm1d(64), ReLU(), Linear(64, 64)))

    def forward(self, x, edge_index):
        hs = self._run(self.enc_s, x[:, :self.split], edge_index)
        hf = self._run(self.enc_f, x[:, self.split:], edge_index)
        g = torch.sigmoid(self.fuse(torch.cat([hs, hf], dim=1)))
        h = g * hs + (1 - g) * hf
        for layer in (self.post, self.post2):
            h = F.dropout(F.relu(layer(h, edge_index)), p=0.2, training=self.training)
        return self.classifier(h)


class DualMixPost(GINDual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.mix = Linear(DIM, DIM)
        self.post = GINConv(Sequential(Linear(64, 64), BatchNorm1d(64), ReLU(), Linear(64, 64)))

    def forward(self, x, edge_index):
        x = x + F.relu(self.mix(x))
        hs = self._run(self.enc_s, x[:, :self.split], edge_index)
        hf = self._run(self.enc_f, x[:, self.split:], edge_index)
        if self.fusion == 'concat':
            h = self.fuse(torch.cat([hs, hf], dim=1))
        else:
            g = torch.sigmoid(self.fuse(torch.cat([hs, hf], dim=1)))
            h = g * hs + (1 - g) * hf
        h = F.dropout(F.relu(self.post(h, edge_index)), p=0.2, training=self.training)
        return self.classifier(h)


class DualConcatPost(GINDual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.post = GINConv(Sequential(Linear(64, 64), BatchNorm1d(64), ReLU(), Linear(64, 64)))

    def forward(self, x, edge_index):
        hs = self._run(self.enc_s, x[:, :self.split], edge_index)
        hf = self._run(self.enc_f, x[:, self.split:], edge_index)
        h = self.fuse(torch.cat([hs, hf], dim=1))
        h = F.dropout(F.relu(self.post(h, edge_index)), p=0.2, training=self.training)
        return self.classifier(h)


class DualMixConcat(GINDual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.mix = Linear(DIM, DIM)

    def forward(self, x, edge_index):
        x = x + F.relu(self.mix(x))
        hs = self._run(self.enc_s, x[:, :self.split], edge_index)
        hf = self._run(self.enc_f, x[:, self.split:], edge_index)
        return self.classifier(self.fuse(torch.cat([hs, hf], dim=1)))


SEED = int(os.environ.get('P2B_SEED', '42'))
EPOCHS = int(os.environ.get('P2B_EPOCHS', '100'))


def build(variant, perm=None):
    torch.manual_seed(SEED)
    if variant == 'single2':
        return GINNodeClassifier(DIM, 64, 2, 2).cuda()
    if variant == 'single4':
        return GINNodeClassifier(DIM, 64, 2, 4).cuda()
    if variant == 'single4_h76':
        return GINNodeClassifier(DIM, 76, 2, 4).cuda()
    if variant == 'dual_concat':
        return GINDual(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='concat').cuda()
    if variant == 'dual_gate':
        return GINDual(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='gate').cuda()
    if variant == 'dual_post':
        return DualPost(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='gate').cuda()
    if variant == 'dual_post2':
        return DualPost2(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='gate').cuda()
    if variant == 'dual_gate25':
        return GINDual(39, 64, 2, num_layers=2, split=25, fusion='gate').cuda()
    if variant == 'dual_mix_post':
        return DualMixPost(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='gate').cuda()
    if variant == 'dual_mix_post_cat':
        return DualMixPost(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='concat').cuda()
    if variant == 'dual_concat_post':
        return DualConcatPost(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='concat').cuda()
    if variant == 'dual_mix_concat':
        return DualMixConcat(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='concat').cuda()
    if variant == 'dual_mix_post3':
        return DualMixPost(DIM, 64, 2, num_layers=3, split=SPLIT, fusion='gate').cuda()
    if variant == 'dual_randsplit':
        return GINDual(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='gate').cuda()
    raise ValueError(variant)


def predict_split(model, split, perm=None):
    d = T.load('trans', split, 'A')
    if perm is not None:
        d['x'] = d['x'][:, perm]
    model.eval()
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
        p = model(d['x'], d['edge'])
    s = torch.softmax(p.float(), 1)[:, 1].cpu().numpy()
    del p, d; gc.collect(); torch.cuda.empty_cache()
    return s


NCE = float(os.environ.get('P2B_NCE', '0'))
TAU = float(os.environ.get('P2B_TAU', '0.1'))
POS = None
NEGPOOL = None
if NCE > 0:
    _gid = np.load(T.MAPD / 'x39row_to_global_train.npy')
    _inv = np.full(int(_gid.max()) + 1, -1, np.int64); _inv[_gid] = np.arange(len(_gid))
    _tr = np.load(T.ROOT / T.CONTRACT['shared_inputs']['trans_train']['folder'] / 'trusted.npy')
    _z = np.load(T.ROOT / 'generate_trans/folds/hosts_bt31/data/processed/satrel_node_pairs.npz')
    _m = _z['kind'] == 0
    _a, _b = _inv[_z['a'][_m]], _inv[_z['b'][_m]]
    _ok = (_a >= 0) & (_b >= 0); _a, _b = _a[_ok], _b[_ok]
    _ok = _tr[_a] & _tr[_b]; _a, _b = _a[_ok], _b[_ok]
    POS = (torch.from_numpy(_a).to(T.DEVICE), torch.from_numpy(_b).to(T.DEVICE))
    _zd = np.load(T.ROOT / 'generate_trans/folds/hosts_bt31/data/processed/satrel_node_pairs_differ.npz')
    _da, _db = _inv[_zd['a']], _inv[_zd['b']]
    _ok = (_da >= 0) & (_db >= 0)
    _pool = np.unique(np.concatenate([_da[_ok], _db[_ok]]))
    _pool = _pool[_tr[_pool]]
    NEGPOOL = torch.from_numpy(_pool).to(T.DEVICE)
    print(f'[NCE] lambda={NCE} pos={_a.size} neg_pool={_pool.size} tau={TAU}', flush=True)


def feat_of(model, x, edge_index):
    x = x + F.relu(model.mix(x))
    hs = model._run(model.enc_s, x[:, :model.split], edge_index)
    hf = model._run(model.enc_f, x[:, model.split:], edge_index)
    if model.fusion == 'concat':
        h = model.fuse(torch.cat([hs, hf], dim=1))
    else:
        g = torch.sigmoid(model.fuse(torch.cat([hs, hf], dim=1)))
        h = g * hs + (1 - g) * hf
    return F.relu(model.post(h, edge_index))


def nce_loss(h, pos, pool, tau, npos=1024, nneg=2048):
    a, b = pos
    sel = torch.randint(0, a.numel(), (min(npos, a.numel()),), device=a.device)
    ia, ib = a[sel], b[sel]
    ineg = pool[torch.randint(0, pool.numel(), (min(nneg, pool.numel()),), device=pool.device)]
    ha = F.normalize(h[ia].float(), dim=1); hb = F.normalize(h[ib].float(), dim=1)
    hn = F.normalize(h[ineg].float(), dim=1)
    pos_sim = (ha * hb).sum(1) / tau
    neg_sim = ha @ hn.T / tau
    return -(pos_sim - torch.logsumexp(torch.cat([pos_sim[:, None], neg_sim], 1), 1)).mean()


def train(variant, perm=None, epochs=None):
    epochs = EPOCHS if epochs is None else epochs
    out = H / 'runs_ablate' / (f'{variant}_s{SEED}' + ('_prim' if DIM == 21 else '') + ('_' + T.EXTRA if getattr(T, 'EXTRA', False) else '') + (f'_sp{SPLIT}' if SPLIT != (7 if DIM == 21 else 29) else '') + (f'_e{EPOCHS}' if EPOCHS != 100 else '') + (f'_eq{T.EQ:g}' if getattr(T, 'EQ', 0) > 0 else '') + ('p' if getattr(T, 'EQ_PERM', False) else '') + (f'_nce{NCE:g}' if NCE > 0 else '')); out.mkdir(parents=True, exist_ok=True)
    if (out / 'SELECTED.json').exists():
        return json.loads((out / 'SELECTED.json').read_text())
    model = build(variant, perm)
    common = H / f'common_init_s{SEED}.pt'
    if common.exists():
        ref = torch.load(common, map_location=DEVICE, weights_only=True)
        cur = model.state_dict()
        cur.update({k: v for k, v in ref.items() if k in cur and cur[k].shape == v.shape})
        model.load_state_dict(cur)
    opt = torch.optim.Adam(model.parameters(), lr=.0002, weight_decay=.001)
    o = T.load('orig', 'train', 'A'); t = T.load('trans', 'train', 'A')
    if perm is not None:
        o['x'] = o['x'][:, perm]; t['x'] = t['x'][:, perm]
    best = dict(score=-1, epoch=-1, path=None)
    for epoch in range(epochs):
        T.seed(SEED + epoch); model.train(); opt.zero_grad(set_to_none=True)
        losses = []
        for _name, d in (('orig', o), ('trans', t)):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                if _name == 'trans' and NCE > 0:
                    _h = feat_of(model, d['x'], d['edge'])
                    logits = model.classifier(_h)
                else:
                    logits = model(d['x'], d['edge'])
            loss = T.domain_loss(logits, d['y'], d['mask'])
            if _name == 'trans' and NCE > 0:
                loss = loss + NCE * nce_loss(_h, POS, NEGPOOL, TAU)
            if _name == 'trans' and getattr(T, 'PAIRS', None) is not None:
                _p = torch.softmax(logits.float(), 1)[:, 1]
                _ia, _ib = T.PAIRS
                _sel = torch.randint(0, _ia.numel(), (min(4096, int(_ia.numel())),), device=T.DEVICE)
                loss = loss + T.EQ * (_p[_ia[_sel]] - _p[_ib[_sel]]).abs().mean()
            loss.backward(); losses.append(float(loss.detach())); del loss, logits
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if (epoch + 1) % 5 == 0:
            val = predict_split(model, 'val', perm)
            summary, _ = T.metrics(val, 'trans', 'val', .5)
            score = summary['trusted']['ap']
            if score > best['score']:
                p = out / f'best_epoch_{epoch+1:03d}.pt'; torch.save(model.state_dict(), p)
                best = dict(score=score, epoch=epoch + 1, path=str(p.relative_to(T.ROOT)))
    T.write(out / 'SELECTED.json', dict(**best, updates=epochs, parameters=sum(p.numel() for p in model.parameters())))
    del model, opt, o, t; gc.collect(); torch.cuda.empty_cache()
    return best


def evaluate(variant, perm=None):
    out = H / 'runs_ablate' / (f'{variant}_s{SEED}' + ('_prim' if DIM == 21 else '') + ('_' + T.EXTRA if getattr(T, 'EXTRA', False) else '') + (f'_sp{SPLIT}' if SPLIT != (7 if DIM == 21 else 29) else '') + (f'_e{EPOCHS}' if EPOCHS != 100 else '') + (f'_eq{T.EQ:g}' if getattr(T, 'EQ', 0) > 0 else '') + ('p' if getattr(T, 'EQ_PERM', False) else '') + (f'_nce{NCE:g}' if NCE > 0 else ''))
    sel = json.loads((out / 'SELECTED.json').read_text())
    model = build(variant, perm); model.load_state_dict(torch.load(T.ROOT / sel['path'], map_location=DEVICE, weights_only=True))
    if perm is not None:
        # permute inside load for both splits
        pass
    res = dict(variant=variant, selected=sel)
    # gate stats on validation for dual variants
    if 'dual' in variant:
        d = T.load('trans', 'val', 'A')
        if perm is not None:
            d['x'] = d['x'][:, perm]
        captured = {}
        h = model.fuse.register_forward_hook(lambda m, i, o: captured.__setitem__('g', torch.sigmoid(o).detach().float()))
        model.eval()
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            _ = model(d['x'], d['edge'])
        h.remove()
        g = captured['g'].cpu().numpy().ravel()
        res['gate_mean'] = [round(float(g.mean()), 4), round(float(g.min()), 4), round(float(g.max()), 4)]
        del d; gc.collect(); torch.cuda.empty_cache()
    # predictions
    v = predict_split(model, 'val', perm); va = T.arrays('trans', 'val')
    neg = v[va['trusted'] & (va['y'] == 0)]
    th = float(np.nextafter(np.quantile(neg, .95), np.inf))
    res['threshold'] = th
    res['val'] = T.metrics(v, 'trans', 'val', th)[0]
    res['test'] = T.metrics(predict_split(model, 'test', perm), 'trans', 'test', th)[0]
    del model; gc.collect(); torch.cuda.empty_cache()
    return res


def main():
    rng = np.random.default_rng(20261031)
    perm = torch.from_numpy(rng.permutation(39)).long().cuda()
    allv = {'single2': None, 'single4_h76': None, 'single4': None, 'dual_concat': None, 'dual_post': None, 'dual_post2': None, 'dual_mix_post': None, 'dual_mix_post3': None, 'dual_mix_post_cat': None, 'dual_gate': None, 'dual_gate25': None, 'dual_concat_post': None, 'dual_mix_concat': None, 'dual_randsplit': perm}
    variants = [(name, allv[name]) for name in os.environ.get('P2B_VARIANTS', 'single2,dual_concat,dual_post,dual_randsplit').split(',')]
    rep = {}
    for v, p in variants:
        train(v, p); rep[v] = evaluate(v, p)
        print(v, json.dumps({k: rep[v][k] for k in ('gate_mean', 'threshold')} if 'gate_mean' in rep[v] else {}), flush=True)
    T.write(H / (f'ablate_report_s{SEED}' + ('_prim' if DIM == 21 else '') + ('_' + T.EXTRA if getattr(T, 'EXTRA', False) else '') + (f'_sp{SPLIT}' if SPLIT != (7 if DIM == 21 else 29) else '') + (f'_e{EPOCHS}' if EPOCHS != 100 else '') + (f'_eq{T.EQ:g}' if getattr(T, 'EQ', 0) > 0 else '') + ('p' if getattr(T, 'EQ_PERM', False) else '') + (f'_nce{NCE:g}' if NCE > 0 else '') + '.json'), rep)
    for v in rep:
        t = rep[v]['test']['trusted']
        print(f"{v:14s} AP={t['ap']:.4f} AUC={t['auc']:.4f} R1={t['r1']:.4f} R5={t['r5']:.4f} FPR={t['control_fpr']:.4f} gate={rep[v].get('gate_mean')}")


if __name__ == '__main__':
    main()
