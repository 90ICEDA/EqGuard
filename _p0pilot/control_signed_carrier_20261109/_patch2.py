from pathlib import Path

pairs = [
    (r'_p0pilot/control_signed_carrier_20261109/build_relations.py', [
        ("'TrojanA_t1': ~(u1 | u2)}", "'n4183': u1, 'n2940': u2}"),
        ("'TrojanA_t1': (u1 | u2)}", "'n4183': u1, 'n2940': u2, 'TrojanA_t1': (u1 | u2)}"),
        ("u1=TrojanAT1.IN1,u2=TrojanAT1.IN2;T=NOT(u1 OR u2)",
         "u1=n4183~TrojanAT1.IN1,u2=n2940~TrojanAT1.IN2;T=NOT(u1 OR u2)"),
    ]),
    (r'_p0pilot/control_signed_carrier_20261109/verify_relations.py', [
        ("'TrojanA_t1': ~(u1 | u2)}", "'n4183': u1, 'n2940': u2}"),
        ("es = {'n8566': a, 'WX3484': b, 'DFF_955_n1': c, 'n4183': u1, 'n2940': u2}",
         "es = {'n8566': a, 'WX3484': b, 'DFF_955_n1': c, 'n4183': u1, 'n2940': u2}"),
    ]),
]
for fp, reps in pairs:
    p = Path(fp)
    s = p.read_text(encoding='utf-8')
    for a, b in reps:
        s = s.replace(a, b)
    p.write_text(s, encoding='utf-8')
print('patched')
