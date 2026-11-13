from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\testctl_model_compare.py')
s = p.read_text(encoding='utf-8')
old = "'ctrlstrat':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlstrat_s1_lam0.1/best_testpred.npz'"
new = old + ",'Nctl':R/'_p0pilot/lcone_trainctl_20261110/run_Nctl_s1/best_testpred.npz'"
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
print('patched')
