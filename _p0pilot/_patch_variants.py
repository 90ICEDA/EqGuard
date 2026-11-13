from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot')
# hard
p = R / 'train_hard.py'; s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_scale_20261110'", "OUT = R / '_p0pilot/lcone_directions_20261110'")
s = s.replace("c = np.load(CONE_DIR / f'cones_v2c_{arm}_D.npz')", "c = np.load(OUT / 'cones_hard_D.npz')")
s = s.replace("run_{arm}_s{seed}_lam{lam}", "run_hard_s{seed}_lam{lam}")
p.write_text(s, encoding='utf-8')
# mean
p = R / 'train_mean.py'; s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_scale_20261110'", "OUT = R / '_p0pilot/lcone_directions_20261110'")
s = s.replace("run_{arm}_s{seed}_lam{lam}", "run_mean_s{seed}_lam{lam}")
s = s.replace("import numpy as np, torch", "import numpy as np, torch\nimport torch.nn.functional as F")
s = s.replace("        l_c = CL.cone_loss(lt, ct, pos_weight=10.0)\n        loss = l_t + lam * l_c",
              "        mar = lt.float()[:, 1] - lt.float()[:, 0]\n        ncone = len(c['label'])\n        sums = torch.zeros(ncone, device=mar.device).index_add_(0, ct['seg'], mar.index_select(0, ct['idx']))\n        counts = torch.bincount(ct['seg'], minlength=ncone).clamp_min(1)\n        cscore = sums / counts\n        l_c = F.binary_cross_entropy_with_logits(cscore, ct['lab'], pos_weight=torch.tensor(10.0, device=mar.device))\n        loss = l_t + lam * l_c")
p.write_text(s, encoding='utf-8')
print('patched')
