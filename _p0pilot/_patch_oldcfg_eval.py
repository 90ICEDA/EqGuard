from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\lcone_oldcfg_20261110_eval.py')
s = p.read_text(encoding='utf-8')
s = s.replace("OUT = R / '_p0pilot/lcone_v2c_20261110'", "OUT = R / '_p0pilot/lcone_oldcfg_20261110'")
s = s.replace("for arm in ('base', 'all'):\n    for seed in (42, 1, 2):", "for arm in ('all',):\n    for seed in (42,):")
p.write_text(s, encoding='utf-8')
print('patched eval')
