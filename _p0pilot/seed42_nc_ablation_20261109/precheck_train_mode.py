"""Training-mode zero-update precheck: real order orig node loss -> trans node+cone loss, BF16/BN/dropout.

Checks:
  - cone score = margin max over trusted physical members; common logit offset invariance;
  - node-term and cone-term gradient norms finite; cone grad nonzero;
  - 0 optimizer.step; params, BN buffers and RNG state restored and verified.
"""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/seed42_nc_ablation_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_supervised_prep_20261109'))
from supervision_loader import FiveGroupLoader  # noqa: E402
from evaluate import Model, T  # noqa: E402
import cone_loss as CL  # noqa: E402


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    assert T.MASK_MODE == 'old' and not T.EXTRA and T.EQ == 0
    T.seed(42)
    model = Model().cuda(); model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))

    arr = loader.arrays('trans')
    rows = CL.load_cones('train', 'D', trust=arr['trusted'])
    cones = CL.cone_tensors(rows)
    # offset invariance on a small synthetic cone set (members in range)
    demo_idx = torch.tensor([0, 3, 7, 11, 19, 23], dtype=torch.long, device='cuda')
    demo_seg = torch.tensor([0, 0, 0, 1, 1, 2], dtype=torch.long, device='cuda')
    demo = dict(rows=[0, 1, 2], idx=demo_idx, seg=demo_seg)
    lg = torch.randn(32, 2, device='cuda')
    c0 = CL.cone_score(CL.margin_of(lg), demo)
    c1 = CL.cone_score(CL.margin_of(lg + 3.5), demo)
    assert torch.allclose(c0, c1), 'margin not offset invariant'

    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    rng = (torch.get_rng_state().clone(), torch.cuda.get_rng_state_all())
    model.train()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    q = loader.step('trans', 'G0', 0)
    ids_t = torch.as_tensor(q.indices, dtype=torch.long, device='cuda')
    qo = loader.step('orig', 'G0', 0)
    ids_o = torch.as_tensor(qo.indices, dtype=torch.long, device='cuda')
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    opt.zero_grad(set_to_none=True)
    losses = {}
    params = [p for p in model.parameters() if p.requires_grad]
    # 1) orig node loss
    d = loader.torch_graph('orig', 'train', 'cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits_o = model(d['x'], d['edge'])
        loss_o = T.domain_loss(logits_o, d['y'], ids_o)
    losses['orig'] = float(loss_o.detach()); loss_o.backward(); del logits_o, loss_o, d
    # 2) trans node + cone on ONE forward, accumulate both
    d = loader.torch_graph('trans', 'train', 'cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits_t = model(d['x'], d['edge'])
        loss_t = T.domain_loss(logits_t, d['y'], ids_t)
        closs = CL.cone_loss(logits_t, cones)
    losses['trans'] = float(loss_t.detach()); losses['cone'] = float(closs.detach())
    # separate term norms before accumulation
    g_node = torch.autograd.grad(loss_t, params, retain_graph=True, allow_unused=True)
    node_gn = sum(float(g.norm()) ** 2 for g in g_node if g is not None) ** 0.5
    g_cone = torch.autograd.grad(closs, params, retain_graph=True, allow_unused=True)
    cone_gn = sum(float(g.norm()) ** 2 for g in g_cone if g is not None) ** 0.5
    loss_t.backward(retain_graph=True); closs.backward()
    finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
    nz = sum(1 for p in params if p.grad is not None and float(p.grad.abs().sum()) > 0)
    assert finite and nz > 0 and cone_gn > 0, (finite, nz, cone_gn)
    peak = torch.cuda.max_memory_allocated() / 1e9
    secs = time.perf_counter() - t0
    # restore and verify
    model.load_state_dict(state)
    torch.set_rng_state(rng[0]); torch.cuda.set_rng_state_all(rng[1])
    now = model.state_dict()
    restored = all(torch.equal(state[k], now[k].detach().cpu()) for k in state)
    out = dict(passed=bool(restored), mode='train', cones=len(rows), pos=cones['pos'], neg=cones['neg'],
               members=cones['members'], member_sha=cones['sha'], losses=losses,
               grad_norm_node=round(node_gn, 4), grad_norm_cone=round(cone_gn, 4),
               grad_params_nonzero=nz, grads_finite=finite,
               optimizer_steps=0, restored=restored, peak_gpu_gb=round(peak, 3), seconds=round(secs, 2))
    (OUT / 'PRECHECK_TRAIN_MODE.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
