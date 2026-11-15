"""Train-fold-only reliability weights and no-update v5 gradient check."""
import csv
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
V5 = P / 'heldout_recipe_v5_20261109'
sys.path.insert(0, str(V5))
import train_v5 as v5

np, torch, F, CL = v5.np, v5.torch, v5.F, v5.CL


def coverage(fold, data):
    layouts = F.views('train')
    ptr = data['cone_ptr']
    flat = data['cone_rows']
    support, meta = [], []
    i = 0
    with (P / 'seed42_supervised_prep_20261109/CONE_CACHE_V2.csv').open(
            encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if (row['split'] != 'train' or row['kind'] != 'D' or int(row['label']) < 0
                    or int(row['n_phys']) < 2):
                continue
            view = row['view']
            if view.endswith('__' + fold):
                continue
            lay = layouts[view]
            physical = np.fromstring(row['phys_rows'], dtype=np.int64, sep='|')
            assert len(physical) == int(row['n_phys']) and np.all(
                (physical >= lay['start']) & (physical < lay['physical_stop']))
            local = data['old2new'][physical]
            if (local < 0).all():
                continue
            assert (local >= 0).all() and data['physical'][local].all()
            assert np.array_equal(data['new2old'][local], physical)
            trusted = local[data['trusted'][local]]
            if len(trusted) < 2:
                continue
            assert np.array_equal(trusted, flat[ptr[i]:ptr[i + 1]])
            assert int(row['label']) == data['cone_label'][i]
            support.append(len(trusted) / len(physical))
            meta.append((view, row['cone_id']))
            i += 1
    assert i == len(data['cone_label']) and len(set(meta)) == i
    exposure = np.bincount(flat, minlength=len(data['y']))
    mean_exposure = np.add.reduceat(exposure[flat], ptr[:-1]) / np.diff(ptr)
    return np.asarray(support), mean_exposure, exposure, meta


def digest(model):
    return {k: hashlib.sha256(x.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
            for k, x in model.state_dict().items()}


def mass_stats(g, exposure):
    mass = np.abs(g)
    total = mass.sum(dtype=np.float64)
    assert total > 0 and np.isfinite(mass).all()
    vals = np.sort(mass[mass > 0].astype(np.float64))[::-1]
    return dict(active=len(vals), top1=vals[0]/total, top10=vals[:10].sum()/total,
                top1pct=vals[:max(1, int(np.ceil(.01*len(vals))))].sum()/total,
                effective=total**2/np.square(vals).sum(),
                shared2=mass[exposure >= 2].sum(dtype=np.float64)/total,
                shared5=mass[exposure >= 5].sum(dtype=np.float64)/total,
                l1=total)


def flat_grad(loss, params):
    return torch.cat([g.flatten() if g is not None else torch.zeros_like(p).flatten()
                      for p, g in zip(params, torch.autograd.grad(
                          loss, params, retain_graph=True, allow_unused=True))])


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    loader = v5.FiveGroupLoader()
    v5.T.CONTRACT, v5.T.NORM, v5.T.arrays = loader.feature_contract, loader.normalization, loader.arrays
    results = []
    weight_rows = []
    for fold in F.RECIPES:
        data = F.load_trans(fold)
        cov, mean_exp, exposure, meta = coverage(fold, data)
        labels = data['cone_label']
        raw = np.sqrt(cov / mean_exp)
        weights = raw.copy()
        for label in (0, 1):
            m = labels == label
            assert m.any()
            weights[m] /= weights[m].mean()
            assert np.isclose(weights[m].sum(), m.sum())
        for (view, cone_id), label, c, e, w in zip(meta, labels, cov, mean_exp, weights):
            weight_rows.append(dict(fold=fold, view=view, cone_id=cone_id, label=int(label),
                                    trusted_coverage=c, mean_exposure=e, weight=w))
        ptr = data['cone_ptr']
        idx = torch.as_tensor(data['cone_rows'], device='cuda')
        seg = torch.repeat_interleave(torch.arange(len(labels), device='cuda'),
                                      torch.as_tensor(np.diff(ptr), device='cuda'))
        lab = torch.as_tensor(labels, dtype=torch.float32, device='cuda')
        w = torch.as_tensor(weights, dtype=torch.float32, device='cuda')
        x = torch.as_tensor(data['x'], device='cuda')
        edges = torch.as_tensor(data['edge'], device='cuda')
        y = torch.as_tensor(data['y'], device='cuda')
        log = json.loads((V5 / fold / 'NC/LOG.json').read_text(encoding='utf-8'))
        points = [('init', v5.R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', 0),
                  ('best', V5 / fold / 'NC/best.pt', log['best_step'] - 1),
                  ('last', V5 / fold / 'NC/last.pt', 199)]
        for point, checkpoint, step in points:
            model = v5.Model().cuda()
            model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cuda'))
            before = digest(model)
            v5.T.seed(42 + step)
            model.train()
            rng = np.random.default_rng(42 + step)
            ids = np.concatenate([data['pos'], rng.choice(data['common_pool'], 8192, replace=False),
                                  rng.choice(data['h_pool'], 144, replace=False)]).astype(np.int64)
            assert F.sha_ids(ids) == log['logs'][step]['trans_sha']
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(x, edges)
                node_loss = v5.T.domain_loss(logits, y, torch.as_tensor(ids, device='cuda'))
            margin = CL.margin_of(logits)
            cones = dict(rows=meta, seg=seg, idx=idx, lab=lab)
            score = CL.cone_score(margin, cones)
            pieces = torch.nn.functional.binary_cross_entropy_with_logits(
                score, lab, pos_weight=lab.new_tensor(10.), reduction='none')
            base, weighted = pieces.mean(), (pieces * w).mean()
            assert torch.equal(base, CL.cone_loss(logits, cones))
            params = [p for p in model.parameters() if p.requires_grad]
            ng = flat_grad(node_loss, params)
            bg = flat_grad(base, params)
            wg = flat_grad(weighted, params)
            winner = margin[idx] == score[seg]
            ties = torch.bincount(seg[winner], minlength=len(labels))
            assert (ties >= 1).all()
            metrics = {}
            for name, loss, g in [('NC', base, bg), ('weighted', weighted, wg)]:
                gm, gs = torch.autograd.grad(loss, (margin, score), retain_graph=True)
                incoming = torch.zeros_like(margin).scatter_add_(
                    0, idx[winner], gs.abs()[seg[winner]] / ties[seg[winner]])
                assert all(torch.isfinite(t).all() for t in (ng, bg, wg, gm, incoming))
                assert g.norm() > 0 and ng.norm() > 0
                assert torch.all(gm.abs() <= incoming + 1e-7)
                metrics[name] = dict(loss=loss.item(), param_norm=g.norm().item(),
                                     node_ratio=(g.norm()/ng.norm()).item(),
                                     cosine_with_node=torch.nn.functional.cosine_similarity(g, ng, dim=0).item(),
                                     net=mass_stats(gm.detach().cpu().numpy(), exposure),
                                     incoming=mass_stats(incoming.detach().cpu().numpy(), exposure))
            after = digest(model)
            param_names = set(dict(model.named_parameters()))
            assert all(before[k] == after[k] for k in param_names)
            model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cuda'))
            assert digest(model) == before and all(p.grad is None for p in params)
            results.append(dict(fold=fold, point=point, step=step+1,
                                positive=int(labels.sum()), negative=int((labels == 0).sum()),
                                coverage_median=float(np.median(cov)),
                                mean_exposure_median=float(np.median(mean_exp)),
                                max_exposure=int(exposure.max()),
                                weight_range=[weights.min(), weights.max()],
                                cosine_NC_weighted=torch.nn.functional.cosine_similarity(bg, wg, dim=0).item(),
                                **metrics))
            print(fold, point, metrics['NC']['net']['top10'], metrics['weighted']['net']['top10'], flush=True)
            del model, params, ng, bg, wg, gm, gs, incoming, logits, margin, score, pieces, base, weighted, node_loss
        del x, edges, y, idx, seg, lab, w
        torch.cuda.empty_cache()
    (OUT / 'GRAD.json').write_text(json.dumps(results, indent=2, allow_nan=False), encoding='utf-8')
    with (OUT / 'WEIGHTS.csv').open('w', encoding='utf-8', newline='') as f:
        wcsv = csv.DictWriter(f, fieldnames=list(weight_rows[0]))
        wcsv.writeheader()
        wcsv.writerows(weight_rows)


if __name__ == '__main__':
    main()
