import unittest
from case_chain import evaluate, emit


def toy():
    return dict(ports={'a':dict(direction='input',bits=[3]),'x':dict(direction='input',bits=[1]),
                       'y':dict(direction='input',bits=[2]),'out':dict(direction='output',bits=[6])},
                netnames={n:dict(bits=[b]) for n,b in [('s',4),('a',3),('b',5),('out',6)]},
                cells={'trigger':dict(type='AND2X2',connections={'IN1':[1],'IN2':[2],'Q':[4]}),
                       'payload':dict(type='XOR2X1',connections={'IN1':[4],'IN2':[3],'Q':[5]}),
                       'hijack':dict(type='MX2X1_RS',connections={'A':[3],'B':[5],'S0':[4],'Y':[6]})})


class ReplayTests(unittest.TestCase):
    def test_wire_intervention_can_change_payload_input(self):
        m=toy();natural=evaluate(m,'100');other=evaluate(m,'100',(4,1))
        self.assertEqual(natural[3],natural[5])
        self.assertNotEqual(other[3],other[5])
        self.assertNotEqual(natural[6],other[6])
        # A fixed functional boundary would retain natural B=0 and be blocked.
        self.assertEqual(natural[6],natural[5])

    def test_emitter_exposes_intervention(self):
        code,spec=emit(toy(),'toy','', ['s','a','b','out','out'])
        self.assertIn('intervention ? value',code)
        self.assertEqual(spec['control_bit'],4)

    def test_undefined_environment_rejected(self):
        with self.assertRaises(ValueError):evaluate(toy(),'1x0')

    def test_q_qn_share_one_physical_state(self):
        m=dict(ports={},cells={'ff':dict(type='SDFFX1',connections={'Q':[1],'QN':[2]})})
        v=evaluate(m,'1');self.assertEqual((v[1],v[2]),(1,0))

    def test_primary_input_is_not_silently_intervened(self):
        with self.assertRaises(ValueError):emit(toy(),'toy','',['a','s','b','out','out'])


if __name__=='__main__':unittest.main()
