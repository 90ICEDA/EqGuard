from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\build_ctrlstrat_cones.py')
s = p.read_text(encoding='utf-8')
s = s.replace("ctrl.append(mem)", "ctrl.append((mem, r['view']))")
s = s.replace("np.mean([len(x) for x in ctrl])", "np.mean([len(x[0]) for x in ctrl])")
s = s.replace("for mem in ctrl:\n    flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(0); view.append('train_control')",
              "for mem, viewname in ctrl:\n    flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(0); view.append(viewname)")
s = s.replace("neg_mean_members=float(np.mean([len(x) for x in ctrl]))", "neg_mean_members=float(np.mean([len(x[0]) for x in ctrl]))")
s = s.replace("np.mean([len(x) for x in ctrl])", "np.mean([len(x[0]) for x in ctrl])")
p.write_text(s, encoding='utf-8')
print('patched')
