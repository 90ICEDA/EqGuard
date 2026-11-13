from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\build_weak_cones03.py')
s = p.read_text(encoding='utf-8')
s = s.replace("nneg/len(mem)>=0.5", "nneg/len(mem)>=0.3")
s = s.replace("lcone_weak_20261110", "lcone_weak03_20261110")
s = s.replace("cones_weak_D.npz", "cones_weak03_D.npz")
s = s.replace("WEAK_BUILD.json", "WEAK03_BUILD.json")
p.write_text(s, encoding='utf-8')
print('patched')
