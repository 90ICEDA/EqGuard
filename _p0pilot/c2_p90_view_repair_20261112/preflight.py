"""Compare C2 nand losses on the same training forward without optimizer updates."""
import argparse
import json
import random
import sys

import numpy as np
import torch

from build import OUT, P, C2, sha

sys.path.insert(0, str(P))
from c2_p90_anchor import CompressionLoss, load_cones
import c2_runner_p90 as runner

FOLD = 'ys_nand'
SEED = 42


def parameter_gradient(loss, params, retain_graph=False):
    grads = torch.autograd.grad(loss, params, retain_graph=retain_graph, allow_unused=True)
    return torch.cat([(g.detach().float() if g is not None else torch.zeros_like(p)).reshape(-1)
                      for g, p in zip(grads, params)])


def anchor_counterexamples():
    cones = dict(rows=np.arange(4), ptr=np.arange(5), label=np.array([1, 1, 0, 0]),
                 view=np.array(['A', 'A', 'A', 'B']))
    corrected = CompressionLoss(cones, ['A', 'B'], 'view-q25', 'cpu')
    scores = torch.tensor([1., 3., 2., 1.], requires_grad=True)
    loss, anchors, mask = corrected.compression(scores)
    assert torch.equal(anchors, torch.tensor([1.5, 1.5, 1.5, 0.]))
    assert mask.tolist() == [False, False, True, True] and loss.item() == 1.625
    assert torch.equal(torch.autograd.grad(loss, scores)[0], torch.tensor([-.75, -.25, 1., 1.5]))
    empty_loss, _, selected = corrected.compression(torch.tensor([1., 3., 1., -1.], requires_grad=True))
    assert empty_loss.item() == 0 and not selected.any()
    try:
        CompressionLoss(cones, ['A'], 'view-q25', 'cpu')
    except ValueError as e:
        assert 'not in the fold' in str(e)
    else:
        raise AssertionError('out-of-fold view accepted')


def rank_counterexample():
    cones = dict(rows=np.arange(13), ptr=np.array([0, 2, 13]), label=np.array([1, 0]),
                 view=np.array(['A', 'A']))
    loss = CompressionLoss(cones, ['A'], 'legacy', 'cpu', 'exact')
    values = torch.tensor([-1., -2., .01, .02, .03, .02] + [0.] * 7, requires_grad=True)
    maxima, scores = loss.cone_scores(values)
    torch.testing.assert_close(maxima, torch.tensor([-1., .03]), atol=0, rtol=0)
    torch.testing.assert_close(scores, torch.tensor([-1., .02]), atol=0, rtol=0)
    expected = torch.zeros_like(values)
    expected[[0, 3]] = 1
    assert torch.equal(torch.autograd.grad(scores.sum(), values)[0], expected)


def diagnose_anchors(old, new, cones, logits):
    with torch.no_grad():
        m = logits.float()[:, 1] - logits.float()[:, 0]
        maxima, p90 = old.cone_scores(m)
        new_maxima, new_p90 = new.cone_scores(m)
        assert torch.equal(maxima, new_maxima) and torch.equal(p90, new_p90)
        before, old_anchor, old_active = old.compression(p90)
        after, anchors, active = new.compression(p90)
        p90_cpu = p90.cpu().numpy()
        views, positive = cones['view'], cones['label'] == 1
        expected = np.zeros_like(p90_cpu)
        supported = np.zeros(len(views), dtype=bool)
        for v in np.unique(views[positive]):
            same = views == v
            expected[same] = np.quantile(p90_cpu[same & positive], 0.25)
            supported |= same
        np.testing.assert_allclose(anchors.cpu().numpy(), expected, rtol=0, atol=2e-6)
        assert torch.all(old_anchor == 0)
        legacy_selected = ~positive & (p90_cpu > 0)
        assert np.array_equal(old_active.cpu().numpy(), legacy_selected)
        assert np.array_equal(active.cpu().numpy(), ~positive & (p90_cpu > expected))
        fallback = ~positive & ~supported
        assert np.array_equal(active.cpu().numpy()[fallback], legacy_selected[fallback])
        if legacy_selected.any():
            np.testing.assert_allclose(before.item(), np.square(p90_cpu[legacy_selected] + 0.5).mean(), rtol=1e-6)
        scores = m.cpu().numpy()[cones['rows']]
        reference = []
        for start, stop in zip(cones['ptr'][:-1], cones['ptr'][1:]):
            rank = stop - start - 1 - (stop - start - 1) // 10
            reference.append(np.partition(scores[start:stop], rank)[rank])
        reference = np.array(reference)
        rank_diff = np.abs(reference - p90_cpu)
        historical_diff = rank_diff
        if old.rank_mode == 'exact':
            assert not rank_diff.any()
            legacy = CompressionLoss(cones, (), 'legacy', m.device, 'legacy')
            _, historical = legacy.cone_scores(m)
            historical_diff = np.abs(reference - historical.cpu().numpy())
        return dict(active_legacy=int(old_active.sum()), active_view_q25=int(active.sum()),
                    selected_status_changes=int((active != old_active).sum()),
                    fallback_negative=int(fallback.sum()), fallback_active=int(legacy_selected[fallback].sum()),
                    anchor_nonzero_negative=int(np.count_nonzero(expected[~positive])),
                    anchor_min=float(expected[~positive].min()), anchor_max=float(expected[~positive].max()),
                    common_rank_diff_count=int((rank_diff > 0).sum()),
                    common_rank_diff_max=float(rank_diff.max()),
                    historical_rank_diff_count=int((historical_diff > 0).sum()),
                    historical_rank_diff_max=float(historical_diff.max()))


def check_forward(model, state, train, sup, old, new, cones):
    device = 'cuda'
    model.load_state_dict(state, strict=True)
    saved_cpu_rng = torch.get_rng_state()
    saved_cuda_rng = torch.cuda.get_rng_state()
    saved_python_rng = random.getstate()
    saved_numpy_rng = np.random.get_state()
    params = tuple(model.parameters())
    try:
        runner.T.seed(SEED)
        model.train()
        orig = torch.as_tensor(runner.norm(runner.orig_x, train['mean'], train['std']), device=device)
        orig_edge = torch.as_tensor(runner.orig_e, device=device)
        orig_y = torch.as_tensor(runner.orig_y, device=device)
        orig_ids = torch.as_tensor(np.array(runner.loader.step('orig', 'G0', 0).indices, copy=True), device=device)
        with torch.autocast(device, dtype=torch.bfloat16):
            orig_loss = runner.T.domain_loss(model(orig, orig_edge), orig_y, orig_ids)
        orig_grad = parameter_gradient(orig_loss, params)
        x = torch.as_tensor(runner.norm(train['x'], train['mean'], train['std']), device=device)
        e = torch.as_tensor(train['edge'], device=device)
        y = torch.as_tensor(train['y'], device=device)
        ids = torch.as_tensor(np.asarray(sup['idx'][0], dtype=np.int64), device=device)
        with torch.autocast(device, dtype=torch.bfloat16):
            logits = model(x, e)
            node = runner.T.domain_loss(logits, y, ids)
            bce_legacy, comp_legacy = old(logits)
            bce_fixed, comp_fixed = new(logits)
        assert torch.equal(bce_legacy, bce_fixed)
        totals = (node + .01 * bce_legacy + .03 * comp_legacy, node + .01 * bce_fixed + .03 * comp_fixed)
        diagnostics = diagnose_anchors(old, new, cones, logits)
        comp_grad = [torch.autograd.grad(comp, logits, retain_graph=True)[0].float()
                     for comp in (comp_legacy, comp_fixed)]
        grad_legacy = orig_grad + parameter_gradient(totals[0], params, retain_graph=True)
        grad_fixed = orig_grad + parameter_gradient(totals[1], params)
        assert all(torch.isfinite(g).all() for g in (*comp_grad, grad_legacy, grad_fixed))
        delta = (grad_fixed - grad_legacy).norm().item()
        assert delta > 0 and all(g.norm().item() > 0 for g in comp_grad)
        assert all(p.grad is None for p in params)
        assert all(torch.equal(p.detach().cpu(), state[k]) for k, p in model.named_parameters())
        metrics = dict(orig_nodes=len(orig), trans_nodes=len(x), orig_sample=len(orig_ids), trans_sample=len(ids),
                       orig_node_loss=orig_loss.item(), trans_node_loss=node.item(), max_bce=bce_legacy.item(),
                       comp_legacy=comp_legacy.item(), comp_view_q25=comp_fixed.item(),
                       total_legacy=(orig_loss + totals[0]).item(), total_view_q25=(orig_loss + totals[1]).item(),
                       comp_logit_grad_norm_legacy=comp_grad[0].norm().item(),
                       comp_logit_grad_norm_view_q25=comp_grad[1].norm().item(),
                       full_grad_norm_legacy=grad_legacy.norm().item(), full_grad_norm_view_q25=grad_fixed.norm().item(),
                       full_grad_delta_norm=delta, **diagnostics)
    finally:
        model.load_state_dict(state, strict=True)
        model.eval()
        torch.set_rng_state(saved_cpu_rng)
        torch.cuda.set_rng_state(saved_cuda_rng)
        random.setstate(saved_python_rng)
        np.random.set_state(saved_numpy_rng)
    assert all(torch.equal(value.cpu(), state[key]) for key, value in model.state_dict().items())
    assert torch.equal(torch.get_rng_state(), saved_cpu_rng) and torch.equal(torch.cuda.get_rng_state(), saved_cuda_rng)
    return dict(metrics, model_and_buffers_restored=True, torch_rng_restored=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rank', choices=('legacy', 'exact'), default='legacy')
    args = parser.parse_args()
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_bf16_supported()
    anchor_counterexamples()
    rank_counterexample()
    with np.load(C2 / f'{FOLD}_train.npz') as data:
        train = {k: data[k] for k in ('x', 'edge', 'y', 'mean', 'std', 'view')}
    with np.load(C2 / f'{FOLD}_sup.npz', allow_pickle=True) as data:
        sup = {k: data[k] for k in ('idx', 'stepsha')}
    assets = [load_cones(C2, FOLD, mode) for mode in ('legacy', 'view-q25')]
    assert all(np.array_equal(assets[0][k], assets[1][k]) for k in ('rows', 'ptr', 'label'))
    common_assets = (assets[1], assets[1]) if args.rank == 'exact' else assets
    old, new = [CompressionLoss(co, train['view'], mode, 'cuda', args.rank)
                for co, mode in zip(common_assets, ('legacy', 'view-q25'))]
    model = runner.Model().cuda().eval()
    old_run = C2 / 'runs_p90/ys_nand_NC_s42'
    init = P / 'control_v3_eligible_20261104/init_s42.pt'
    best = old_run / 'best_resume.pt'
    result = dict(fold=FOLD, seed=SEED, rank_mode=args.rank, optimizer_steps=0, sat_cec_calls=0, labels_modified=False,
                  missing_positive_policy='constant_zero_anchor', checkpoints={})
    for name, path in (('initialization', init), ('legacy_best', best)):
        state = torch.load(path, map_location='cpu', weights_only=True)
        if name == 'legacy_best':
            assert (state['fold'], state['arm'], state['seed']) == (FOLD, 'NC', SEED)
            state = state['model']
        result['checkpoints'][name] = dict(path=str(path.relative_to(P)), sha256=sha(path),
                                          **check_forward(model, state, train, sup, old, new, assets[1]))
        print(name, result['checkpoints'][name], flush=True)
    history = json.loads((old_run / 'LOG.json').read_text(encoding='utf-8'))['logs'][0]
    result['historical_step1'] = {k: history[k] for k in ('node_orig', 'node_trans', 'bce', 'comp', 'grad_norm')}
    name = 'PREFLIGHT_EXACT.json' if args.rank == 'exact' else 'PREFLIGHT.json'
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
