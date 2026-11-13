from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_ctrlgn.py')
s = p.read_text(encoding='utf-8')
s = s.replace('import numpy as np, torch', 'import numpy as np, torch\nimport torch.nn.functional as F')
s = s.replace("run_ctrlall_s{seed}_lam{lam}", "run_ctrlgn_s{seed}_lam{lam}")
old = """    l_o.backward()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(sup['idx'][step], device='cuda')); l_c = CL.cone_loss(lt, ct, pos_weight=10.0)
        loss = l_t + lam * l_c
    loss.backward(); gn = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)); opt.step()
    rec = dict(step=step + 1, node_orig=float(l_o), node_trans=float(l_t), cone=float(l_c),
               orig_sha=hashlib.sha256(io.tobytes()).hexdigest(), trans_sha=str(sup['stepsha'][step]),
               grad_norm=gn, finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(gn)))"""
new = """    with torch.autocast('cuda', dtype=torch.bfloat16):
        lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(sup['idx'][step], device='cuda'))
        mar = lt.float()[:, 1] - lt.float()[:, 0]
        ncone = len(c['label'])
        cmax = torch.full((ncone,), -1e9, device=mar.device)
        cmax.scatter_reduce_(0, ct['seg'], mar.index_select(0, ct['idx']), reduce='amax', include_self=True)
        pos = ct['lab'] == 1; neg = ~pos
        l_pos = F.binary_cross_entropy_with_logits(cmax[pos], torch.ones_like(cmax[pos]), pos_weight=torch.tensor(10.0, device=mar.device))
        l_neg = F.binary_cross_entropy_with_logits(cmax[neg], torch.zeros_like(cmax[neg]))
        l_c = l_pos + l_neg
    params = [p for p in model.parameters() if p.requires_grad]
    go = torch.autograd.grad(l_o, params, retain_graph=True, allow_unused=True)
    gt = torch.autograd.grad(l_t, params, retain_graph=True, allow_unused=True)
    gp = torch.autograd.grad(l_pos, params, retain_graph=True, allow_unused=True)
    gn = torch.autograd.grad(l_neg, params, retain_graph=True, allow_unused=True)
    def add_norm(acc, g, target):
        if g is None: return
        n = float(g.norm())
        if n > 0: acc.append(g * (target / n))
    node_parts=[]; pos_parts=[]; neg_parts=[]
    for g1,g2 in zip(go,gt):
        if g1 is not None or g2 is not None:
            g = (g1 if g1 is not None else 0) + (g2 if g2 is not None else 0)
            add_norm(node_parts, g, 1.0)
    for g in gp: add_norm(pos_parts, g, 0.5)
    for g in gn: add_norm(neg_parts, g, 1.0)
    node_s = torch.stack(node_parts); pos_s = torch.stack(pos_parts); neg_s = torch.stack(neg_parts)
    for idx,p in enumerate(params):
        p.grad = node_s[idx] + pos_s[idx] + neg_s[idx]
    gn_total = float(torch.nn.utils.clip_grad_norm_(params, 5.0)); opt.step()
    rec = dict(step=step + 1, node_orig=float(l_o), node_trans=float(l_t), cone=float(l_c),
               grad_node=float(node_s.norm()), grad_pos=float(pos_s.norm()), grad_neg=float(neg_s.norm()), grad_norm=gn_total,
               orig_sha=hashlib.sha256(io.tobytes()).hexdigest(), trans_sha=str(sup['stepsha'][step]),
               finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(gn_total)))"""
if old not in s:
    raise SystemExit('block not found')
s = s.replace(old, new)
s = s.replace("arm=arm, seed=seed, lambda_=lam, pos_weight=10.0", "arm=arm, seed=seed, lambda_=lam, pos_weight=10.0, gradnorm=True")
p.write_text(s, encoding='utf-8')
print('patched')
