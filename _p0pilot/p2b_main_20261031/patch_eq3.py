from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')
s = s.replace("    _tr = np.load(P2 / 'trans_train' / 'trusted.npy')",
              "    _tr = np.load(ROOT / CONTRACT['shared_inputs']['trans_train']['folder'] / 'trusted.npy')")
p.write_text(s, encoding='utf-8')
print('fixed:', "CONTRACT['shared_inputs']['trans_train']" in s)
