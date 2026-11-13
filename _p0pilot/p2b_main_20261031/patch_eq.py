from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')

anchor = "def extra_for(split):"
setup = '''EQ = float(os.environ.get('P2B_EQ', '0'))
EQ_PERM = os.environ.get('P2B_EQ_PERM', '0') == '1'
PAIRS = None
if EQ > 0:
    _z = np.load(ROOT / 'generate_trans/folds/hosts_bt31/data/processed/satrel_node_pairs.npz')
    _a, _b, _k = _z['a'], _z['b'], _z['kind']
    _gid = np.load(MAPD / 'x39row_to_global_train.npy')
    _inv = np.full(int(_gid.max()) + 1, -1, np.int64)
    _inv[_gid] = np.arange(len(_gid))
    _m = _k == 0
    _ra = _inv[_a[_m]]; _rb = _inv[_b[_m]]
    _ok = (_ra >= 0) & (_rb >= 0)
    _tr = np.load(P2 / 'trans_train' / 'trusted.npy')
    _ok &= _tr[_ra] & _tr[_rb]
    _ra, _rb = _ra[_ok], _rb[_ok]
    if EQ_PERM:
        _rng = np.random.default_rng(20261031)
        _rb = _rb[_rng.permutation(len(_rb))]
    PAIRS = (torch.from_numpy(_ra).to(DEVICE), torch.from_numpy(_rb).to(DEVICE))
    print(f'[EQ] lambda={EQ} pairs={_ra.size} perm={EQ_PERM}', flush=True)


'''
assert anchor in s
s = s.replace(anchor, setup + anchor, 1)

old_loop = """        for d in (o, t):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(d['x'], d['edge'])
            loss = domain_loss(logits, d['y'], d['mask']); loss.backward(); losses.append(float(loss.detach())); del loss, logits"""
new_loop = """        for _name, d in (('orig', o), ('trans', t)):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(d['x'], d['edge'])
            loss = domain_loss(logits, d['y'], d['mask'])
            if _name == 'trans' and PAIRS is not None:
                _p = torch.softmax(logits.float(), 1)[:, 1]
                _ia, _ib = PAIRS
                _sel = torch.randint(0, _ia.numel(), (min(4096, int(_ia.numel())),), device=DEVICE)
                loss = loss + EQ * (_p[_ia[_sel]] - _p[_ib[_sel]]).abs().mean()
            loss.backward(); losses.append(float(loss.detach())); del loss, logits"""
assert old_loop in s
s = s.replace(old_loop, new_loop, 1)

s = s.replace("    if EPOCHS != 100:\n        base += f'_e{EPOCHS}'",
              "    if EPOCHS != 100:\n        base += f'_e{EPOCHS}'\n    if EQ > 0:\n        base += f'_eq{EQ:g}'\n        if EQ_PERM:\n            base += 'p'", 1)
s = s.replace("        if EPOCHS != 100:\n            tag += f'_e{EPOCHS}'",
              "        if EPOCHS != 100:\n            tag += f'_e{EPOCHS}'\n        if EQ > 0:\n            tag += f'_eq{EQ:g}'\n            if EQ_PERM:\n                tag += 'p'", 1)
p.write_text(s, encoding='utf-8')
print('EQ setup:', 'PAIRS = (torch.from_numpy' in s)
print('loop patched:', "_name == 'trans' and PAIRS is not None" in s)
print('suffix count:', s.count("_eq{EQ:g}"))
