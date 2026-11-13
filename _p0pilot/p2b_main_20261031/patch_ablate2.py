from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
s = p.read_text(encoding='utf-8')
old = 'DIM = 21 if getattr(T, "ENCODING", "39") == "prim" else 39'
new = 'DIM = (21 if getattr(T, "ENCODING", "39") == "prim" else 39) + (19 if getattr(T, "EXTRA", False) else 0)'
if old in s:
    s = s.replace(old, new)
s = s.replace('self.mix = Linear(39, 39)', 'self.mix = Linear(DIM, DIM)')
p.write_text(s, encoding='utf-8')
print('DIM line present:', 'getattr(T, "EXTRA"' in s)
print('mix line:', 'self.mix = Linear(DIM, DIM)' in s)
