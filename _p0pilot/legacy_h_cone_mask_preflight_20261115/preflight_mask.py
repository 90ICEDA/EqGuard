"""No-update gradient preflight: full cone max vs positive-member-only max."""
import json, sys, copy
from pathlib import Path
import numpy as np
import torch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
RUN_DIR = OUT.parent / 'legacy_h_cone_20261115'
sys.path.insert(0, str(RUN_DIR))
import run

def stats(loss, logits, model):
    model.zero_grad(set_to_none=True)
    g = torch.autograd.grad(loss, [p for p in model.parameters() if p.requires_grad], retain_graph=True, allow_unused=True)
    total = sum(float((x.float()**2).sum()) for x in g if x is not None)
    return total ** .5

def main():
    seed = 42
    mod, manifest = run.configure(seed, cone=True)
    old = run.predecessor(seed)
    model = mod.Model().cuda()
    model.load_state_dict(torch.load(RUN_DIR / f'seed{seed}/H/best.pt', map_location='cuda', weights_only=True))
    model.train()
    before = {k: v.detach().clone() for k, v in model.state_dict().items()}
    d = mod.T.load('trans', 'train', 'A')
    base = np.flatnonzero(np.load(old / 'trans_base_mask.npy'))
    slots = np.load(old / 'trans_H_slots.npy')[0]
    ids = torch.as_tensor(np.concatenate([base, slots]), dtype=torch.long, device='cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(d['x'], d['edge'])
    node = mod.T.domain_loss(logits, d['y'], ids)
    full = mod.CONES
    # positive cone: only trusted positive members; negative cones unchanged
    y = d['y'].detach().cpu().numpy()
    # membership count used for shared-node variants
    from collections import Counter
    cnt = Counter()
    for _, _, mem in full['rows']:
        for x in mem: cnt[x] += 1
    rows = []
    empty = 0
    for cid, lab, mem in full['rows']:
        if lab == 1:
            mm = [x for x in mem if y[x] == 1]
            if not mm:
                empty += 1
                continue
        else:
            mm = list(mem)
        rows.append((cid, lab, mm))
    masked = mod.CONE.cone_tensors(rows)
    rows_excl = []
    empty_excl = 0
    for cid, lab, mem in full['rows']:
        if lab == 1:
            mm = [x for x in mem if y[x] == 1 and cnt[x] == 1]
            if not mm:
                empty_excl += 1
                continue
        else:
            mm = list(mem)
        rows_excl.append((cid, lab, mm))
    excl = mod.CONE.cone_tensors(rows_excl)
    cone_full = mod.CONE.cone_loss(logits, full)
    cone_mask = mod.CONE.cone_loss(logits, masked)
    cone_excl = mod.CONE.cone_loss(logits, excl)
    # gradients of cone terms w.r.t. logits and parameters
    model.zero_grad(set_to_none=True)
    gf = torch.autograd.grad(cone_full, logits, retain_graph=True)[0].float()
    gm = torch.autograd.grad(cone_mask, logits, retain_graph=True)[0].float()
    ge = torch.autograd.grad(cone_excl, logits, retain_graph=True)[0].float()
    def per_node(g):
        return g.abs().sum(1)
    nf, nm, ne = per_node(gf), per_node(gm), per_node(ge)
    def top_share(v, k=10):
        total = float(v.sum())
        return float(v.topk(min(k, len(v))).values.sum() / total) if total else 0.0
    shared = torch.tensor([cnt[i] >= 2 for i in range(len(y))], device='cuda')
    def shared_share(v):
        total = float(v.sum())
        return float(v[shared].sum() / total) if total else 0.0
    ptotal = stats(node + cone_full, logits, model)
    mtotal = stats(node + cone_mask, logits, model)
    etotal = stats(node + cone_excl, logits, model)
    model.load_state_dict(before)
    out = dict(seed=seed, checkpoint=str(RUN_DIR / f'seed{seed}/H/best.pt'),
        node_ids=int(len(ids)), positive_cones=int(full['pos']), negative_cones=int(full['neg']),
        masked_positive_cones=int(masked['pos']), empty_positive_cones=empty,
        excl_positive_cones=int(excl['pos']), empty_excl_positive_cones=empty_excl,
        full_cone_loss=float(cone_full.detach()), masked_cone_loss=float(cone_mask.detach()),
        excl_cone_loss=float(cone_excl.detach()),
        full_grad_norm=ptotal, masked_grad_norm=mtotal, excl_grad_norm=etotal,
        full_top10_share=top_share(nf), masked_top10_share=top_share(nm), excl_top10_share=top_share(ne),
        full_shared_share=shared_share(nf), masked_shared_share=shared_share(nm), excl_shared_share=shared_share(ne),
        full_shared_nodes=int(shared.sum()), members_full=int(full['members']), members_masked=int(masked['members']),
        members_excl=int(excl['members']))
    (OUT / 'PREFLIGHT_MASK_S42.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
