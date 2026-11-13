"""Probe frozen training gradients and held-out score-gap derivatives without updates."""
import itertools
import sys

import numpy as np
import torch
import torch.nn.functional as F

from audit import OUT, P, load_module, read, sha, write_json
from diagnose_pilot import FOLD, load_cases
from pilot_preflight import ACTIVE_STEPS, cone_terms, grad_vector, maximum_rows
from run_pilot import ARMS, CONTRACT, RUNS, cuda_graph

TARGETS = {'gamma_gap': ('injgamma_d1_s42', 'D:DFF_1100_Q_reg', 'D:DFF_304_Q_reg'),
           'delta_gap': ('injdelta_d1_s42', 'D:DFF_679_Q_reg', 'D:DFF_107_Q_reg')}


def margin(logits):
    return logits.float()[:, 1] - logits.float()[:, 0]


def main():
    contract = read(CONTRACT)['folds'][FOLD]
    mechanism = read(OUT / 'PILOT_MECHANISM.json')
    assert mechanism['margins_sha256'] == sha(OUT / 'PILOT_TEST_MARGINS.npz')
    io, test, cases = load_cases()
    module = load_module('pilot_model', P / 'control_best200_20261104/evaluate.py')
    sys.path.insert(0, str(P / 'control_loader_po_20261105'))
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    model = module.Model().cuda()
    params = tuple(model.parameters())
    train = io.load_trans(FOLD)
    x, edge, y = cuda_graph(train)
    xo, eo, yo = cuda_graph(io.load_orig('train', train['mean'], train['std']))
    xt, et = (torch.as_tensor(test[k], device='cuda') for k in ('x', 'edge'))
    step = ACTIVE_STEPS[-1]
    ids_o = np.array(loader.step('orig', 'G0', step).indices, copy=True)
    ids_t, _ = io.step_indices(FOLD, step)
    batch_ids = contract['schedule'][str(step)]
    pairs = [contract['pool'][i] for i in batch_ids]
    weights = contract['initial_gradient_matched_weights']
    data = []
    for point, arm in itertools.product(('best', 'last'), ARMS):
        run = RUNS / FOLD / arm
        path = run / f'{point}.pt'
        history = read(run / 'LOG.json')
        assert history['checkpoints'][path.name] == sha(path)
        assert history['logs'][step]['sample_sha256'] == [io.sha_ids(ids_o), io.sha_ids(ids_t)]
        assert history['logs'][step]['pairs'] == (batch_ids if arm != 'N' else [])
        state = torch.load(path, map_location='cpu', weights_only=True)
        model.load_state_dict(state, strict=True)
        module.T.seed(42 + step)
        model.train()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = module.T.domain_loss(model(xo, eo), yo, torch.as_tensor(ids_o, device='cuda'))
        og = grad_vector(lo, params)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(x, edge)
            lt = module.T.domain_loss(logits, y, torch.as_tensor(ids_t, device='cuda'))
        mt = margin(logits)
        bce, rank = cone_terms(mt, pairs)
        gb = grad_vector(bce*weights['bce'], params, retain=True)
        gr = grad_vector(rank*weights['rank'], params, retain=True)
        gn = og + grad_vector(lt, params)
        grads = {'node': gn, 'bce': gb, 'rank': gr}
        assert all(torch.isfinite(g).all() for g in grads.values())
        pair_info = []
        values = mt.detach().cpu().numpy()
        for p in pairs:
            pr, nr = (np.array(p[k]) for k in ('pos_rows', 'neg_rows'))
            pm, nm = (set(maximum_rows(values, a)) for a in (pr, nr))
            pair_info.append(dict(source=p['source'], positive=p['positive'], negative=p['negative'],
                                  positive_score=float(values[pr].max()), negative_score=float(values[nr].max()),
                                  positive_max=sorted(pm), negative_max=sorted(nm), shared_max=len(pm & nm)))
        model.load_state_dict(state, strict=True)
        model.eval()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            mh = margin(model(xt, et))
        projections = {}
        for i, (tag, (source, p, n)) in enumerate(TARGETS.items()):
            pg, ng = (cases[source][k][1] for k in (p, n))
            gap = mh[pg].amax() - mh[ng].amax()
            dg = grad_vector(gap, params, retain=(i+1 < len(TARGETS)))
            projections[tag] = dict(score_gap=gap.detach().item(), gradient_norm=dg.norm().item(),
                                    local_gap_derivative={k: -torch.dot(dg, g).item() for k, g in grads.items()})
        assert all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
        assert all(p.grad is None for p in params)
        row = dict(point=point, arm=arm, weighted_grad_norm={k: g.norm().item() for k, g in grads.items()},
                   gradient_cosine={f'{a}/{b}': F.cosine_similarity(grads[a], grads[b], dim=0).item()
                                    for a, b in itertools.combinations(grads, 2)},
                   training_pairs=pair_info, projections=projections, checkpoint_sha256=sha(path))
        print(point, arm, row['weighted_grad_norm'], row['gradient_cosine'], projections, flush=True)
        data.append(row)
    write_json(OUT / 'PILOT_GRADIENTS.json', dict(fold=FOLD, train_step_zero_based=step, batch_ids=batch_ids,
              targets=TARGETS, diagnostics=data, optimizer_steps=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
