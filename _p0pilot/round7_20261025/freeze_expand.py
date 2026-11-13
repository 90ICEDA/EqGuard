"""Freeze at most 16 queries' relations on eight new designs, labels never loaded."""
import hashlib
import itertools
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
R7 = ROOT / '_p0pilot/round7_20261025'
OUT = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_repair_round7'
WORK = ROOT / 'generate_trans/folds/hosts_bt31'
sys.path.insert(0, str(ROOT / '_p0pilot/round6_20261025'))
import freeze_r6 as F
from r3_nets import dff_d_targets, out_ports
from audit_repair import boundary_check


def main():
    F.R6 = R7
    split = json.loads((WORK / 'views.json').read_text())
    old = set()
    for folder, name in [('sat_nonlocal_round5', 'r5'), ('sat_expand_round6', 'r6')]:
        old.update(pd.read_csv(OUT.parent / folder / f'{name}_nonlocal_relations.csv').design.str.removesuffix('.v'))
    key = lambda s: hashlib.sha256(('r7|' + s).encode()).hexdigest()
    frozen, rejected, selected = [], [], []
    started = time.monotonic()
    for role in ('train', 'val'):
        pool = sorted([v for v in split[role + '_views'] if v not in old and 'keep' not in v
                       and (WORK / 'trans' / (v + '.v')).exists()], key=key)[:4]
        for view in pool:
            if time.monotonic() - started > 600:
                rejected.append(dict(design=view, reason='freeze_600s_cap'))
                continue
            v = WORK / 'trans' / (view + '.v')
            idx = F.load_index(v)
            targets = dff_d_targets(idx)
            for net in out_ports(idx):
                bits = idx['netbits'].get(net, ())
                if len(bits) != 1:
                    continue
                drv = idx['bit_driver'].get(bits[0], set())
                if len(drv) == 1 and not next(iter(drv)) in idx['dff_cells']:
                    targets.append(dict(target=net, bit=bits[0], kind='cone'))
            targets.sort(key=lambda t: (t['kind'], key(t['target'])))
            choices = []
            # Seek PO/DFF diversity, with deterministic fallback; no reach computation needed.
            for distinct in (True, False):
                for t in targets:
                    if len(choices) >= 2:
                        break
                    if any(t['target'] == z['target'] for z in choices):
                        continue
                    if distinct and any(t['kind'] == z['kind'] for z in choices):
                        continue
                    cut = F.deep_cut_bfs(idx, t['target'])
                    if cut['reason'] or len(cut['leaves']) != 4:
                        continue
                    cutbits = {idx['netbits'][n][0] for n in cut['leaves']}
                    boundary = boundary_check(idx, t['bit'], cutbits)
                    driver = next(iter(idx['bit_driver'][t['bit']]))
                    choices.append(dict(role=role, host=view.split('__')[0], inst=view.split('__')[1],
                        recipe=view.split('__')[-1], usage='hash_selected_no_label', design=v.name,
                        target=t['target'], kind=t['kind'], target_bit=t['bit'], driver=driver,
                        target_id=f'{v.name}|{t["bit"]}|{t["target"]}', reach_po=0, reach_dff=0,
                        reach_measured=False, cut=cut['leaves'], cut_distances=cut['distances'],
                        cut_leaf_total=cut['leaf_total'], cut_truncated=int(cut['truncated']),
                        selected_ratio=cut['selected_ratio'],
                        cut_kind='full_boundary' if boundary['boundary_closed'] else 'partial_probe',
                        **boundary, patterns=list(map(''.join, itertools.product('01', repeat=4))), n_patterns=16))
            frozen.extend(choices)
            selected.append(dict(design=view, role=role, accepted=len(choices)))
    plan = dict(created=datetime.now().astimezone().isoformat(), frozen=frozen,
                selected_designs=selected, rejected=rejected, relations=len(frozen),
                expected_queries=len(frozen) * 32,
                rule='first four previously unused non-keep views per role by sha256(r7|view); PO/DFF kinds then sha256(r7|net); no labels',
                budget=dict(max_queries=544, expansion=512, review=32, timeout_s=5, wall_cap_s=1800))
    plan['plan_sha256'] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    (OUT / 'r7_candidate_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(relations=len(frozen), expected_queries=len(frozen)*32, selected=selected), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
