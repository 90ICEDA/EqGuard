import unittest
from audit import replay
from native import emit,layout


def toy(alias=False):
    return dict(ports={'input':dict(direction='input',bits=[1]),'out':dict(direction='output',bits=[3])},
        netnames={'a':dict(bits=[1]),'b':dict(bits=[1 if alias else 2]),'c':dict(bits=[2]),'d':dict(bits=[3]),'target':dict(bits=[3])},
        cells={'not':dict(type='INVX0',connections={'IN':[1],'QN':[2]}),
               'xor':dict(type='XOR2X1',connections={'IN1':[1],'IN2':[2],'Q':[3]})})


class ContextTests(unittest.TestCase):
    def test_slot_order_matches_verilog_pattern(self):
        for n in range(16):
            p=format(n,'04b');literal=int(''.join(reversed(p)),2)
            self.assertEqual([int(c) for c in p],[(literal>>i)&1 for i in range(4)])

    def test_native_no_operating_mode_constraints(self):
        code,_=emit(toy(),'impl',['a','b','c','d','target'])
        self.assertNotIn('sys_rst_l',code);self.assertNotIn('test_mode',code)
        self.assertNotIn('intervention',code)

    def test_logical_aliases_are_preserved(self):
        code,spec=emit(toy(True),'impl',['a','b','c','d','target'])
        self.assertEqual(spec['probes'][0],spec['probes'][1])
        self.assertIn('output [4:0] sigs',code)
        # No last-write '-set alias 0 -set alias 1'; the table wrapper uses one equality predicate.

    def test_replay_unknown_is_not_forced_zero(self):
        v=replay(toy(),'x');self.assertIsNone(v[1]);self.assertIsNone(v[3])

    def test_replay_propagates_truth(self):
        for bit in ['0','1']:self.assertEqual(replay(toy(),bit)[3],1)

    def test_physical_state_q_qn_complement(self):
        m=dict(ports={},netnames={},cells={'ff':dict(type='SDFFX1',connections={'Q':[1],'QN':[2],'D':[1]})})
        v=replay(m,'0');self.assertEqual((v[1],v[2]),(0,1))

    def test_missing_scalar_boundary_rejected(self):
        m=toy();m['netnames']['a']['bits']=[1,2]
        with self.assertRaises(ValueError):emit(m,'impl',['a','b','c','d','target'])

    def test_unknown_cell_fails_closed(self):
        m=toy();m['cells']['xor']['type']='UNSUPPORTED'
        with self.assertRaises(ValueError):emit(m,'impl',['a','b','c','d','target'])


if __name__=='__main__':unittest.main()
