from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\build_ctrlstrat_cones.py')
s = p.read_text(encoding='utf-8')
s = s.replace("OUT/'cones_ctrlall_D.npz'", "OUT/'cones_ctrlstrat_D.npz'")
s = s.replace("'CTRLALL_BUILD.json'", "'CTRLSTRAT_BUILD.json'")
s = s.replace("for mem in ctrl:\n    flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(0); view.append('train_control')",
              "for mem in ctrl:\n    flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(0); view.append('train_control')")
p.write_text(s, encoding='utf-8')
print('patched')
