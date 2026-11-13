from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\testctl_model_compare.py')
s = p.read_text(encoding='utf-8')
old = "'ctrlonly':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlonly_s1_lam0.1/best_testpred.npz'"
new = old + ",'ctrlall':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlall_s1_lam0.1/best_testpred.npz'"
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
print('patched')
