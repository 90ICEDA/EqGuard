"""Round 21A preflight: row alignment, folds, feature masks, one FP32 update."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from build_features import FAMILIES, OUT, R18, sha_file, write_json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.gin_net import GINNodeClassifier


def state_sha(state):
    h = hashlib.sha256()
    for key, value in sorted(state.items()):
        h.update(key.encode())
        h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def main():
    torch.set_num_threads(4)
    if not torch.cuda.is_available():
        raise RuntimeError('GPU required; no CPU fallback')
    protocol = json.loads((OUT / 'protocol.json').read_text(encoding='utf-8'))
    folds = json.loads((OUT / 'folds.json').read_text(encoding='utf-8'))
    fz = np.load(OUT / 'features.npz')
    b = np.load(R18 / 'base_inputs.npz')
    rec = json.loads((R18 / 'records.json').read_text(encoding='utf-8'))
    family = fz['family']
    assert len(family) == len(b['global_ids']) == 2435
    assert set(family.tolist()) == set(FAMILIES)
    for key, path in [('features', OUT / 'features.npz'), ('folds', OUT / 'folds.json')]:
        assert sha_file(path) == protocol['hashes'][key]
    for key in ('metadata', 'real', 'permuted'):
        assert fz[key].shape == (2435, 114) and np.isfinite(fz[key]).all()
    meta = fz['metadata']
    assert np.all(meta[:, :80] == 0) and np.all(meta[:, 98:110] == 0)
    assert np.all(meta[:, 96] >= 0) and np.all(meta[:, 96] <= 1)
    changed = int((np.abs(fz['real'] - fz['permuted']).max(1) > 0).sum())
    assert changed > 0
    covered = fz['real'][:, 97] > 0
    assert int(covered.sum()) == 2291
    assert np.all(fz['real'][~covered][:, :98] == 0)
    assert np.all(fz['permuted'][~covered][:, :98] == 0)

    # Only train/val labels are read before model selection.
    g = torch.load(ROOT / 'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt',
                   map_location='cpu', weights_only=False, mmap=True)
    y_all = g.y
    ids_all = b['global_ids']
    fold_check = []
    for f in folds['folds']:
        sets = [set(f[k]) for k in ('train_indices', 'val_indices', 'test_indices')]
        assert not sets[0] & sets[1] and not sets[0] & sets[2] and not sets[1] & sets[2]
        assert len(sets[0] | sets[1] | sets[2]) == 2435
        ytr = y_all[torch.tensor(ids_all[f['train_indices']])].numpy().astype(int)
        yva = y_all[torch.tensor(ids_all[f['val_indices']])].numpy().astype(int)
        assert ytr.sum() > 0 and yva.sum() > 0
        fold_check.append(dict(fold=f['fold'], train_families=f['train_families'],
                               val_families=f['val_families'], test_families=f['test_families'],
                               train_nodes=len(f['train_indices']), val_nodes=len(f['val_indices']),
                               test_nodes=len(f['test_indices']),
                               train_positives=int(ytr.sum()), val_positives=int(yva.sum()),
                               test_labels_read=False))

    f = folds['folds'][0]
    tr = np.asarray(f['train_indices'])
    x = b['x'].astype(np.float32)
    mu = x[tr].mean(0, keepdims=True)
    sd = x[tr].std(0, keepdims=True, ddof=1).clip(1e-6)
    base = np.nan_to_num((x - mu) / sd).clip(-10, 10).astype(np.float32)
    edges = b['edge_index']
    rev = np.full(2435, -1, np.int64)
    rev[tr] = np.arange(len(tr))
    keep = np.isin(edges[0], tr) & np.isin(edges[1], tr)
    edge = torch.tensor(rev[edges[:, keep]], dtype=torch.long, device='cuda')
    xtr = torch.tensor(np.concatenate([base[tr], fz['metadata'][tr]], 1), device='cuda')
    ytr = y_all[torch.tensor(ids_all[tr])].to('cuda')
    weight = torch.tensor([1.0, float((ytr == 0).sum()) / float((ytr == 1).sum())], device='cuda')

    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(42)
    np.random.seed(42)
    model = GINNodeClassifier(39 + 114, 64, 2, num_layers=4).cuda()
    init = state_sha(model.state_dict())
    model.train()
    logits = model(xtr, edge)
    loss = F.cross_entropy(logits, ytr, weight=weight)
    loss.backward()
    grads = [p.grad for p in model.parameters() if p.grad is not None]
    finite = bool(torch.isfinite(loss) and all(torch.isfinite(g).all() for g in grads))
    assert finite
    model.eval()
    with torch.no_grad():
        p1 = torch.softmax(model(xtr, edge).float(), 1)[:, 1].cpu().numpy()
        p2 = torch.softmax(model(xtr, edge).float(), 1)[:, 1].cpu().numpy()
    repeat = float(np.max(np.abs(p1 - p2)))
    assert repeat <= 1e-6
    out = dict(status='preflight_passed', protocol_sha=sha_file(OUT / 'protocol.json'),
               data_rows=2435, covered=2291, width=114, arms=protocol['arms'],
               folds=fold_check, init_sha=init, loss=float(loss.detach()),
               grad_finite=finite, repeat_max_abs=repeat, device=torch.cuda.get_device_name(0),
               precision='float32', amp=False, deterministic=True,
               train_labels_only=True, test_labels_read=False)
    write_json(OUT / 'preflight.json', out)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
