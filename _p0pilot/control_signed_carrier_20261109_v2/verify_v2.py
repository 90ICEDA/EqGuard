"""Export -> load -> validate, plus tamper tests that must be rejected by the loader."""
import copy
import json
from pathlib import Path

import Signed_common as S
import load_relations as L

OUT = S.HERE


def main():
    base = L.load_rows(OUT / 'RELATIONS_V2.csv') + L.load_rows(OUT / 'EXTENDED_V2.csv')
    members = S.rows(OUT / 'REGION_MEMBERS_V2.csv')
    nets, snaps = {}, {'train': S.load_snapshot('train')}
    ok = L.validate(copy.deepcopy(base), members=copy.deepcopy(members), netlists=nets, snapshots=snaps)

    def mutate_polarity(rows, mem):
        rows[0]['polarity'] = '+1'

    def mutate_boundary(rows, mem):
        al = json.loads(rows[0]['boundary_aliases'])
        al[1]['target_net'] = 'TrojanAP0.IN2'
        rows[0]['boundary_aliases'] = json.dumps(al)

    def mutate_driver(rows, mem):
        rows[0]['target_driver_cells'] = 'g__0383__520'

    def mutate_context(rows, mem):
        rows[0]['context'] = 'tied;no declaration'

    def mutate_hash(rows, mem):
        rows[0]['source_sha'] = '0' * 64

    def mutate_label(rows, mem):
        rows[0]['current_y'] = '1' if rows[0]['current_y'] == '0' else '0'

    def mutate_member_polarity(rows, mem):
        target = next(m for m in mem if m['relation_id'] == 'R4_delta_DP0_carrier')
        target['polarity'] = '+1'

    def mutate_ext_polarity(rows, mem):
        ext = next(r for r in rows if r['relation_id'].startswith('V2_EXT'))
        ext['polarity'] = '-1' if ext['polarity'] == '+1' else '+1'

    tests = [
        ('T1_polarity_flip', mutate_polarity, 'polarity'),
        ('T2_boundary_swap', mutate_boundary, 'alias|polarity'),
        ('T3_driver_cell', mutate_driver, 'target_driver|row|y|trusted'),
        ('T4_context_tied', mutate_context, 'context'),
        ('T5_hash_changed', mutate_hash, 'sha'),
        ('T6_label_changed', mutate_label, 'y_mismatch|trusted'),
        ('T7_member_polarity', mutate_member_polarity, 'member_polarity'),
        ('T8_extension_polarity', mutate_ext_polarity, 'polarity'),
    ]
    results = []
    for name, fn, expect in tests:
        rows = copy.deepcopy(base)
        mem = copy.deepcopy(members)
        fn(rows, mem)
        try:
            L.validate(rows, members=mem, netlists=nets, snapshots=snaps)
            rejected, reason = False, 'NOT_REJECTED'
        except AssertionError as e:
            rejected, reason = True, str(e.args[0]) if e.args else 'assert'
        results.append(dict(tamper=name, expected_reason=expect, rejected=rejected, reason=reason))
        assert rejected, (name, 'tamper not rejected')
    S.table(OUT / 'TAMPER_TESTS.csv', results)

    # unchanged labels/inputs (same hash contract as the v1 round)
    c = S.read(S.CONTRACT)
    untouched = 0
    for split in ('train', 'val', 'test'):
        folder = S.ROOT / c['shared_inputs']['trans_' + split]['folder']
        for n in ('y', 'trusted', 'physical', 'x39', 'edge_index'):
            p = folder / (n + '.npy')
            rel = str(p.relative_to(S.ROOT))
            assert S.sha(p) == c['files'][rel], rel
            untouched += 1

    out = dict(passed=True, base=ok, tamper=results, untouched_files=untouched,
               training=0, SAT=0, solver_calls=0, model_forwards=0, labels_changed=False,
               files={f: S.sha(OUT / f) for f in ('RELATIONS_V2.csv', 'REGION_MEMBERS_V2.csv',
                                                  'TAMPER_TESTS.csv', 'load_relations.py', 'build_v2.py')})
    S.write_json(OUT / 'VERIFY_V2.json', out)
    print(json.dumps({k: v for k, v in out.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
