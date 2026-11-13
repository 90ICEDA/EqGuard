import json
from pathlib import Path

H = Path(r'_p0pilot/p2b_main_20261031')


def show(rel):
    p = H / rel
    s = p / 'SELECTED.json'
    if not s.exists():
        return None
    d = json.loads(s.read_text(encoding='utf-8'))
    c = json.loads((p / 'config.json').read_text(encoding='utf-8')) if (p / 'config.json').exists() else {}
    return dict(rel=str(rel), val=round(d.get('score', -1), 4), epoch=d.get('epoch'), params=c.get('parameters'))


rows = []
for s in (42, 1, 2):
    for arm in ('A', 'B'):
        rows.append(show(f'runs_oldmask/seed{s}/{arm}'))
for s in (42, 1, 2, 3, 4, 5, 6, 7):
    rows.append(show(f'runs_ablate/dual_mix_post_cat_s{s}'))
    rows.append(show(f'runs_ablate/dual_mix_post_cat_s{s}_k4f_sp39'))
for s in (42, 1, 2):
    for tag in ('k4', 'k4n', 'k4s', 'prim'):
        for arm in ('A', 'B'):
            r = show(f'runs_oldmask_{tag}/seed{s}/{arm}')
            if r:
                rows.append(r)
for r in rows:
    if r:
        print(f"{r['rel']:58s} val={r['val']:.4f} epoch={r['epoch']} params={r['params']}")
