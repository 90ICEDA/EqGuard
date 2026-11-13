import sys
sys.path.insert(0, r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\endpoint_cone_build_20261109')
import re
import cone_builder as B

text = 'input [3:0] a; output o;'
for st in [x.strip() for x in B._strip(text).split(';') if x.strip()]:
    m = re.match(r'^(input|inout|output)\b(.*)$', st, re.S)
    print('st', repr(st), 'match', m.groups() if m else None)
    if m:
        rest = m.group(2).strip()
        rng = re.match(r'^\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*(.*)$', rest, re.S)
        print(' rng', rng.groups() if rng else None)
print('declared', B.declared_ports(text))
print('source_has_backslash_dollar', '\\$' in B.declared_ports.__code__.co_consts[2])
print([c for c in B.declared_ports.__code__.co_consts if isinstance(c, str)])
