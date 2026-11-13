"""Summarize the compact cone cache: trusted-member coverage, trainable budget, missing cells."""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/endpoint_cone_build_20261109'
sys.path.insert(0, str(OUT))
import Signed_common as S

snaps = {sp: S.load_snapshot(sp) for sp in ('train', 'val')}
stats = S.rows(OUT / 'CONE_VIEW_STATS.csv')
tot = collections.Counter()
for r in stats:
    for k in ('cones', 'members', 'pos', 'neg', 'unknown', 'singleton', 'empty', 'trainable', 'missing'):
        tot[k] += int(r[k])
trusted_members = member_total = 0
train_members = 0
for r in S.rows(OUT / 'CONE_CACHE.csv'):
    _, arr, _, _ = snaps[r['split']]
    rows = [int(x) for x in r['member_rows'].split('|') if x]
    trusted_members += sum(1 for x in rows if bool(arr['trusted'][x]))
    member_total += len(rows)
    if int(r['label']) in (0, 1) and int(r['n_members']) >= 2:
        train_members += len(rows)
top_missing = sorted(stats, key=lambda r: -int(r['missing']))[:8]
out = dict(views=len(stats), cones=tot['cones'], members=member_total,
           pos=tot['pos'], neg=tot['neg'], unknown=tot['unknown'],
           singleton=tot['singleton'], empty=tot['empty'], trainable_cones=tot['trainable'],
           trainable_member_exposure=train_members,
           trusted_member_coverage=round(trusted_members / member_total, 6) if member_total else 0,
           missing_members=tot['missing'],
           top_missing_views=[dict(view=r['view'], missing=int(r['missing']), members=int(r['members'])) for r in top_missing],
           pos_rate=round(tot['pos'] / tot['cones'], 6), neg_rate=round(tot['neg'] / tot['cones'], 6),
           unknown_rate=round(tot['unknown'] / tot['cones'], 6))
S.write_json(OUT / 'CACHE_SUMMARY.json', out)
print(json.dumps(out, ensure_ascii=False))
