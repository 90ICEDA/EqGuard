from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_pw1.py')
s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_scale_20261110'", "OUT = R / '_p0pilot/lcone_directions_20261110'")
s = s.replace("run_{arm}_s{seed}_lam{lam}", "run_max_pw1_s{seed}_lam{lam}")
s = s.replace("CL.cone_loss(lt, ct, pos_weight=10.0)", "CL.cone_loss(lt, ct, pos_weight=1.0)")
p.write_text(s, encoding='utf-8')
print('patched')
