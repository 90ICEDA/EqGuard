"""Execute the frozen seed42, two-fold, shared-pair loss pilot."""
import argparse
import time

import numpy as np
import torch
from sklearn.metrics import average_precision_score

from audit import OUT, P, V5, load_module, read, sha, write_json
from capped_backward import CAP_RATIO, backward_capped
from pilot_preflight import ACTIVE_STEPS, FOLDS, PAIR_MARGIN, cone_terms

ARMS = ('N', 'NC-BCE', 'NC-Rank')
CAPPED_ARM = 'NC-BCE-Cap'
RUNS = OUT / 'pilot_runs'
CONTRACT = OUT / 'PILOT_PREFLIGHT.json'
INIT = P / 'control_v3_eligible_20261104/init_s42.pt'


def node_schedule(io, loader, fold, train):
    history = read(V5 / fold / 'N/LOG.json')['logs']
    schedule = []
    for step in range(200):
        rng = np.random.default_rng(42 + step)
        trans = np.concatenate((train['pos'], rng.choice(train['common_pool'], 8192, replace=False),
                                rng.choice(train['h_pool'], 144, replace=False))).astype(np.int64)
        orig = np.array(loader.step('orig', 'G0', step).indices, copy=True)
        hashes = [io.sha_ids(ids) for ids in (orig, trans)]
        assert hashes == [history[step]['orig_sha'], history[step]['trans_sha']]
        schedule.append((orig, trans, hashes))
    return schedule


def cuda_graph(data):
    return tuple(torch.as_tensor(data[k], device='cuda') for k in ('x', 'edge', 'y'))


def validation_slices(io, data):
    slices = []
    for view in io.views('val').values():
        a, b = np.searchsorted(data['rows'], [view['start'], view['stop']])
        trust = data['trusted'][a:b]
        y = data['y'][a:b][trust]
        if np.unique(y).size > 1:
            slices.append((np.arange(a, b)[trust], y))
    assert slices
    return slices


def train_arm(fold, arm, model_type, T, init, orig, train, val, val_slices, schedule, plan):
    folder = RUNS / fold / arm
    log_path = folder / 'LOG.json'
    if log_path.is_file():
        old = read(log_path)
        assert old['contract_sha256'] == sha(CONTRACT) and len(old['logs']) == 200
        assert all(sha(folder / name) == digest for name, digest in old['checkpoints'].items())
        print(f'REUSE {fold} {arm}', flush=True)
        return
    folder.mkdir(parents=True, exist_ok=True)
    assert not any(folder.iterdir()), f'incomplete run artifacts at {folder}'
    start = time.perf_counter()
    T.seed(42)
    model = model_type().cuda()
    model.load_state_dict(init, strict=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    best_score, best_step, best = -1, None, None
    logs = []
    loss_key = {'NC-BCE': 'bce', 'NC-Rank': 'rank', CAPPED_ARM: 'bce'}.get(arm)
    weight = plan['initial_gradient_matched_weights'][loss_key] if loss_key else 0.0
    pair_schedule = {int(step): ids for step, ids in plan['schedule'].items()}
    assert tuple(pair_schedule) == ACTIVE_STEPS
    for step, (ids_o, ids_t, sample_hashes) in enumerate(schedule):
        T.seed(42 + step)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            orig_loss = T.domain_loss(model(orig[0], orig[1]), orig[2], torch.as_tensor(ids_o, device='cuda'))
        orig_loss.backward()
        ids = pair_schedule.get(step, []) if loss_key else []
        with torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(train[0], train[1])
            trans_loss = T.domain_loss(logits, train[2], torch.as_tensor(ids_t, device='cuda'))
        aux = None
        if ids:
            margin = logits.float()[:, 1] - logits.float()[:, 0]
            bce, rank = cone_terms(margin, [plan['pool'][i] for i in ids])
            aux = bce if loss_key == 'bce' else rank
        cap_info = None
        if aux is not None and arm == CAPPED_ARM:
            cap_info = backward_capped(trans_loss, aux, model.parameters(), weight)
        else:
            total = trans_loss if aux is None else trans_loss + weight * aux
            total.backward()
        grad = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.).item()
        item = dict(step=step+1, node_orig=orig_loss.detach().item(), node_trans=trans_loss.detach().item(),
                    aux_loss=aux.detach().item() if aux is not None else None, grad_norm=grad,
                    sample_sha256=sample_hashes, pairs=ids)
        if cap_info is not None:
            item['gradient_cap'] = cap_info
        assert all(np.isfinite(v) for v in (item['node_orig'], item['node_trans'], grad))
        assert item['aux_loss'] is None or np.isfinite(item['aux_loss'])
        optimizer.step()
        if (step+1) % 5 == 0:
            model.eval()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lg = model(val[0], val[1]).float()
                margin = (lg[:, 1] - lg[:, 0]).cpu().numpy()
            ap = float(np.mean([average_precision_score(y, margin[ids]) for ids, y in val_slices]))
            assert np.isfinite(ap)
            item['val_ap'] = ap
            if ap > best_score:
                best_score, best_step = ap, step+1
                best = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        logs.append(item)
    assert len(logs) == 200 and best_step is not None
    torch.save(best, folder / 'best.pt')
    torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, folder / 'last.pt')
    write_json(log_path, dict(fold=fold, arm=arm, seed=42, aux_weight=weight, best_step=best_step, best_val_ap=best_score,
                              cap_ratio=CAP_RATIO if arm == CAPPED_ARM else None,
                              contract_sha256=sha(CONTRACT), init_sha256=sha(INIT), logs=logs,
                              checkpoints={f: sha(folder / f) for f in ('best.pt', 'last.pt')},
                              seconds=time.perf_counter()-start))
    print(f'DONE {fold} {arm} best={best_step} val_AP={best_score:.6f} seconds={time.perf_counter()-start:.1f}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fold', choices=FOLDS, action='append')
    parser.add_argument('--arm', choices=(*ARMS, CAPPED_ARM), action='append')
    args = parser.parse_args()
    preflight = read(CONTRACT)
    if args.arm and CAPPED_ARM in args.arm:
        gate = read(OUT / 'CAPPED_BCE_ENTRY_PREFLIGHT.json')
        assert gate['contract_sha256'] == sha(CONTRACT) and gate['cap_ratio'] == CAP_RATIO
        assert gate['optimizer_steps'] == 0 and all(r['aux_to_node'] <= CAP_RATIO for r in gate['diagnostics'])
    assert preflight['init_sha256'] == sha(INIT) and preflight['pair_margin'] == PAIR_MARGIN
    assert preflight['node_steps'] == 200 and preflight['candidate_sha256'] == sha(OUT / 'VERIFIED_HARD_PAIR_CANDIDATES.csv')
    init = torch.load(INIT, map_location='cpu', weights_only=True)
    assert torch.cuda.is_bf16_supported()
    module = load_module('pilot_model', P / 'control_best200_20261104/evaluate.py')
    io = load_module('pilot_io', V5 / 'fold_io.py')
    import sys
    sys.path.insert(0, str(P / 'control_loader_po_20261105'))
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    for fold in args.fold or FOLDS:
        plan = preflight['folds'][fold]
        assert plan['train_map_sha256'] == sha(io.V4 / f'{fold}_train_map.npz')
        train, val = io.load_trans(fold), io.load_trans(fold, 'val')
        orig = io.load_orig('train', train['mean'], train['std'])
        schedule = node_schedule(io, loader, fold, train)
        val_slices = validation_slices(io, val)
        graphs = tuple(cuda_graph(g) for g in (orig, train, val))
        for arm in args.arm or ARMS:
            train_arm(fold, arm, module.Model, module.T, init, *graphs, val_slices, schedule, plan)
        del graphs


if __name__ == '__main__':
    main()
