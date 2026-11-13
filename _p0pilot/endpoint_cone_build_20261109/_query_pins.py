import sys
sys.path.insert(0, r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\control_signed_carrier_20261109_v3')
import Signed_common as S

g = S.raw_network(S.F / 'trans' / 's35932t200__injalpha_d1_s42__ys_abc.v', S.lib_pins)
for n in ('test_so62_orig', 'TrojanAHJ.IN1', 'U6001.Q', 'U5321.IN1', '_0384_', 'test_so62'):
    print(n, '->', g['find'](n), 'drivers', sorted(g['drivers'].get(g['find'](n), [])))
print('DFF names', sorted(c for c in g['pins'] if c.startswith('DFF'))[:12])
print('po', g['po'])
