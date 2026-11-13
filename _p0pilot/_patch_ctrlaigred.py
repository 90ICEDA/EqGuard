from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_ctrlaigred.py')
s = p.read_text(encoding='utf-8')
s = s.replace("cones_ctrlstrat_D.npz", "cones_ctrlaigred_D.npz")
s = s.replace("run_ctrlstrat_s{seed}_lam{lam}", "run_ctrlaigred_s{seed}_lam{lam}")
s = s.replace("mode='recipe_stratified'", "mode='recipe_stratified_aigred'")
p.write_text(s, encoding='utf-8')
print('patched')
