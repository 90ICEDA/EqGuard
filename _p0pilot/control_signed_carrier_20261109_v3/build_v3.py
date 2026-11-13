"""v3: rewrite the existing 8 relations with strict fields (no new candidates).

Fixes:
  1) alias inversion only via inv_formula (verified INV structure); exact/pin/driver aliases are non-inverting;
  2) source_signal must be the output of source_cell at source_output_pin (checked on load);
  3) context is structured JSON: free_vars / fixed / state (no free-text-only flag);
  4) absorbed relations carry source_observation, target_observation and host_endpoints,
     and must prove the output expression on both sides.
"""
import json

import numpy as np

import Signed_common as S

OUT = S.HERE
V2 = S.ROOT / '_p0pilot/control_signed_carrier_20261109_v2'
FLOWS = {'delta': 'ys_nand', 'alpha': 'ys_abc'}


def context(free, fixed=None, state=None):
    return json.dumps(dict(free_vars=list(free), fixed=dict(fixed or {}), state=list(state or [])), ensure_ascii=False)


def main():
    assert not (OUT / 'RELATIONS_V3.csv').exists()
    rels = S.rows(V2 / 'RELATIONS_V2.csv') + S.rows(V2 / 'EXTENDED_V2.csv')
    members = S.rows(V2 / 'REGION_MEMBERS_V2.csv')
    out = []
    for r in rels:
        q = dict(r)
        rid = q['relation_id']
        if rid == 'R1_alpha_P2_carrier':
            q['context'] = context(['n8566', 'WX3484', 'DFF_955_n1', 'n4183', 'n2940'])
        elif rid == 'R2_alpha_T_carrier':
            q['context'] = context(['n4183', 'n2940'])
        elif rid == 'R3_alpha_H_carrier':
            q['context'] = context(['test_so62_orig'], state=[dict(net='test_so62_orig', dff_cell='DFF_1081_Q_reg', pin='Q')])
        elif rid in ('R4_delta_DP0_carrier', 'R5_delta_DP2_carrier'):
            q['context'] = context(['TrojanD_t4', 'n533'])
        elif rid == 'R6_delta_absorbed_at_output':
            q['context'] = context(['TrojanD_t4', 'g10801_orig', 'n533'])
            q['source_observation'] = json.dumps(dict(cell='TrojanDHJ', pin='Q', signal='g10801'), ensure_ascii=False)
            q['target_observation'] = json.dumps(dict(cell='g_g10801_1673', pin='QN', signal='TrojanDHJ.Q'), ensure_ascii=False)
            q['host_endpoints'] = json.dumps(['g10801'], ensure_ascii=False)
        else:
            # extension relations: free vars are the alias source nets; no fixed/state
            free = [a['source_net'] for a in json.loads(q['boundary_aliases'])]
            q['context'] = context(free)
        out.append(q)
    fields = sorted({k for q in out for k in q})
    for q in out:
        for k in fields:
            q.setdefault(k, '')
    S.table(OUT / 'RELATIONS_V3.csv', [{k: q[k] for k in fields} for q in out])
    S.table(OUT / 'REGION_MEMBERS_V3.csv', members)
    S.write_json(OUT / 'BUILD_V3_SUMMARY.json', dict(relations=len(out), members=len(members),
                                                     training=0, SAT=0, model_forwards=0))
    print('built', len(out), 'relations', len(members), 'members')


if __name__ == '__main__':
    main()
