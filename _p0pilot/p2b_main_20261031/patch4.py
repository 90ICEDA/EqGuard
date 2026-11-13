from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')
s = s.replace('        dim += 19', '        dim += K4.size(1)')
s = s.replace("        base += '_k4'", "        base += '_' + EXTRA")
s = s.replace("            tag += '_k4'", "            tag += '_' + EXTRA")
p.write_text(s, encoding='utf-8')

q = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
t = q.read_text(encoding='utf-8')
t = t.replace("+ ('_k4' if getattr(T, 'EXTRA', False) else '')", "+ ('_' + T.EXTRA if getattr(T, 'EXTRA', False) else '')")
q.write_text(t, encoding='utf-8')
print('train dim dynamic:', 'dim += K4.size(1)' in s)
print('train suffix:', s.count("base += '_' + EXTRA"), s.count("tag += '_' + EXTRA"))
print('ablate suffix:', t.count("T.EXTRA if getattr"))
