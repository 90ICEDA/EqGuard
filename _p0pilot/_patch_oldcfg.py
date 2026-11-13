from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\lcone_oldcfg_20261110_train.py')
s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_v2c_20261110'", "OUT = R / '_p0pilot/lcone_oldcfg_20261110'\nCONE_DIR = R / '_p0pilot/lcone_v2c_20261110'")
s = s.replace("c = np.load(OUT / f'cones_v2c_{arm}_D.npz')", "c = np.load(CONE_DIR / f'cones_v2c_{arm}_D.npz')")
s = s.replace("l_c = CL.cone_loss(lt, ct);\n        loss = l_t + l_c", "l_c = CL.cone_loss(lt, ct, pos_weight=30.0);\n        loss = l_t + 10.0 * l_c")
s = s.replace("dict(arm=arm, seed=seed, best_step=best['step'], best_score=best['score'], logs=logs)",
              "dict(arm=arm, seed=seed, lambda_=10.0, pos_weight=30.0, best_step=best['step'], best_score=best['score'], logs=logs)")
p.write_text(s, encoding='utf-8')
print('patched')
