from pathlib import Path

q = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
t = q.read_text(encoding='utf-8')

old = """        losses = []
        for d in (o, t):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(d['x'], d['edge'])
            loss = T.domain_loss(logits, d['y'], d['mask']); loss.backward(); losses.append(float(loss.detach())); del loss, logits"""
new = """        losses = []
        for _name, d in (('orig', o), ('trans', t)):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(d['x'], d['edge'])
            loss = T.domain_loss(logits, d['y'], d['mask'])
            if _name == 'trans' and getattr(T, 'PAIRS', None) is not None:
                _p = torch.softmax(logits.float(), 1)[:, 1]
                _ia, _ib = T.PAIRS
                _sel = torch.randint(0, _ia.numel(), (min(4096, int(_ia.numel())),), device=T.DEVICE)
                loss = loss + T.EQ * (_p[_ia[_sel]] - _p[_ib[_sel]]).abs().mean()
            loss.backward(); losses.append(float(loss.detach())); del loss, logits"""
assert old in t, 'loop not found'
t = t.replace(old, new, 1)

suf = "+ (f'_e{EPOCHS}' if EPOCHS != 100 else '')"
new_suf = suf + " + (f'_eq{T.EQ:g}' if getattr(T, 'EQ', 0) > 0 else '') + ('p' if getattr(T, 'EQ_PERM', False) else '')"
assert suf in t
t = t.replace(suf, new_suf)
q.write_text(t, encoding='utf-8')
print('ablate eq loop:', "T.PAIRS" in t)
print('ablate suffix:', t.count("_eq{T.EQ:g}"))
