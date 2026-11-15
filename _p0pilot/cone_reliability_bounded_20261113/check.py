"""Bound reliability weights and compare cone gradients at frozen NC states."""
import csv
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent / 'cone_reliability_20261113'))
from check_grad import CL, F, V5, coverage, digest, flat_grad, mass_stats, np, torch, v5

LOW, HIGH = 0.5, 1.5


def bound(raw):
    """Scale then clip, keeping mean one and both hard bounds."""
    lo, hi = 0.0, HIGH / raw.min()
    for _ in range(60):
        scale = (lo + hi) / 2
        if np.clip(scale * raw, LOW, HIGH).mean() < 1:
            lo = scale
        else:
            hi = scale
    result = np.clip(((lo + hi) / 2) * raw, LOW, HIGH)
    assert abs(result.mean() - 1) < 1e-12
    return result


def direction(fold, point, data, cache, log, exposure):
    checkpoint = V5 / fold / 'NC' / f'{point}.pt'
    step = log['best_step'] - 1 if point == 'best' else 199
    model = v5.Model().cuda()
    model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cuda'))
    before = digest(model)
    v5.T.seed(42 + step)
    model.train()
    x, edges, labels, cones, weight = cache
    rng = np.random.default_rng(42 + step)
    ids = np.concatenate([data['pos'], rng.choice(data['common_pool'], 8192, replace=False),
                          rng.choice(data['h_pool'], 144, replace=False)]).astype(np.int64)
    assert F.sha_ids(ids) == log['logs'][step]['trans_sha']
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(x, edges)
        node = v5.T.domain_loss(logits, labels, torch.as_tensor(ids, device='cuda'))
    margin = CL.margin_of(logits)
    score = CL.cone_score(margin, cones)
    lab, seg, idx = (cones[k] for k in ('lab', 'seg', 'idx'))
    pieces = torch.nn.functional.binary_cross_entropy_with_logits(
        score, lab, pos_weight=lab.new_tensor(10.), reduction='none')
    nc, weighted = pieces.mean(), (pieces * weight).mean()
    assert torch.equal(nc, CL.cone_loss(logits, cones))
    params = [p for p in model.parameters() if p.requires_grad]
    g_node = flat_grad(node, params)
    g_nc = flat_grad(nc, params)
    g_raw = flat_grad(weighted, params)
    assert g_nc.norm() > 0 and g_raw.norm() > 0 and g_node.norm() > 0
    scale = (g_nc.norm() / g_raw.norm()).detach()
    # Match the cone gradient after the BF16 backward, in FP32 parameter space.
    g_matched = scale * g_raw
    assert abs((g_matched.norm() / g_nc.norm()).item() - 1) < 2e-6
    winner = margin[idx] == score[seg]
    ties = torch.bincount(seg[winner], minlength=len(lab))
    assert (ties > 0).all()
    result = dict(fold=fold, point=point, step=step+1, scale=scale.item(),
                  raw_norm=g_raw.norm().item(), node_norm=g_node.norm().item(),
                  effective_weight_min=scale.item()*LOW, effective_weight_max=scale.item()*HIGH)
    for name, loss, g, factor in [('nc', nc, g_nc, 1.), ('bounded', weighted, g_matched, scale)]:
        gm, gs = torch.autograd.grad(loss, (margin, score), retain_graph=True)
        gm, gs = gm * factor, gs * factor
        incoming = torch.zeros_like(margin).scatter_add_(
            0, idx[winner], gs.abs()[seg[winner]] / ties[seg[winner]])
        assert all(torch.isfinite(t).all() for t in (gm, incoming, g))
        assert torch.all(gm.abs() <= incoming + 1e-7)
        result[name] = dict(norm=g.norm().item(),
                            net=mass_stats(gm.detach().cpu().numpy(), exposure),
                            incoming=mass_stats(incoming.detach().cpu().numpy(), exposure),
                            cosine_with_node=torch.nn.functional.cosine_similarity(g, g_node, dim=0).item())
    after = digest(model)
    assert all(before[k] == after[k] for k, _ in model.named_parameters())
    assert all(p.grad is None for p in params)
    model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cuda'))
    assert digest(model) == before
    return result


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    previous = json.loads((OUT.parent / 'cone_reliability_20261113/GRAD.json').read_text(encoding='utf-8'))
    by_key = {(row['fold'], row['point']): row['NC'] for row in previous}
    loader = v5.FiveGroupLoader()
    v5.T.CONTRACT, v5.T.NORM, v5.T.arrays = loader.feature_contract, loader.normalization, loader.arrays
    results, weights = [], []
    for fold in F.RECIPES:
        data = F.load_trans(fold)
        cov, mean_exp, exposure, meta = coverage(fold, data)
        labels = data['cone_label']
        raw = np.sqrt(cov / mean_exp)
        w = np.empty_like(raw)
        for label in (0, 1):
            m = labels == label
            w[m] = bound(raw[m])
        weights.extend(dict(fold=fold, view=view, cone_id=cone, label=int(label), weight=float(value))
                       for (view, cone), label, value in zip(meta, labels, w))
        cuda = lambda x: torch.as_tensor(x, device='cuda')
        cones = dict(rows=meta, idx=cuda(data['cone_rows']),
                     seg=torch.repeat_interleave(torch.arange(len(labels), device='cuda'),
                                                 cuda(np.diff(data['cone_ptr']))),
                     lab=cuda(labels.astype(np.float32)))
        cache = (cuda(data['x']), cuda(data['edge']), cuda(data['y']), cones, cuda(w.astype(np.float32)))
        log = json.loads((V5 / fold / 'NC/LOG.json').read_text(encoding='utf-8'))
        for point in ('best', 'last'):
            row = direction(fold, point, data, cache, log, exposure)
            ref = by_key[fold, point]
            row['prior_nc'] = dict(norm=ref['param_norm'], top10=ref['net']['top10'],
                                   shared5=ref['net']['shared5'])
            print('NC replay', fold, point, row['nc']['norm'], ref['param_norm'],
                  row['nc']['net']['top10'], ref['net']['top10'], flush=True)
            results.append(row)
            print(fold, point, row['scale'], *(round(100 * row[a]['net'][m], 3)
                  for m in ('top10', 'shared5') for a in ('nc', 'bounded')), flush=True)
        del cache, cones
        torch.cuda.empty_cache()
    (OUT / 'RESULTS.json').write_text(json.dumps(results, indent=2, allow_nan=False), encoding='utf-8')
    with (OUT / 'WEIGHTS.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(weights[0]))
        writer.writeheader()
        writer.writerows(weights)


if __name__ == '__main__':
    main()
