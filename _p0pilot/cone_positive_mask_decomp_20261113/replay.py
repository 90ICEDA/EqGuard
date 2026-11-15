"""Decompose the independent validation D-margin projection at frozen NC states."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

OUT = Path(__file__).resolve().parent
P = OUT.parent
PREV = P / 'cone_positive_mask_20261113'
sys.path.insert(0, str(PREV))
from probe import CL, F, V5, bind_validation, coverage, cuda, digest, flat_grad, np, torch, v5, validation


def load_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def training_vectors(model, train, graph, fold, point):
    path = V5 / fold / 'NC' / f'{point}.pt'
    state = torch.load(path, weights_only=True, map_location='cuda')
    model.load_state_dict(state)
    fingerprint = digest(model)
    log = json.loads((path.parent / 'LOG.json').read_text(encoding='utf-8'))
    step = log['best_step'] if point == 'best' else 200
    rng = np.random.default_rng(41 + step)
    ids = np.concatenate([train['pos'], rng.choice(train['common_pool'], 8192, replace=False),
                          rng.choice(train['h_pool'], 144, replace=False)]).astype(np.int64)
    assert F.sha_ids(ids) == log['logs'][step-1]['trans_sha']
    model.train()
    v5.T.seed(41 + step)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(*graph)
    margin = CL.margin_of(logits)
    labels = cuda(train['cone_label'].astype(np.float32))
    idx = cuda(train['cone_rows'])
    seg = torch.repeat_interleave(torch.arange(len(labels), device='cuda'), cuda(np.diff(train['cone_ptr'])))
    keep = ~((labels[seg] == 1) & cuda(train['y'][train['cone_rows']] == 0))
    assert (torch.bincount(seg[keep], minlength=len(labels)) > 0).all()
    base = CL.cone_loss(logits, dict(rows=labels, idx=idx, seg=seg, lab=labels))
    score = torch.full_like(labels, -1e9).scatter_reduce_(0, seg[keep], margin[idx[keep]],
                                                         reduce='amax', include_self=True)
    masked = torch.nn.functional.binary_cross_entropy_with_logits(
        score, labels, pos_weight=labels.new_tensor(10.))
    params = tuple(model.parameters())
    nc, raw = (flat_grad(loss, params) for loss in (base, masked))
    assert nc.norm() > 0 and raw.norm() > 0 and torch.isfinite(nc).all() and torch.isfinite(raw).all()
    matched = raw * (nc.norm() / raw.norm())
    assert abs((matched.norm()/nc.norm()).item()-1) < 2e-6
    after = digest(model)
    assert all(fingerprint[k] == after[k] for k, _ in model.named_parameters())
    model.load_state_dict(state)
    model.eval()
    assert digest(model) == fingerprint
    return {'nc': nc, 'masked': matched, 'raw': raw}, fingerprint


def validation_endpoints():
    from probe import CACHE, EVIDENCE
    truth = {(r['view'], r['cone_id']): r['status']
             for r in json.loads(EVIDENCE.read_text(encoding='utf-8'))['endpoints']
             if r['split'] == 'val' and r['kind'] == 'D' and r['status'] in ('positive', 'negative')}
    negative = defaultdict(list)
    for r in load_rows(CACHE):
        key = r['view'], r['cone_id']
        if r['split'] == 'val' and truth.get(key) == 'negative':
            negative[r['view']].append((r['cone_id'], np.fromstring(r['phys_rows'], sep='|', dtype=np.int64)))
    assert sum(map(len, negative.values())) == sum(v == 'negative' for v in truth.values())
    return negative


def inspect(model, graph, val, sources, endpoints, vectors, fold, point, prior):
    with torch.autocast('cuda', dtype=torch.bfloat16):
        margin = CL.margin_of(model(*graph))
    params = tuple(model.parameters())
    rows = []
    for source, entries in sources.items():
        for view, recipe, pos, neg, neg_count in entries:
            positive = torch.stack([margin[a].amax() for a in pos]).mean()
            negative = margin[neg].amax()
            gap = positive-negative
            gp, gn, gd = [flat_grad(metric, params) for metric in (positive, negative, gap)]
            row = dict(fold=fold, point=point, source=source, recipe=recipe, view=view,
                       positive_cones=len(pos), negative_cones=neg_count,
                       positive_score=positive.item(), negative_score=negative.item(),
                       top_negative_cones='|'.join(cid for cid, members in endpoints[view]
                                                   if margin[cuda(val['old2new'][members])].amax().item() == negative.item()))
            assert row['top_negative_cones']
            reference = prior[fold, point, view]
            assert abs(gap.item()-float(reference['gap'])) < .02
            for arm, g in vectors.items():
                p, n, direct = [-torch.dot(d, g).item() for d in (gp, gn, gd)]
                assert np.isfinite([p, n, direct]).all()
                row.update({f'{arm}_positive': p, f'{arm}_negative': n,
                            f'{arm}_split_gap': p-n, f'{arm}_gap': direct,
                            f'{arm}_residual': direct-(p-n)})
            for field in ('positive', 'negative', 'gap', 'split_gap'):
                row[f'delta_{field}'] = row[f'masked_{field}']-row[f'nc_{field}']
            rows.append(row)
    assert all(p.grad is None for p in params)
    return rows


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    evidence, endpoints = validation(), validation_endpoints()
    prior = {(r['fold'], r['point'], r['view']): r for r in load_rows(PREV / 'VALIDATION_BY_VIEW.csv')}
    rows = []
    for fold, point in [('ys_abc', 'last'), ('ys_nand', 'best')]:
        train, val = F.load_trans(fold), F.load_trans(fold, 'val')
        _, _, _, meta = coverage(fold, train)
        sources = bind_validation(fold, val, evidence)
        assert len(sources) == 5 and not set(sources) & {v.rsplit('__ys_', 1)[0].split('__keep')[0] for v, _ in meta}
        assert train['trusted'][train['cone_rows']].all() and train['physical'][train['cone_rows']].all()
        model = v5.Model().cuda()
        vectors, fingerprint = training_vectors(model, train, (cuda(train['x']), cuda(train['edge'])), fold, point)
        rows.extend(inspect(model, (cuda(val['x']), cuda(val['edge'])), val, sources, endpoints,
                            vectors, fold, point, prior))
        assert digest(model) == fingerprint
        print('DONE', fold, point, flush=True)
    assert len(rows) == 40
    write('BY_VIEW.csv', rows)
    groups = defaultdict(list)
    for r in rows:
        groups[r['fold'], r['point'], r['source']].append(r)
    summary = []
    keys = [k for k in rows[0] if k.startswith(('nc_', 'masked_', 'raw_', 'delta_'))]
    for (fold, point, source), rr in groups.items():
        row = dict(fold=fold, point=point, source=source, views=len(rr),
                   **{k: mean(r[k] for r in rr) for k in keys})
        print(fold, source, *(round(row[k], 5) for k in ('delta_positive', 'delta_negative', 'delta_gap')), flush=True)
        summary.append(row)
    write('BY_SOURCE.csv', summary)


if __name__ == '__main__':
    main()
