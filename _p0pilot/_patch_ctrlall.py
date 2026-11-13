from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_ctrlall.py')
s = p.read_text(encoding='utf-8')
s = s.replace("cones_ctrlonly_D.npz", "cones_ctrlall_D.npz")
s = s.replace("run_ctrlonly_s{seed}_lam{lam}", "run_ctrlall_s{seed}_lam{lam}")
p.write_text(s, encoding='utf-8')
print('patched')
