from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')
s = s.replace("EPOCHS = 100", "EPOCHS = int(os.environ.get('P2B_EPOCHS', '100'))")
s = s.replace("    if EXTRA:\n        base += '_' + EXTRA", "    if EXTRA:\n        base += '_' + EXTRA\n    if EPOCHS != 100:\n        base += f'_e{EPOCHS}'")
s = s.replace("        if EXTRA:\n            tag += '_' + EXTRA", "        if EXTRA:\n            tag += '_' + EXTRA\n        if EPOCHS != 100:\n            tag += f'_e{EPOCHS}'")
p.write_text(s, encoding='utf-8')

q = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
t = q.read_text(encoding='utf-8')
t = t.replace("SEED = int(os.environ.get('P2B_SEED', '42'))",
              "SEED = int(os.environ.get('P2B_SEED', '42'))\nEPOCHS = int(os.environ.get('P2B_EPOCHS', '100'))")
t = t.replace("def train(variant, perm=None, epochs=100):", "def train(variant, perm=None, epochs=None):\n    epochs = EPOCHS if epochs is None else epochs")
t = t.replace("+ (f'_sp{SPLIT}' if SPLIT != (7 if DIM == 21 else 29) else '')",
              "+ (f'_sp{SPLIT}' if SPLIT != (7 if DIM == 21 else 29) else '') + (f'_e{EPOCHS}' if EPOCHS != 100 else '')")
q.write_text(t, encoding='utf-8')
print('train epochs env:', "P2B_EPOCHS" in s, s.count("_e{EPOCHS}"))
print('ablate epochs env:', "P2B_EPOCHS" in t, t.count("_e{EPOCHS}"))
