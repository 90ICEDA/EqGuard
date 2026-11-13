from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')
old = """    if EXTRA == 'k4n':
        _gid = np.load(MAPD / 'x39row_to_global_train.npy')
        _tr = _gid[_gid < 3220146]
        _keep = [c for c in range(18) if float(_k[_tr, c].std()) > 0]
        _m = _k[_tr][:, _keep].mean(0); _s = np.maximum(_k[_tr][:, _keep].std(0), 1e-6)
        _z = np.clip((_k[:, _keep] - _m) / _s, -10, 10)
        _k = np.concatenate([_z, _k[:, 18:19]], 1)"""
new = """    if EXTRA in ('k4n', 'k4f'):
        _gid = np.load(MAPD / 'x39row_to_global_train.npy')
        _tr = _gid[_gid < 3220146]
        _thr = 0.0 if EXTRA == 'k4n' else 0.2
        _keep = [c for c in range(18) if float(_k[_tr, c].std()) > _thr]
        _m = _k[_tr][:, _keep].mean(0); _s = np.maximum(_k[_tr][:, _keep].std(0), 1e-6)
        _z = np.clip((_k[:, _keep] - _m) / _s, -10, 10)
        _k = np.concatenate([_z, _k[:, 18:19]], 1) if EXTRA == 'k4n' else _z"""
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
print('patched k4f')
