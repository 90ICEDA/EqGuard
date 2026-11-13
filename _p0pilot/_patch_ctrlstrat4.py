from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_ctrlstrat4.py')
s = p.read_text(encoding='utf-8')
s = s.replace("run_ctrlstrat_s{seed}_lam{lam}", "run_ctrlstrat4_s{seed}_lam{lam}")
s = s.replace("'ys_aig':0.2,'ys_nand':0.2", "'ys_aig':0.0,'ys_nand':0.2")
s = s.replace("mode='recipe_stratified'", "mode='recipe_stratified_v4'")
p.write_text(s, encoding='utf-8')
print('patched')
