"""Frozen NC audit of trusted-negative winners in weak-positive D cones."""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'cone_reliability_20261113'))
from check_grad import CL, F, V5, coverage, digest, flat_grad, np, torch, v5

CACHE = P / 'seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'
EVIDENCE = P / 'lcone_endpoint_frozen_20261112/EVIDENCE.json'


def write(name, rows):
    with (OUT / name).open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def cuda(a):
    return torch.as_tensor(a, device='cuda')


def identity(view):
    prefix, recipe = view.rsplit('__ys_', 1)
    return prefix.split('__keep', 1)[0], recipe


def validation():
    labels = {}
    for r in json.loads(EVIDENCE.read_text(encoding='utf-8'))['endpoints']:
        if r['split'] == 'val' and r['kind'] == 'D' and r['status'] in ('positive', 'negative'):
            key = r['view'], r['cone_id']
            assert key not in labels
            labels[key] = r['status']
    by_view = defaultdict(lambda: defaultdict(list))
    with CACHE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            key = r['view'], r['cone_id']
            if r['split'] == 'val' and key in labels:
                a = np.fromstring(r['phys_rows'], sep='|', dtype=np.int64)
                assert len(a) == int(r['n_phys']) > 0 and np.all(np.diff(a) > 0)
                by_view[r['view']][labels.pop(key)].append(a)
    assert not labels
    return by_view


def bind_validation(fold, val, evidence):
    sources = defaultdict(list)
    layouts = F.views('val')
    for view, groups in sorted(evidence.items()):
        if view.endswith('__' + fold) or not (groups['positive'] and groups['negative']):
            continue
        layout = layouts[view]
        mapping = val['old2new']
        assert (mapping[layout['start']:layout['stop']] >= 0).all()
        pos = groups['positive']
        neg = np.unique(np.concatenate(groups['negative']))
        for a in (*pos, neg):
            assert ((a >= layout['start']) & (a < layout['physical_stop'])).all()
            assert val['physical'][mapping[a]].all()
            assert np.array_equal(val['new2old'][mapping[a]], a)
        source, recipe = identity(view)
        sources[source].append((view, recipe, [cuda(mapping[a]) for a in pos], cuda(mapping[neg]),
                                len(groups['negative'])))
    assert sources
    return sources


def inspect(fold, point, score, masked, margin, cones, neg_member, pos_member, train):
    labels = cones['lab']
    idx, seg = cones['idx'], cones['seg']
    is_pos = labels[seg] == 1
    at_max = (margin[idx] == score[seg]) & is_pos
    neg_wins = torch.bincount(seg[at_max & neg_member], minlength=len(labels)).cpu().numpy()
    pos_wins = torch.bincount(seg[at_max & pos_member], minlength=len(labels)).cpu().numpy()
    total_wins = torch.bincount(seg[at_max], minlength=len(labels)).cpu().numpy()
    pos_rows = np.flatnonzero(train['cone_label'] == 1)
    assert np.all(total_wins[pos_rows] == (neg_wins + pos_wins)[pos_rows])
    base, new = (a.detach().cpu().numpy() for a in (score, masked))
    outcomes = []
    for i in pos_rows:
        view, cone = cones['rows'][i]
        source, recipe = identity(view)
        status = 'negative_only' if neg_wins[i] and not pos_wins[i] else (
            'mixed_tie' if neg_wins[i] else 'positive_only')
        assert (new[i] < base[i]) == (status == 'negative_only')
        outcomes.append(dict(fold=fold, point=point, source=source, recipe=recipe, view=view, cone=cone,
                             outcome=status, neg_winners=int(neg_wins[i]), pos_winners=int(pos_wins[i]),
                             old_score=float(base[i]), masked_score=float(new[i])))
    return outcomes


def probe(fold, point, model, train, train_gpu, val_gpu, sources, cones):
    path = V5 / fold / 'NC' / f'{point}.pt'
    log = json.loads((path.parent / 'LOG.json').read_text(encoding='utf-8'))
    step = log['best_step'] - 1 if point == 'best' else 199
    state = torch.load(path, weights_only=True, map_location='cuda')
    model.load_state_dict(state)
    before = digest(model)
    params = tuple(model.parameters())
    rng = np.random.default_rng(42 + step)
    ids = np.concatenate([train['pos'], rng.choice(train['common_pool'], 8192, replace=False),
                          rng.choice(train['h_pool'], 144, replace=False)]).astype(np.int64)
    assert F.sha_ids(ids) == log['logs'][step]['trans_sha']
    model.train()
    v5.T.seed(42 + step)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(*train_gpu)
    margin = CL.margin_of(logits)
    lab, seg, idx = (cones[k] for k in ('lab', 'seg', 'idx'))
    neg_member = cuda(train['y'][train['cone_rows']] == 0)
    pos_member = cuda(train['y'][train['cone_rows']] == 1)
    in_positive = lab[seg] == 1
    keep = ~(in_positive & neg_member)
    assert torch.all(torch.bincount(seg[keep], minlength=len(lab)) > 0)
    assert not (in_positive & keep & ~pos_member).any()
    score = CL.cone_score(margin, cones)
    masked = torch.full_like(score, -1e9).scatter_reduce_(
        0, seg[keep], margin[idx[keep]], reduce='amax', include_self=True)
    assert torch.equal(masked[lab == 0], score[lab == 0])
    train_rows = inspect(fold, point, score, masked, margin, cones, neg_member, pos_member, train)
    loss = CL.cone_loss(logits, cones)
    new_loss = torch.nn.functional.binary_cross_entropy_with_logits(
        masked, lab, pos_weight=lab.new_tensor(10.))
    g0 = flat_grad(loss, params)
    g1 = flat_grad(new_loss, params)
    assert g0.norm() > 0 and g1.norm() > 0 and torch.isfinite(g0).all() and torch.isfinite(g1).all()
    ratio = g0.norm() / g1.norm()
    match = g1 * ratio
    assert abs((match.norm() / g0.norm()).item()-1) < 2e-6
    assert all(before[k] == value for k, value in digest(model).items()
               if k in dict(model.named_parameters()))
    model.load_state_dict(state)
    model.eval()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        vmargin = CL.margin_of(model(*val_gpu))
    projections = []
    for source, entries in sources.items():
        for view, recipe, pos, neg, neg_count in entries:
            gap = torch.stack([vmargin[a].amax() for a in pos]).mean() - vmargin[neg].amax()
            gradient = flat_grad(gap, params)
            assert torch.isfinite(gradient).all()
            base = -torch.dot(gradient, g0).item()
            changed = -torch.dot(gradient, match).item()
            projections.append(dict(fold=fold, point=point, source=source, recipe=recipe, view=view,
                                    positive=len(pos), negative=neg_count, gap=gap.item(),
                                    nc=base, masked=changed, delta=changed-base,
                                    masked_raw=-torch.dot(gradient, g1).item()))
    assert digest(model) == before and all(p.grad is None for p in params)
    meta = dict(fold=fold, point=point, step=step+1, nc_norm=g0.norm().item(),
                masked_raw_norm=g1.norm().item(), masked_matched_norm=match.norm().item(),
                nc_loss=loss.item(), masked_loss=new_loss.item(),
                gradient_cosine=torch.nn.functional.cosine_similarity(g0, match, dim=0).item(),
                masked_entries=int((~keep).sum().item()))
    return train_rows, projections, meta


def mean(xs):
    return sum(xs) / len(xs)


def summarize(train, validation):
    counts = defaultdict(Counter)
    for r in train:
        for s, recipe in [(r['source'], r['recipe']), ('all', r['recipe']), ('all', 'all')]:
            counts[r['fold'], r['point'], s, recipe][r['outcome']] += 1
    outcomes = ['negative_only', 'mixed_tie', 'positive_only']
    buckets = [dict(fold=f, point=p, source=s, recipe=r, total=sum(c.values()),
                    **{k: c[k] for k in outcomes}) for (f,p,s,r), c in sorted(counts.items())]
    vals = defaultdict(list)
    for r in validation:
        vals[r['fold'], r['point'], r['source']].append(r)
    vs = [dict(fold=f, point=p, source=s, views=len(rr),
               **{k: mean([r[k] for r in rr]) for k in ('nc', 'masked', 'delta', 'masked_raw')})
          for (f,p,s), rr in sorted(vals.items())]
    for r in buckets:
        if r['source'] == r['recipe'] == 'all':
            subset = [a for a in vs if (a['fold'], a['point']) == (r['fold'], r['point'])]
            print(r, [(k, round(mean([s[k] for s in subset]), 6), sum(s[k] > 0 for s in subset))
                      for k in ('nc', 'masked', 'delta')], flush=True)
    return buckets, vs


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    evidence = validation()
    tr, va, diagnostic = [], [], []
    for fold in F.RECIPES:
        train, val = F.load_trans(fold), F.load_trans(fold, 'val')
        _, _, _, meta = coverage(fold, train)
        assert train['trusted'][train['cone_rows']].all() and train['physical'][train['cone_rows']].all()
        sources = bind_validation(fold, val, evidence)
        assert not set(sources) & {identity(v)[0] for v, _ in meta}
        cones = dict(rows=meta, idx=cuda(train['cone_rows']),
                     seg=torch.repeat_interleave(torch.arange(len(meta), device='cuda'),
                                                 cuda(np.diff(train['cone_ptr']))),
                     lab=cuda(train['cone_label'].astype(np.float32)))
        train_gpu, val_gpu = [(cuda(d['x']), cuda(d['edge'])) for d in (train, val)]
        model = v5.Model().cuda()
        for point in ('best', 'last'):
            a,b,c = probe(fold, point, model, train, train_gpu, val_gpu, sources, cones)
            tr.extend(a)
            va.extend(b)
            diagnostic.append(c)
            print('DONE', fold, point, flush=True)
        del train_gpu, val_gpu, model, sources, cones
        torch.cuda.empty_cache()
    counts, sources = summarize(tr, va)
    for filename, rows in [('TRAIN_CONES.csv', tr), ('TRAIN_BY_SOURCE_RECIPE.csv', counts),
                           ('VALIDATION_BY_VIEW.csv', va), ('VALIDATION_BY_SOURCE.csv', sources),
                           ('GRADIENTS.csv', diagnostic)]:
        write(filename, rows)


if __name__ == '__main__':
    main()
