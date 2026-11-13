from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
s = p.read_text(encoding='utf-8')
if "'dual_gate': None" not in s:
    s = s.replace("'dual_mix_post_cat': None,", "'dual_mix_post_cat': None, 'dual_gate': None,")
p.write_text(s, encoding='utf-8')
print("dual_gate registered:", "'dual_gate': None" in s)
