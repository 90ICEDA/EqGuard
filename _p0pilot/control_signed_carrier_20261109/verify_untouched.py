"""Confirm labels, inputs and netlists used by this round are unchanged (hash check only)."""
import json
from pathlib import Path

import Signed_common as S

OUT = S.HERE


def main():
    c = S.read(S.CONTRACT)
    checked = {}
    for split in ('train', 'val', 'test'):
        key = 'trans_' + split
        folder = S.ROOT / c['shared_inputs'][key]['folder']
        for name in ('y', 'trusted', 'physical', 'x39', 'edge_index'):
            p = folder / (name + '.npy')
            rel = str(p.relative_to(S.ROOT))
            assert rel in c['files'], rel
            assert S.sha(p) == c['files'][rel], rel
            checked[rel] = c['files'][rel]
    # netlists used by the three cases and the 12-object extension
    sel = S.rows(OUT / 'SELECTION.csv')
    netfiles = set()
    for src in {s['source'] for s in sel}:
        netfiles.add(S.F / 'orig' / (src + '.v'))
        for p in S.F.glob('trans/' + src + '__*.v'):
            netfiles.add(p)
    for p in sorted(netfiles):
        checked[str(p.relative_to(S.ROOT))] = S.sha(p)
    S.write_json(OUT / 'UNTOUCHED.json', dict(passed=True, checked=checked, note='hash-only check; no file written'))
    print('untouched ok', len(checked), 'files')


if __name__ == '__main__':
    main()
