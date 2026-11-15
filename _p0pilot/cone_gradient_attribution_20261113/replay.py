"""Attribute frozen v5 last-step cone gradients to weighting and aggregation."""
import csv
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'cone_reliability_bounded_20261113'))
from check import bound, CL, F, V5, coverage, digest, flat_grad, mass_stats, np, torch, v5


def write(name, rows):
    with (OUT / name).open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def lookup(data, local_ids):
    names = (v5.R / 'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt'
             ).read_text(encoding='utf-8').splitlines()
    views = sorted(F.views('train').items(), key=lambda p: p[1]['start'])
    starts = np.array([v['start'] for _, v in views])
    result = {}
    for local in local_ids:
        old = int(data['new2old'][local])
        view, lay = views[np.searchsorted(starts, old, side='right')-1]
        assert lay['start'] <= old < lay['physical_stop']
        name_index = lay['old_start'] + old - lay['start']
        assert lay['old_start'] <= name_index < lay['old_stop']
        result[local] = dict(row=old, view=view, node=names[name_index].strip().lstrip('\\'),
                             label=int(data['y'][local]))
    return result


def run(fold, previous):
    data = F.load_trans(fold)
    cov, mean_exp, exposure, meta = coverage(fold, data)
    labels, flat, ptr = (data[k] for k in ('cone_label', 'cone_rows', 'cone_ptr'))
    weights = {}
    for name, raw in [('coverage', np.sqrt(cov)), ('sharing', 1/np.sqrt(mean_exp)),
                      ('both', np.sqrt(cov / mean_exp))]:
        w = np.empty_like(raw)
        for label in (0, 1):
            mask = labels == label
            w[mask] = bound(raw[mask])
        weights[name] = w
    cuda = lambda x: torch.as_tensor(x, device='cuda')
    lab = cuda(labels.astype(np.float32))
    idx = cuda(flat)
    seg = torch.repeat_interleave(torch.arange(len(lab), device='cuda'), cuda(np.diff(ptr)))
    model = v5.Model().cuda()
    checkpoint = V5 / fold / 'NC/last.pt'
    model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cuda'))
    before = digest(model)
    model.train()
    v5.T.seed(241)
    rng = np.random.default_rng(241)
    ids = np.concatenate([data['pos'], rng.choice(data['common_pool'], 8192, replace=False),
                          rng.choice(data['h_pool'], 144, replace=False)]).astype(np.int64)
    log = json.loads((checkpoint.parent / 'LOG.json').read_text(encoding='utf-8'))
    assert F.sha_ids(ids) == log['logs'][199]['trans_sha']
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(cuda(data['x']), cuda(data['edge']))
    margin = CL.margin_of(logits)
    cones = dict(rows=meta, idx=idx, seg=seg, lab=lab)
    hard = CL.cone_score(margin, cones)
    centered = margin[idx] - hard.detach()[seg]
    exp = centered.exp()
    denom = torch.zeros_like(hard).scatter_add_(0, seg, exp)
    smooth = hard.detach() + denom.log() - cuda(np.diff(ptr).astype(np.float32)).log()
    assert torch.all(smooth <= hard + 2e-6)
    # Diagnostic only: hold the forward scores and BCE residuals at hard max.
    soft_backward = hard.detach() + (smooth - smooth.detach())
    assert torch.equal(soft_backward, hard)
    hard_hits = margin[idx] == hard[seg]
    n_ties = torch.bincount(seg[hard_hits], minlength=len(lab))
    hard_dist = hard_hits.float() / n_ties[seg]
    soft_dist = exp / denom[seg]
    params = [p for p in model.parameters() if p.requires_grad]
    stats, signed, incoming, factors = [], {}, {}, {}
    nc_norm = None
    for name, score, dist, key in [
            ('NC', hard, hard_dist, None), ('coverage', hard, hard_dist, 'coverage'),
            ('sharing', hard, hard_dist, 'sharing'), ('both', hard, hard_dist, 'both'),
            ('smooth', smooth, soft_dist, None), ('both_smooth', smooth, soft_dist, 'both'),
            ('soft_backward', soft_backward, soft_dist, None)]:
        pieces = torch.nn.functional.binary_cross_entropy_with_logits(
            score, lab, pos_weight=lab.new_tensor(10.), reduction='none')
        loss = pieces.mean() if key is None else (pieces * cuda(weights[key].astype(np.float32))).mean()
        if name == 'NC':
            assert torch.equal(loss, CL.cone_loss(logits, cones))
        norm = flat_grad(loss, params).norm()
        assert torch.isfinite(norm) and norm > 0
        nc_norm = norm if nc_norm is None else nc_norm
        factor = nc_norm / norm
        g, gs = torch.autograd.grad(loss, (margin, score), retain_graph=True)
        expected = torch.zeros_like(margin).scatter_add_(0, idx, gs[seg] * dist)
        assert torch.allclose(g, expected, atol=1e-7, rtol=1e-4)
        mass = torch.zeros_like(margin).scatter_add_(0, idx, gs[seg].abs() * dist)
        signed[name] = (g * factor).detach().cpu().numpy()
        incoming[name] = (mass * factor).detach().cpu().numpy()
        factors[name] = factor.item()
        metrics = mass_stats(signed[name], exposure)
        unsummed = mass_stats(incoming[name], exposure)
        stats.append(dict(fold=fold, arm=name, scale=factor.item(), norm=(norm*factor).item(),
                          **metrics, incoming_top10=unsummed['top10'], incoming_shared5=unsummed['shared5']))
    for name, previous_key in [('NC', 'nc'), ('both', 'bounded')]:
        cur = next(r for r in stats if r['arm'] == name)
        assert all(abs(cur[k] - previous[previous_key]['net'][k]) < .003
                   for k in ('top10', 'shared5'))
        assert abs(cur['norm'] / previous[previous_key]['norm'] - 1) < .003
    # Deterministic ranking when multiple nodes have equal gradient.
    node_ids = np.arange(len(exposure))
    top = {name: np.lexsort((node_ids, -np.abs(g)))[:10] for name, g in signed.items()}
    focus = sorted(set(top['NC']) | set(top['both']))
    records = lookup(data, focus)
    hit_seg, hit_node = seg[hard_hits].cpu().numpy(), idx[hard_hits].cpu().numpy()
    node_rows, cone_rows = [], []
    for local in focus:
        cids = hit_seg[hit_node == local]
        node_rows.append(dict(fold=fold, **records[local], exposure=int(exposure[local]),
                              winning_cones=len(cids), positive_wins=int(labels[cids].sum()),
                              nc_rank=(list(top['NC']).index(local)+1 if local in top['NC'] else ''),
                              both_rank=(list(top['both']).index(local)+1 if local in top['both'] else ''),
                              **{f'{n}_share': float(abs(g[local])/np.abs(g).sum())
                                 for n, g in signed.items()},
                              **{f'{n}_gradient': float(g[local]) for n, g in signed.items()}))
        for i in cids:
            assert meta[i][0] == records[local]['view']
            cone_rows.append(dict(fold=fold, row=records[local]['row'], view=meta[i][0],
                                  cone=meta[i][1], label=int(labels[i]), coverage=cov[i],
                                  mean_exposure=mean_exp[i], trusted_members=int(ptr[i+1]-ptr[i]),
                                  **{f'{n}_weight': w[i] for n, w in weights.items()}))
    for row in stats:
        g = np.abs(signed[row['arm']])
        row['fixed_nc_top10'] = float(g[top['NC']].sum()/g.sum())
        row['fixed_both_top10'] = float(g[top['both']].sum()/g.sum())
    assert all(before[k] == digest_after for k, digest_after in digest(model).items()
               if k in dict(model.named_parameters()))
    assert all(p.grad is None for p in params)
    model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cuda'))
    assert digest(model) == before
    return stats, node_rows, cone_rows


def main():
    torch.set_num_threads(2)
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    prior = json.loads((P / 'cone_reliability_bounded_20261113/RESULTS.json').read_text(encoding='utf-8'))
    stats, nodes, cones = [], [], []
    for row in prior:
        if row['point'] != 'last':
            continue
        a, b, c = run(row['fold'], row)
        stats.extend(a)
        nodes.extend(b)
        cones.extend(c)
        print(row['fold'], [(r['arm'], round(100*r['top10'], 2), round(100*r['shared5'], 2))
                            for r in a], flush=True)
        torch.cuda.empty_cache()
    write('SUMMARY.csv', stats)
    write('NODES.csv', nodes)
    write('WINNING_CONES.csv', cones)


if __name__ == '__main__':
    main()
