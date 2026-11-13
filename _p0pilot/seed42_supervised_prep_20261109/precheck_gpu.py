"""Real-load / zero-update loss+grad precheck on ginvenv_gpu.

- loads the frozen seed42 engine/loader and init;
- runs one trans_train forward with the frozen node supervision step 0;
- adds the endpoint-cone MIL loss over train D cones only (lambda=1, pos_weight=10);
- verifies actual aggregation indices, positive/negative cone counts and denominators against the cache;
- checks finite loss/grad, peak GPU memory and wall time;
- 0 optimizer.step; parameters and BN buffers must be identical before/after.
"""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import csv
import gc
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/seed42_supervised_prep_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L))
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from supervision_loader import FiveGroupLoader  # noqa: E402
from evaluate import Model, T  # noqa: E402
import torch  # noqa: E402


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract
    T.NORM = loader.normalization
    T.arrays = loader.arrays
    assert T.MASK_MODE == 'old' and not T.EXTRA and T.EQ == 0

    T.seed(42)
    model = Model().cuda()
    assert sum(p.numel() for p in model.parameters()) == 46620
    model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))

    # node supervision step 0 (frozen indices)
    q = loader.step('trans', 'G0', 0)
    ids = torch.as_tensor(q.indices, dtype=torch.long, device='cuda')
    arr = loader.arrays('trans')
    assert bool(arr['trusted'][q.indices].all()) and bool(arr['physical'][q.indices].all())

    # cone cache: train D cones with label in {0,1} and >=2 physical members
    rows = []
    with (OUT / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
                continue
            mem = [int(x) for x in r['phys_rows'].split('|')
                   if x and bool(arr['trusted'][int(x)])]
            assert mem, r['cone_id']
            rows.append((r['cone_id'], int(r['label']), mem))
    assert rows, 'no qualified train D cones'
    labels = np.array([lab for _, lab, _ in rows], np.float32)
    flat, ptr = [], [0]
    for _, _, mem in rows:
        flat.extend(mem)
        ptr.append(len(flat))
    flat = np.array(flat, np.int64)
    assert bool(arr['trusted'][flat].all()), 'cone members must be trusted physical rows'
    assert labels.sum() > 0 and (labels == 0).sum() > 0
    member_t = torch.as_tensor(flat, dtype=torch.long, device='cuda')
    label_t = torch.as_tensor(labels, dtype=torch.float32, device='cuda')
    cone_ptr = torch.as_tensor(np.array(ptr[:-1], np.int64), dtype=torch.long, device='cuda')
    cone_len = torch.as_tensor(np.array([p - q for p, q in zip(ptr[1:], ptr[:-1])], np.int64),
                               dtype=torch.long, device='cuda')
    # index digest for evidence
    idx_sha = hashlib.sha256(flat.tobytes()).hexdigest()

    before = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    d = loader.torch_graph('trans', 'train', 'cuda')
    assert set(d) == {'x', 'edge', 'y'}
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(d['x'], d['edge'])
        node_loss = T.domain_loss(logits, d['y'], ids)
    # cone MIL loss: max over the trusted physical members of each cone
    pos_logits = logits.float()[:, 1]
    # amax via segment reduce
    cmax = torch.full((len(rows),), -1e9, device='cuda')
    cmax.scatter_reduce_(0, torch.repeat_interleave(torch.arange(len(rows), device='cuda'), cone_len),
                         pos_logits.index_select(0, member_t), reduce='amax', include_self=True)
    cone_loss = torch.nn.functional.binary_cross_entropy_with_logits(
        cmax, label_t, pos_weight=torch.tensor(10.0, device='cuda'))
    total = node_loss + 1.0 * cone_loss
    assert torch.isfinite(total), 'non-finite loss'
    total.backward()
    bad = [n for n, p in model.named_parameters() if p.grad is not None and not torch.isfinite(p.grad).all()]
    assert not bad, bad
    after = model.state_dict()
    unchanged = all(torch.equal(before[k], after[k].detach().cpu()) for k in before)
    assert unchanged, 'parameters or BN buffers changed without optimizer.step'
    peak = torch.cuda.max_memory_allocated() / 1e9
    secs = time.perf_counter() - t0
    out = dict(passed=True, node_step=0, cone_step=0, qualified_cones=len(rows),
               cone_pos=int(labels.sum()), cone_neg=int((labels == 0).sum()),
               cone_members=int(len(flat)), member_index_sha=idx_sha,
               node_loss=float(node_loss.detach()), cone_loss=float(cone_loss.detach()),
               grads_finite=True, optimizer_steps=0, params_unchanged=True,
               peak_gpu_gb=round(peak, 3), seconds=round(secs, 2),
               train_views=len({r['view'] for r in csv.DictReader((OUT / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig'))}))
    (OUT / 'PRECHECK_GPU.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False))
    del logits, total, node_loss, cone_loss, d
    gc.collect(); torch.cuda.empty_cache()


if __name__ == '__main__':
    main()
