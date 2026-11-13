from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
s = p.read_text(encoding='utf-8')
s = s.replace(
    "+ ('_prim' if DIM == 21 else '')",
    "+ ('_prim' if DIM == 21 else '') + ('_k4' if getattr(T, 'EXTRA', False) else '')")
p.write_text(s, encoding='utf-8')
print(s.count("'_k4'"))
