from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')
old = """    if EXTRA in ('k4n', 'k4f'):
        _gid = np.load(MAPD / 'x39row_to_global_train.npy')
        _tr = _gid[_gid < 3220146]
        _thr = 0.0 if EXTRA == 'k4n' else 0.2
        _keep = [c for c in range(18) if float(_k[_tr, c].std()) > _thr]"""
new = """    if EXTRA in ('k4n', 'k4f', 'k4s'):
        _gid = np.load(MAPD / 'x39row_to_global_train.npy')
        _tr = _gid[_gid < 3220146]
        if EXTRA == 'k4s':
            _keep = [0, 5, 13, 11, 8, 15]   # k_over_4, infeasible, max_input_influence, change_on_comparable, ones_on_forced, complete_restricted
        else:
            _thr = 0.0 if EXTRA == 'k4n' else 0.2
            _keep = [c for c in range(18) if float(_k[_tr, c].std()) > _thr]"""
assert old in s
s = s.replace(old, new)
s = s.replace("        _k = np.concatenate([_z, _k[:, 18:19]], 1) if EXTRA == 'k4n' else _z",
              "        _k = np.concatenate([_z, _k[:, 18:19]], 1) if EXTRA in ('k4n', 'k4f') else _z")
s = s.replace("    split = 7 if dim == 21 else 29",
              "    split = int(os.environ.get('P2B_SPLIT', 7 if dim == 21 else 29))")
p.write_text(s, encoding='utf-8')

q = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
t = q.read_text(encoding='utf-8')
t = t.replace("SPLIT = 7 if DIM == 21 else 29", "SPLIT = int(os.environ.get('P2B_SPLIT', 7 if DIM == 21 else 29))")
q.write_text(t, encoding='utf-8')
print('k4s keep:', '_keep = [0, 5, 13, 11, 8, 15]' in s)
print('split env:', "P2B_SPLIT" in s, "P2B_SPLIT" in t)
