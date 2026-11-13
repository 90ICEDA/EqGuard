from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_ctrlstrat.py')
s = p.read_text(encoding='utf-8')
s = s.replace('import numpy as np, torch', 'import numpy as np, torch\nimport torch.nn.functional as F')
s = s.replace("OUT / 'cones_ctrlall_D.npz'", "OUT / 'cones_ctrlstrat_D.npz'")
s = s.replace("run_ctrlall_s{seed}_lam{lam}", "run_ctrlstrat_s{seed}_lam{lam}")
old = "        lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(sup['idx'][step], device='cuda')); l_c = CL.cone_loss(lt, ct, pos_weight=10.0)\n        loss = l_t + lam * l_c"
new = "        lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(sup['idx'][step], device='cuda'))\n        mar = lt.float()[:, 1] - lt.float()[:, 0]\n        ncone = len(c['label'])\n        cmax = torch.full((ncone,), -1e9, device=mar.device)\n        cmax.scatter_reduce_(0, ct['seg'], mar.index_select(0, ct['idx']), reduce='amax', include_self=True)\n        pos = ct['lab'] == 1; neg = ~pos\n        recs = [str(v).split('__')[-1] for v in c['view']]\n        pw_map = {'ys_abc':1.0,'ys_id':1.0,'ys_opt':1.0,'ys_aig':4.0,'ys_nand':10.0}\n        nw_map = {'ys_abc':1.0,'ys_id':1.0,'ys_opt':1.0,'ys_aig':0.2,'ys_nand':0.2}\n        wp = torch.tensor([pw_map.get(r,1.0) for r in recs], device=mar.device)[pos]\n        wn = torch.tensor([nw_map.get(r,1.0) for r in recs], device=mar.device)[neg]\n        wp = wp / wp.mean(); wn = wn / wn.mean()\n        bcp = F.binary_cross_entropy_with_logits(cmax[pos], torch.ones_like(cmax[pos]), pos_weight=torch.tensor(10.0, device=mar.device), reduction='none')\n        bcn = F.binary_cross_entropy_with_logits(cmax[neg], torch.zeros_like(cmax[neg]), reduction='none')\n        l_pos = (bcp * wp).sum() / wp.sum()\n        l_neg = (bcn * wn).sum() / wn.sum()\n        l_c = l_pos + 10.8 * l_neg\n        loss = l_t + lam * l_c"
if old not in s:
    raise SystemExit('block not found')
s = s.replace(old, new)
s = s.replace("arm=arm, seed=seed, lambda_=lam, pos_weight=10.0", "arm=arm, seed=seed, lambda_=lam, pos_weight=10.0, mode='recipe_stratified', neg_global=10.8, pw_map=pw_map, nw_map=nw_map")
p.write_text(s, encoding='utf-8')
print('patched')
