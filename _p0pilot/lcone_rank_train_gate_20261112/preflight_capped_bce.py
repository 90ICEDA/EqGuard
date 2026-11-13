"""Exercise the production capped backward path without optimizer updates."""
import argparse
import sys

import torch

from audit import OUT, P, V5, load_module, read, sha, write_json
from capped_backward import CAP_RATIO, backward_capped, norm
from pilot_preflight import ACTIVE_STEPS, cone_terms
from run_pilot import CAPPED_ARM, CONTRACT, FOLDS, INIT, RUNS, cuda_graph, node_schedule


def counterexamples():
    p = torch.nn.Parameter(torch.tensor([1., -2.]))
    q = torch.nn.Parameter(torch.tensor([3.]))
    (p[0]*3).backward()
    info = backward_capped(4*p[1], 10*q[0], (p, q), 1.)
    torch.testing.assert_close(p.grad, torch.tensor([3., 4.]))
    torch.testing.assert_close(q.grad, torch.tensor([.5]))
    assert info['aux_to_node'] == CAP_RATIO
    p.grad = q.grad = None
    info = backward_capped(0*p[0], 10*q[0], (p, q), 1.)
    assert info['aux_to_node'] == 0.0 and q.grad is None
    p.grad = q.grad = None
    info = backward_capped(4*p[0], 0*q[0], (p, q), 1.)
    assert info['aux_to_node'] == 0.0 and info['raw_aux_norm'] == 0.0 and q.grad is None


def exercise(model, T, state, graphs, schedule, plan, step):
    orig, train = graphs
    model.load_state_dict(state, strict=True)
    model.zero_grad(set_to_none=True)
    model.train()
    T.seed(42+step)
    ids_o, ids_t, hashes = schedule[step]
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = T.domain_loss(model(orig[0], orig[1]), orig[2], torch.as_tensor(ids_o, device='cuda'))
    lo.backward()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(train[0], train[1])
        lt = T.domain_loss(logits, train[2], torch.as_tensor(ids_t, device='cuda'))
    ids = plan['schedule'][str(step)]
    margin = logits.float()[:, 1] - logits.float()[:, 0]
    bce, _ = cone_terms(margin, [plan['pool'][i] for i in ids])
    initial_weight = plan['initial_gradient_matched_weights']['bce']
    info = backward_capped(lt, bce, model.parameters(), initial_weight, capture=True)
    expected = info.pop('expected')
    params = tuple(p for p in model.parameters() if p.requires_grad)
    for p, e in zip(params, expected):
        assert (p.grad is None and e is None) or torch.equal(p.grad, e)
    combined = norm(p.grad for p in params)
    clipped = torch.nn.utils.clip_grad_norm_(params, 1.).item()
    assert abs(combined-clipped) < 1e-5
    clipped_norm = norm(p.grad for p in params)
    assert clipped_norm <= 1.0 + 1e-6
    assert info['aux_to_node'] <= CAP_RATIO
    assert all(torch.equal(v.detach().cpu(), state[k]) for k, v in model.named_parameters())
    model.load_state_dict(state, strict=True)
    model.zero_grad(set_to_none=True)
    model.eval()
    assert all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
    return dict(step=step+1, pair_ids=ids, sample_sha256=hashes, old_weight=initial_weight,
                original_aux_to_node=initial_weight*info['raw_aux_norm']/info['node_norm'],
                combined_norm_before_clip=combined, combined_norm_after_clip=clipped_norm, **info)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recheck', action='store_true')
    args = parser.parse_args()
    counterexamples()
    assert torch.cuda.is_bf16_supported() and 'ginvenv_gpu' in sys.executable
    io = load_module('v5_io', V5 / 'fold_io.py')
    module = load_module('v5_model', P / 'control_best200_20261104/evaluate.py')
    sys.path.insert(0, str(P / 'control_loader_po_20261105'))
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    model = module.Model().cuda()
    contract = read(CONTRACT)
    rows = []
    for fold in FOLDS:
        train = io.load_trans(fold)
        plan = contract['folds'][fold]
        assert sha(io.V4 / f'{fold}_train_map.npz') == plan['train_map_sha256']
        graphs = tuple(cuda_graph(g) for g in (io.load_orig('train', train['mean'], train['std']), train))
        schedule = node_schedule(io, loader, fold, train)
        for point, step in (('initialization', ACTIVE_STEPS[0]), ('best', ACTIVE_STEPS[-1]), ('last', ACTIVE_STEPS[-1])):
            path = INIT if point == 'initialization' else RUNS / fold / 'NC-BCE' / f'{point}.pt'
            expected = (contract['init_sha256'] if point == 'initialization' else
                        read(path.parent / 'LOG.json')['checkpoints'][path.name])
            assert sha(path) == expected
            state = torch.load(path, map_location='cpu', weights_only=True)
            r = dict(fold=fold, point=point, checkpoint_sha256=expected,
                     **exercise(model, module.T, state, graphs, schedule, plan, step))
            rows.append(r)
            print(fold, point, r['original_aux_to_node'], r['aux_to_node'], r['effective_weight'], flush=True)
        del graphs
    assert not any((RUNS / f / CAPPED_ARM / 'LOG.json').exists() for f in FOLDS)
    target = OUT / 'CAPPED_BCE_ENTRY_PREFLIGHT.json'
    if args.recheck:
        previous = read(target)
        assert previous['contract_sha256'] == sha(CONTRACT) and len(previous['diagnostics']) == len(rows)
        assert all((a['checkpoint_sha256'], a['pair_ids'], a['sample_sha256']) ==
                   (b['checkpoint_sha256'], b['pair_ids'], b['sample_sha256'])
                   for a, b in zip(previous['diagnostics'], rows))
    else:
        write_json(target, dict(diagnostics=rows, cap_ratio=CAP_RATIO, contract_sha256=sha(CONTRACT),
                                optimizer_steps=0, sat_cec_calls=0, labels_modified=False,
                                validation_or_test_predictions_read=False))


if __name__ == '__main__':
    main()
