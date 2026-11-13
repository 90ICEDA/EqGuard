from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_relaxed.py')
s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_scale_20261110'", "OUT = R / '_p0pilot/lcone_relaxed_20261111'")
s = s.replace("c = np.load(CONE_DIR / f'cones_v2c_{arm}_D.npz')", "c = np.load(OUT / 'cones_relaxed_D.npz')")
s = s.replace("run_{arm}_s{seed}_lam{lam}", "run_relaxed_s{seed}_lam{lam}")
p.write_text(s, encoding='utf-8')
print('patched')
