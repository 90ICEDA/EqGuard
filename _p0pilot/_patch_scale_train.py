from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\lcone_scale_train.py')
s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_v2c_20261110'", "OUT = R / '_p0pilot/lcone_scale_20261110'\nCONE_DIR = R / '_p0pilot/lcone_v2c_20261110'")
s = s.replace("c = np.load(OUT / f'cones_v2c_{arm}_D.npz')", "c = np.load(CONE_DIR / f'cones_v2c_{arm}_D.npz')")
s = s.replace("arm = sys.argv[1]; seed = int(sys.argv[2])", "arm = sys.argv[1]; seed = int(sys.argv[2]); lam = float(sys.argv[3])")
s = s.replace("outdir = OUT / f'run_{arm}_s{seed}'; outdir.mkdir(exist_ok=True)",
              "outdir = OUT / f'run_{arm}_s{seed}_lam{lam}'; outdir.mkdir(parents=True, exist_ok=True)")
s = s.replace("l_c = CL.cone_loss(lt, ct);\n        loss = l_t + l_c", "l_c = CL.cone_loss(lt, ct, pos_weight=10.0);\n        loss = l_t + lam * l_c")
s = s.replace("dict(arm=arm, seed=seed, best_step=best['step'], best_score=best['score'], logs=logs)",
              "dict(arm=arm, seed=seed, lambda_=lam, pos_weight=10.0, best_step=best['step'], best_score=best['score'], logs=logs)")
p.write_text(s, encoding='utf-8')
print('patched train')
