from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')
s = s.replace("        _k = np.concatenate([_z, _k[:, 18:19]], 1) if EXTRA in ('k4n', 'k4f') else _z",
              "        _k = np.concatenate([_z, _k[:, 18:19]], 1) if EXTRA == 'k4n' else _z")
p.write_text(s, encoding='utf-8')

q = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
t = q.read_text(encoding='utf-8')
old = "+ ('_' + T.EXTRA if getattr(T, 'EXTRA', False) else '')"
new = old + " + (f'_sp{SPLIT}' if SPLIT != (7 if DIM == 21 else 29) else '')"
if new not in t:
    t = t.replace(old, new)
q.write_text(t, encoding='utf-8')
print('k4f 9-dim:', "if EXTRA == 'k4n' else _z" in s)
print('split suffix:', t.count("_sp{SPLIT}"))
