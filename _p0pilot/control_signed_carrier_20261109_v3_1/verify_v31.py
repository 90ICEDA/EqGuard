"""v3 tamper suite: 8 original + 4 new combined attacks; each must be rejected by load_v3.validate."""
import copy
import importlib.util
import json

import Signed_common as S

OUT = S.HERE
_spec = importlib.util.spec_from_file_location('signed_carrier_load_v3', OUT / 'load_v31.py')
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)


def main():
    base = L.load_rows(OUT / 'RELATIONS_V31.csv')
    members = S.rows(OUT / 'REGION_MEMBERS_V31.csv')
    nets, snaps = {}, {'train': S.load_snapshot('train')}
    ok = L.validate(copy.deepcopy(base), members=copy.deepcopy(members), netlists=nets, snapshots=snaps)

    def mut_phase(rows, mem):
        rows[0]['polarity'] = '+1'

    def mut_boundary(rows, mem):
        al = json.loads(rows[0]['boundary_aliases'])
        al[1]['target_net'] = 'TrojanAP0.IN2'
        rows[0]['boundary_aliases'] = json.dumps(al)

    def mut_driver(rows, mem):
        rows[0]['target_driver_cells'] = 'g__0383__520'

    def mut_ctx_free(rows, mem):
        c = json.loads(rows[0]['context'])
        c['free_vars'] = c['free_vars'][:-1]
        rows[0]['context'] = json.dumps(c)

    def mut_hash(rows, mem):
        rows[0]['source_sha'] = '0' * 64

    def mut_label(rows, mem):
        rows[0]['current_y'] = '1' if rows[0]['current_y'] == '0' else '0'

    def mut_member(rows, mem):
        m = next(x for x in mem if x['relation_id'] == 'R4_delta_DP0_carrier')
        m['polarity'] = '+1'

    def mut_ext(rows, mem):
        r = next(x for x in rows if x['relation_id'].startswith('V2_EXT'))
        r['polarity'] = '-1' if r['polarity'] == '+1' else '+1'

    # new combined attacks
    def mut_exact_invert(rows, mem):
        r = next(x for x in rows if x['relation_id'] == 'R1_alpha_P2_carrier')
        al = json.loads(r['boundary_aliases'])
        al[2]['invert'] = True          # exact_name alias forced inverted
        r['boundary_aliases'] = json.dumps(al)

    def mut_source_signal(rows, mem):
        r = next(x for x in rows if x['relation_id'] == 'R1_alpha_P2_carrier')
        r['source_signal'] = 'TrojanA_t1'   # exists, but driven by TrojanAT1

    def mut_ctx_conflict(rows, mem):
        r = next(x for x in rows if x['relation_id'] == 'R3_alpha_H_carrier')
        c = json.loads(r['context'])
        c['fixed'] = {'test_so62_orig': '0'}   # fixed conflicts with free var
        r['context'] = json.dumps(c)

    def mut_absorbed_target(rows, mem):
        r = next(x for x in rows if x['relation_id'] == 'R6_delta_absorbed_at_output')
        r['target_observation'] = json.dumps(dict(cell='g__0473__923', pin='QN', signal='_0473_'))

    def mut_obs_signal_mismatch(rows, mem):
        r = next(x for x in rows if x['relation_id'] == 'R6_delta_absorbed_at_output')
        o = json.loads(r['target_observation'])
        o['signal'] = '_0473_'            # still driven by g__0473__923, but != target_signal
        r['target_observation'] = json.dumps(o)

    def mut_obs_cell_mismatch(rows, mem):
        r = next(x for x in rows if x['relation_id'] == 'R6_delta_absorbed_at_output')
        o = json.loads(r['target_observation'])
        o['cell'] = 'g__0473__923'        # cell/pin disagree with target_driver_cells/target_output_pin
        o['pin'] = 'QN'
        r['target_observation'] = json.dumps(o)

    tests = [
        ('T1_polarity_flip', mut_phase, 'polarity'),
        ('T2_boundary_swap', mut_boundary, 'alias|polarity'),
        ('T3_driver_cell', mut_driver, 'target_driver'),
        ('T4_context_free_drop', mut_ctx_free, 'context_free_mismatch'),
        ('T5_hash_changed', mut_hash, 'sha'),
        ('T6_label_changed', mut_label, 'y_mismatch|trusted'),
        ('T7_member_polarity', mut_member, 'member_polarity'),
        ('T8_extension_polarity', mut_ext, 'polarity'),
        ('T9_exact_alias_forced_invert', mut_exact_invert, 'alias_invert_without_evidence'),
        ('T10_source_signal_unbound', mut_source_signal, 'source_signal'),
        ('T11_context_free_fixed_conflict', mut_ctx_conflict, 'context_free_fixed_conflict'),
        ('T12_absorbed_target_not_T', mut_absorbed_target, 'absorbed_target_expression|target_obs'),
        ('T13_obs_signal_vs_target_signal', mut_obs_signal_mismatch, 'target_obs_signal_mismatch'),
        ('T14_obs_cell_pin_vs_driver', mut_obs_cell_mismatch, 'target_obs_cell_mismatch|target_obs_pin_mismatch'),
    ]
    results = []
    for name, fn, expect in tests:
        rows = copy.deepcopy(base); mem = copy.deepcopy(members)
        fn(rows, mem)
        try:
            L.validate(rows, members=mem, netlists=nets, snapshots=snaps)
            rejected, reason = False, 'NOT_REJECTED'
        except AssertionError as e:
            rejected, reason = True, str(e.args[0]) if e.args else 'assert'
        results.append(dict(tamper=name, expected_reason=expect, rejected=rejected, reason=reason))
        assert rejected, (name, 'not rejected')
    S.table(OUT / 'TAMPER_TESTS_V31.csv', results)
    out = dict(passed=True, base=ok, tamper=results, training=0, SAT=0, solver_calls=0, model_forwards=0,
               labels_changed=False, files={f: S.sha(OUT / f) for f in
                                            ('RELATIONS_V31.csv', 'REGION_MEMBERS_V31.csv', 'TAMPER_TESTS_V31.csv',
                                             'load_v31.py')})
    S.write_json(OUT / 'VERIFY_V31.json', out)
    print(json.dumps({k: v for k, v in out.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

