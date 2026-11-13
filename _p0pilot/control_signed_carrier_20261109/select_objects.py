"""Freeze the 12-object extension selection BEFORE looking at any relation result.

Rule (deterministic, hash order):
  - candidates: NODE_LINEAGE rows with key in {orig_train, orig_val} and role in {payload, output_hijack};
  - gate type must be in the supported local set;
  - order by sha256('SIGNED_CARRIER_SELECT|<source>|<gate>');
  - greedy: at most 2 objects per host, 6 per split (train / val).
No test predictions, no model scores, no labels beyond the lineage table.
"""
import collections
import hashlib

import Signed_common as S

OUT = S.HERE
SUPPORTED = {'AND2X2', 'OR2X1', 'XOR2X1', 'XNOR2X1', 'INVX0', 'NOR2X0', 'NAND2X0', 'MUX21X2', 'MX2X1_RS'}
ROLES = {'payload', 'output_hijack'}
PER_HOST = 2
PER_SPLIT = 6


def key(source, gate):
    return hashlib.sha256(f'SIGNED_CARRIER_SELECT|{source}|{gate}'.encode()).hexdigest()


def main():
    assert not (OUT / 'SELECTION.csv').exists()
    rows = S.rows(S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')
    cands = []
    for r in rows:
        if r['key'] not in ('orig_train', 'orig_val'):
            continue
        if r['role'] not in ROLES:
            continue
        if r['target_type'] not in SUPPORTED:
            continue
        cands.append(dict(split='train' if r['key'] == 'orig_train' else 'val', source=r['source'],
                          host=r['host'], gate=r['node_name'], type=r['target_type'], role=r['role'],
                          key=key(r['source'], r['node_name'])))
    chosen = []
    for split in ('train', 'val'):
        pool = sorted([c for c in cands if c['split'] == split], key=lambda c: c['key'])
        per_host = collections.Counter()
        taken = 0
        cap = PER_HOST if split == 'train' else PER_SPLIT
        for c in pool:
            if taken >= PER_SPLIT:
                break
            if per_host[c['host']] >= cap:
                continue
            per_host[c['host']] += 1
            taken += 1
            chosen.append(dict(rank=len(chosen) + 1, **c,
                               rule=f'role={c["role"]};type={c["type"]};hash-ordered;cap={cap}/host;<= {PER_SPLIT}/split'))
    S.table(OUT / 'SELECTION.csv', chosen)
    (OUT / 'SELECTION_RULE.md').write_text(
        '# Extension selection rule (frozen before probing)\n\n'
        '- Source: `_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv` (key in orig_train/orig_val).\n'
        '- Roles: payload, output_hijack; types: ' + ', '.join(sorted(SUPPORTED)) + '.\n'
        '- Order: sha256("SIGNED_CARRIER_SELECT|source|gate"), greedy with <=2 per host for train and <=6 for the single-host val split.\n'
        '- No test predictions/scores, no label-based ranking; labels are only read after selection.\n'
        '- If relations are insufficient, the extension records unresolved instead of lowering the bar.\n',
        encoding='utf-8')
    S.table(OUT / 'SELECTION_HASHES.csv', [dict(path='SELECTION.csv', sha256=S.sha(OUT / 'SELECTION.csv'))])
    print('selected', len(chosen), collections.Counter((c['split'], c['host']) for c in chosen))


if __name__ == '__main__':
    main()
