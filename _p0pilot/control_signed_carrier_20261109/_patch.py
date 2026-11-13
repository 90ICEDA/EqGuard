from pathlib import Path

p = Path(r'_p0pilot/control_signed_carrier_20261109/build_relations.py')
s = p.read_text(encoding='utf-8')
s = s.replace(
    "lineage = {r['node_name']: r for r in S.rows(S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')\n               if r['side'] in ('positive', 'M')}",
    "lineage = {(r['source'], r['node_name']): r for r in S.rows(S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')}")
s = s.replace("lineage['TrojanAP2']", "lineage[(src_alpha, 'TrojanAP2')]")
s = s.replace("lineage['TrojanAT1']", "lineage[(src_alpha, 'TrojanAT1')]")
s = s.replace("lineage[gate]", "lineage[(src_delta, gate)]")
s = s.replace("lineage['TrojanDP0']", "lineage[(src_delta, 'TrojanDP0')]")
s = s.replace(
    "        mid, _ = S.evaluate(t_delta, S.LIB, base + '.Q', et_d)\n        tgt_v, _ = S.evaluate(t_delta, S.LIB, gate + '.Q', et_d)",
    "        _, base_net = S.output_net(t_delta, base)\n        _, inv_net = S.output_net(t_delta, inv)\n        mid, _ = S.evaluate(t_delta, S.LIB, base_net, et_d)\n        tgt_v, _ = S.evaluate(t_delta, S.LIB, inv_net, et_d)")
s = s.replace("named_v, _ = S.evaluate(t_alpha, S.LIB, 'TrojanA_p2_528.Q', et)", "named_v, _ = S.evaluate(t_alpha, S.LIB, 'TrojanAHJ.IN2', et)")
p.write_text(s, encoding='utf-8')
print('patched')
