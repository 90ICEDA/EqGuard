from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_ctrl.py')
s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_weak_20261110'", "OUT = R / '_p0pilot/lcone_trainctl_20261110'")
s = s.replace("c = np.load(OUT / 'cones_weak_D.npz')", "c = np.load(OUT / 'cones_ctrl_D.npz')")
s = s.replace("run_weak_s{seed}_lam{lam}", "run_ctrl_s{seed}_lam{lam}")
p.write_text(s, encoding='utf-8')
print('patched')
