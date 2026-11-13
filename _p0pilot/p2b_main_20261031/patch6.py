from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
s = p.read_text(encoding='utf-8')
old = 'DIM = (21 if getattr(T, "ENCODING", "39") == "prim" else 39) + (19 if getattr(T, "EXTRA", False) else 0)'
new = 'DIM = (21 if getattr(T, "ENCODING", "39") == "prim" else 39) + (int(T.K4.size(1)) if getattr(T, "EXTRA", False) else 0)'
assert old in s
p.write_text(s.replace(old, new), encoding='utf-8')
print('dim now dynamic')
