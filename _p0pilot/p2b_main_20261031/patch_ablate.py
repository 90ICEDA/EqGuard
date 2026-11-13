from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
s = p.read_text(encoding='utf-8')

s = s.replace(
    'import train_ab as T',
    'import train_ab as T\nDIM = 21 if getattr(T, "ENCODING", "39") == "prim" else 39\nSPLIT = 7 if DIM == 21 else 29')
for a, b in [
    ('GINNodeClassifier(39, 64, 2, 2)', 'GINNodeClassifier(DIM, 64, 2, 2)'),
    ('GINNodeClassifier(39, 64, 2, 4)', 'GINNodeClassifier(DIM, 64, 2, 4)'),
    ('GINDual(39, 64, 2, num_layers=2, split=29, fusion=', 'GINDual(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='),
    ('DualPost(39, 64, 2, num_layers=2, split=29, fusion=', 'DualPost(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='),
    ('DualPost2(39, 64, 2, num_layers=2, split=29, fusion=', 'DualPost2(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='),
    ('DualMixPost(39, 64, 2, num_layers=2, split=29, fusion=', 'DualMixPost(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='),
    ('DualMixPost(39, 64, 2, num_layers=3, split=29, fusion=', 'DualMixPost(DIM, 64, 2, num_layers=3, split=SPLIT, fusion='),
    ('DualConcatPost(39, 64, 2, num_layers=2, split=29, fusion=', 'DualConcatPost(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='),
    ('DualMixConcat(39, 64, 2, num_layers=2, split=29, fusion=', 'DualMixConcat(DIM, 64, 2, num_layers=2, split=SPLIT, fusion='),
    ('self.mix = Linear(39, 39)', 'self.mix = Linear(DIM, DIM)'),
    ("out = H / 'runs_ablate' / f'{variant}_s{SEED}';",
     "out = H / 'runs_ablate' / (f'{variant}_s{SEED}' + ('_prim' if DIM == 21 else ''));"),
    ("out = H / 'runs_ablate' / f'{variant}_s{SEED}'",
     "out = H / 'runs_ablate' / (f'{variant}_s{SEED}' + ('_prim' if DIM == 21 else ''))"),
    ("T.write(H / f'ablate_report_s{SEED}.json', rep)",
     "T.write(H / (f'ablate_report_s{SEED}' + ('_prim' if DIM == 21 else '') + '.json'), rep)"),
]:
    s = s.replace(a, b)

p.write_text(s, encoding='utf-8')
print('patched')
