"""P2-B main: single vs dual branch on corrected v2 inputs, seeds 42/1/2.

Training mask: taint-derived trusted labels, injection views only (no control labels).
Eval scope   : taint-derived trusted labels (controls keep their original labels).
Engine/loss  : identical to round32/35 (ASL + 1.4 soft-miss, 100 updates, bf16).
"""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
import sys, json, time, random, hashlib, csv, importlib.util, gc
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
P2 = ROOT / '_p0pilot/round32_20261029'
sys.path.insert(0, str(ROOT))
from models.gin_net import GINNodeClassifier, GINDual

spec = importlib.util.spec_from_file_location('legacy22', ROOT / 'train_test2.2.py')
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
torch.set_num_threads(2)
CONTRACT = json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))
NORM = np.load(P2 / 'normalization.npz')
DEVICE = 'cuda'
EPOCHS = int(os.environ.get('P2B_EPOCHS', '100'))
MASK_MODE = os.environ.get('P2B_MASK', 'new')
SEEDS = tuple(int(x) for x in os.environ.get('P2B_SEEDS', '42,1,2').split(','))
ARMS = tuple(x.strip() for x in os.environ.get('P2B_ARMS', 'A,B').split(','))


def write(p, x):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp'); tmp.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8'); os.replace(tmp, p)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def seed(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)


def arrays(domain, split):
    folder = ROOT / CONTRACT['shared_inputs'][f'{domain}_{split}']['folder']
    d = {n: np.load(folder / (n + '.npy'), mmap_mode='r') for n in ('x39', 'edge_index', 'y', 'physical')}
    if domain == 'trans' and MASK_MODE == 'new':
        d['trusted'] = np.load(H / f'new_mask_{split}.npy')
    elif domain == 'trans' and MASK_MODE == 'mix':
        d['trusted'] = np.load(folder / 'trusted.npy') | np.load(H / f'new_mask_{split}.npy')
    else:
        d['trusted'] = np.load(folder / 'trusted.npy')
    return d


ENCODING = os.environ.get('P2B_ENC', '39')
PRIM = None
if ENCODING == 'prim':
    PRIM = torch.from_numpy(np.load(P2 / 'primitive_matrix.npy').astype(np.float32)).to(DEVICE)

EXTRA = os.environ.get('P2B_EXTRA', '')
K4 = None
EXTRA_DIM = 0
MAPD = H.parent / 'label_expand_20261031' / 'p2_mapping'
K4_SPLIT = {}
if EXTRA in ('k4r', 'k4sr'):
    EXTRA_DIM = 18
elif EXTRA:
    _k = np.load(ROOT / 'generate_trans/folds/hosts_bt31/data/processed/satrel_k4_node_feats.npy').astype(np.float32)
    _k = np.concatenate([_k, np.zeros((1829, _k.shape[1]), np.float32)], 0)   # virtual ids
    if EXTRA in ('k4n', 'k4f', 'k4s'):
        _gid = np.load(MAPD / 'x39row_to_global_train.npy')
        _tr = _gid[_gid < 3220146]
        if EXTRA == 'k4s':
            _keep = [0, 5, 13, 11, 8, 15]   # k_over_4, infeasible, max_input_influence, change_on_comparable, ones_on_forced, complete_restricted
        else:
            _thr = 0.0 if EXTRA == 'k4n' else 0.2
            _keep = [c for c in range(18) if float(_k[_tr, c].std()) > _thr]
        _m = _k[_tr][:, _keep].mean(0); _s = np.maximum(_k[_tr][:, _keep].std(0), 1e-6)
        _z = np.clip((_k[:, _keep] - _m) / _s, -10, 10)
        _k = np.concatenate([_z, _k[:, 18:19]], 1) if EXTRA == 'k4n' else _z
    K4 = torch.from_numpy(_k)
    EXTRA_DIM = int(K4.size(1))


EQ = float(os.environ.get('P2B_EQ', '0'))
EQ_PERM = os.environ.get('P2B_EQ_PERM', '0') == '1'
PAIRS = None
if EQ > 0:
    _z = np.load(ROOT / 'generate_trans/folds/hosts_bt31/data/processed/satrel_node_pairs.npz')
    _a, _b, _k = _z['a'], _z['b'], _z['kind']
    _gid = np.load(MAPD / 'x39row_to_global_train.npy')
    _inv = np.full(int(_gid.max()) + 1, -1, np.int64)
    _inv[_gid] = np.arange(len(_gid))
    _m = _k == 0
    _ra = _inv[_a[_m]]; _rb = _inv[_b[_m]]
    _ok = (_ra >= 0) & (_rb >= 0)
    _tr = np.load(ROOT / CONTRACT['shared_inputs']['trans_train']['folder'] / 'trusted.npy')
    _ok &= _tr[_ra] & _tr[_rb]
    _ra, _rb = _ra[_ok], _rb[_ok]
    if EQ_PERM:
        _rng = np.random.default_rng(20261031)
        _rb = _rb[_rng.permutation(len(_rb))]
    PAIRS = (torch.from_numpy(_ra).to(DEVICE), torch.from_numpy(_rb).to(DEVICE))
    print(f'[EQ] lambda={EQ} pairs={_ra.size} perm={EQ_PERM}', flush=True)


def extra_for(split):
    if split not in K4_SPLIT:
        if EXTRA in ('k4r', 'k4sr'):
            mode = 'lin' if EXTRA == 'k4r' else 'str'
            p = ROOT / f'generate_trans/folds/hosts_bt31/data/processed/satrel_k4_resid_{mode}_{split}.npy'
            K4_SPLIT[split] = torch.from_numpy(np.load(p)).to(DEVICE)
        else:
            gid = torch.from_numpy(np.load(MAPD / f'x39row_to_global_{split}.npy'))
            K4_SPLIT[split] = K4[gid].to(DEVICE)
    return K4_SPLIT[split]


def load(domain, split, arm):
    a = arrays(domain, split)
    x = torch.tensor(np.asarray(a['x39']), device=DEVICE)
    structural = ((x[:, 25:] - torch.tensor(NORM['mean'][25:], device=DEVICE)) / torch.tensor(NORM['std'][25:], device=DEVICE)).clamp(-10, 10)
    if ENCODING == 'prim':
        x = torch.cat((x[:, :25] @ PRIM, structural), 1)
    else:
        x = torch.cat((x[:, :25], structural), 1)
    if EXTRA:
        if domain == 'trans':
            x = torch.cat((x, extra_for(split)), 1)
        else:
            x = torch.cat((x, torch.zeros((x.size(0), EXTRA_DIM), device=DEVICE)), 1)
    return dict(x=x, edge=torch.tensor(np.asarray(a['edge_index']), device=DEVICE),
                y=torch.tensor(np.asarray(a['y']), device=DEVICE),
                mask=torch.tensor(np.asarray(a['trusted']), device=DEVICE))


def domain_loss(logits, y, mask):
    selected = logits[mask].float(); labels = y[mask]
    task = L.compute_task_loss(selected, labels, loss_type='asl')
    recall = L.calc_soft_f1_metrics(torch.softmax(selected / .5, 1), labels)[3]
    return task + 1.4 * (1 - recall).square()


def metrics(scores, domain, split, threshold):
    a = arrays(domain, split); yy = a['y']; rows = []
    for view in CONTRACT['shared_inputs'][f'{domain}_{split}']['views']:
        lo, hi = view['start'], view['stop']
        for scope, mask in [('trusted', a['trusted'][lo:hi]), ('legacy', a['physical'][lo:hi])]:
            y = yy[lo:hi][mask]; p = scores[lo:hi][mask]; pos = int(y.sum()); neg = len(y) - pos
            row = dict(view=view['view'], scope=scope, n=len(y), positive=pos, negative=neg,
                       ap=float(average_precision_score(y, p)) if pos else None,
                       auc=float(roc_auc_score(y, p)) if pos and neg else None,
                       fpr=float((p[y == 0] >= threshold).mean()) if neg else None,
                       threshold=threshold, recall=float((p[y == 1] >= threshold).mean()) if pos else None)
            for budget in (.01, .05):
                k = max(1, int(len(y) * budget)); order = np.argsort(-p, kind='stable')
                row['r' + str(int(budget * 100))] = float(y[order[:k]].sum() / pos) if pos else None
            rows.append(row)
    summary = {}
    for scope in ('trusted', 'legacy'):
        inj = [r for r in rows if r['scope'] == scope and '__inj' in r['view'] and r['positive']]
        summary[scope] = {k: float(np.mean([r[k] for r in inj if r[k] is not None])) for k in ('ap', 'auc', 'r1', 'r5', 'recall')}
        summary[scope]['views'] = len(inj)
        controls = [r for r in rows if r['scope'] == scope and '__inj' not in r['view'] and r['negative']]
        summary[scope]['control_fpr'] = float(np.mean([r['fpr'] for r in controls])) if controls else None
    return summary, rows


def predict(model, domain, split):
    d = load(domain, split, 'A'); model.eval()
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
        p = model(d['x'], d['edge'])
    score = torch.softmax(p.float(), 1)[:, 1].cpu().numpy()
    del p, d; gc.collect(); torch.cuda.empty_cache()
    assert np.isfinite(score).all()
    return score


def model_for(arm, s):
    seed(s)
    dim = 21 if ENCODING == 'prim' else 39
    if EXTRA:
        dim += EXTRA_DIM
    split = int(os.environ.get('P2B_SPLIT', 7 if dim == 21 else 29))
    if arm == 'A':
        return GINNodeClassifier(dim, 64, 2, 4).cuda()
    return GINDual(dim, 64, 2, num_layers=2, split=split, fusion='gate').cuda()


def train_arm(arm, s):
    base = 'runs' if MASK_MODE == 'new' else ('runs_mix' if MASK_MODE == 'mix' else 'runs_oldmask')
    if ENCODING == 'prim':
        base += '_prim'
    if EXTRA:
        base += '_' + EXTRA
    if EPOCHS != 100:
        base += f'_e{EPOCHS}'
    if EQ > 0:
        base += f'_eq{EQ:g}'
        if EQ_PERM:
            base += 'p'
    out = H / base / f'seed{s}' / arm
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'SELECTED.json').exists():
        return json.loads((out / 'SELECTED.json').read_text())
    model = model_for(arm, s)
    common = H / f'common_init_{arm}_s{s}.pt'
    if common.exists():
        ref = torch.load(common, map_location=DEVICE, weights_only=True)
        cur = model.state_dict()
        cur.update({k: v for k, v in ref.items() if k in cur and cur[k].shape == v.shape})
        model.load_state_dict(cur)
    else:
        torch.save({k: v.cpu() for k, v in model.state_dict().items()}, common)
    opt = torch.optim.Adam(model.parameters(), lr=.0002, weight_decay=.001)
    best = dict(score=-1, epoch=-1, path=None); records = []
    o = load('orig', 'train', arm); t = load('trans', 'train', arm)
    assert (o['y'][o['mask']] >= 0).all() and (t['y'][t['mask']] >= 0).all()
    cfg = dict(arm=arm, seed=s, epochs=EPOCHS, updates_per_epoch=1,
               model='single GIN 4 layers hidden64' if arm == 'A' else 'dual gate GIN 2+2 hidden64 split29',
               parameters=sum(p.numel() for p in model.parameters()),
               device=torch.cuda.get_device_name(), python=sys.executable, torch=torch.__version__, amp='bfloat16',
               loss='ASL(1,4,.05) orig+trans + 1.4*(soft miss orig^2 + trans^2)', mode=2,
               label_mask='taint-derived injection-only training mask (no control labels); unknown/virtual excluded',
               validation_every=5, selection='validation mean per-view AP over injection views, trusted scope',
               graph='v2 directed all-pin edges', normalization='gate raw; structural train-only z-score +/-10',
               common_parameter_init='same seed + deterministic construction order; equal-shaped tensors shared only within the same architecture family (cross-architecture tensors are NOT shared)')
    write(out / 'config.json', cfg)
    for epoch in range(EPOCHS):
        begin = time.perf_counter(); seed(s + epoch); model.train(); opt.zero_grad(set_to_none=True)
        losses = []
        for _name, d in (('orig', o), ('trans', t)):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(d['x'], d['edge'])
            loss = domain_loss(logits, d['y'], d['mask'])
            if _name == 'trans' and PAIRS is not None:
                _p = torch.softmax(logits.float(), 1)[:, 1]
                _ia, _ib = PAIRS
                _sel = torch.randint(0, _ia.numel(), (min(4096, int(_ia.numel())),), device=DEVICE)
                loss = loss + EQ * (_p[_ia[_sel]] - _p[_ib[_sel]]).abs().mean()
            loss.backward(); losses.append(float(loss.detach())); del loss, logits
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        rec = dict(epoch=epoch + 1, loss=sum(losses), seconds=time.perf_counter() - begin)
        if (epoch + 1) % 5 == 0:
            val = predict(model, 'trans', 'val'); summary, _ = metrics(val, 'trans', 'val', .5)
            rec['val_ap'] = summary['trusted']['ap']
            if rec['val_ap'] > best['score']:
                path = out / f'best_epoch_{epoch+1:03d}.pt'; torch.save(model.state_dict(), path)
                best = dict(score=rec['val_ap'], epoch=epoch + 1, path=str(path.relative_to(ROOT)))
            torch.save(dict(epoch=epoch, model=model.state_dict(), optimizer=opt.state_dict(), best=best), out / f'checkpoint_{epoch+1:03d}.pt')
        records.append(rec)
    write(out / 'train_log.json', records); write(out / 'SELECTED.json', dict(**best, updates=100, peak_vram_mib=torch.cuda.max_memory_allocated() / 2**20))
    del model, opt, o, t; gc.collect(); torch.cuda.empty_cache()
    return best


def evaluate(arm, s):
    base = 'runs' if MASK_MODE == 'new' else ('runs_mix' if MASK_MODE == 'mix' else 'runs_oldmask')
    if ENCODING == 'prim':
        base += '_prim'
    if EXTRA:
        base += '_' + EXTRA
    if EPOCHS != 100:
        base += f'_e{EPOCHS}'
    out = H / base / f'seed{s}' / arm
    sel = json.loads((out / 'SELECTED.json').read_text())
    m = model_for(arm, s); m.load_state_dict(torch.load(ROOT / sel['path'], map_location=DEVICE, weights_only=True))
    v = predict(m, 'trans', 'val'); va = arrays('trans', 'val')
    neg = v[va['trusted'] & (va['y'] == 0)]
    threshold = float(np.nextafter(np.quantile(neg, .95), np.inf))
    res = dict(arm=arm, seed=s, selected=sel, threshold=threshold)
    for split in ('val', 'test'):
        scores = v if split == 'val' else predict(m, 'trans', split)
        summary, rows = metrics(scores, 'trans', split, threshold)
        res[split] = summary
        np.save(out / f'{split}_scores.npy', scores)
        with (out / f'{split}_per_view.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    del m; gc.collect(); torch.cuda.empty_cache()
    return res


def main():
    assert torch.cuda.is_available() and 'ginvenv_gpu' in sys.executable
    for s in SEEDS:
        pair = {}
        for arm in ARMS:
            train_arm(arm, s)
            pair[arm] = evaluate(arm, s)
        tag = f'seed{s}_AB'
        if MASK_MODE != 'new':
            tag += '_oldmask'
        if ENCODING != '39':
            tag += '_prim'
        if EXTRA:
            tag += '_' + EXTRA
        if EPOCHS != 100:
            tag += f'_e{EPOCHS}'
        if EQ > 0:
            tag += f'_eq{EQ:g}'
            if EQ_PERM:
                tag += 'p'
        write(H / (tag + '.json'), pair)
        for arm in pair:
            t = pair[arm]['test']['trusted']; l = pair[arm]['test']['legacy']
            print(f"SEED {s} {arm}: test_trusted AP={t['ap']:.4f} AUC={t['auc']:.4f} R@1%={t['r1']:.4f} R@5%={t['r5']:.4f} FPR={t['control_fpr']:.4f} | legacy AP={l['ap']:.4f}", flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
