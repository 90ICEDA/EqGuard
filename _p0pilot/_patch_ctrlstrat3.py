from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_ctrlstrat3.py')
s = p.read_text(encoding='utf-8')
s = s.replace("run_ctrlstrat_s{seed}_lam{lam}", "run_ctrlstrat3_s{seed}_lam{lam}")
s = s.replace("'ys_aig':4.0,'ys_nand':10.0", "'ys_aig':4.0,'ys_nand':20.0")
s = s.replace("mode='recipe_stratified'", "mode='recipe_stratified_v3'")
p.write_text(s, encoding='utf-8')
print('patched')
