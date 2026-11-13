import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'phase2/ys'))
import native_boundary_extract as N


class NativeExtractionTests(unittest.TestCase):
    def test_reconvergent_complete_frontier(self):
        deps={10:[8,9],8:[1,2],9:[8,3]}
        cut,meta,status=N.choose_cut(10,deps,3,4)
        self.assertEqual(status,'eligible');self.assertLessEqual(len(cut),3)
        todo=[10]
        while todo:
            b=todo.pop()
            if b not in cut:todo.extend(deps[b])
        self.assertTrue(meta['nonlocal_cut'])

    def test_wide_gate_not_truncated_to_fake_cut(self):
        self.assertEqual(N.choose_cut(10,{10:[1,2,3,4,5]},4,4)[2],'unexpanded_target')

    def test_physical_state_complement_no_scan_mode_constraint(self):
        m=dict(ports={'scan':dict(direction='input',bits=[1])},
               cells={'ff':dict(type='SDFFX1',connections={'D':[1],'SE':[1],'Q':[2],'QN':[3]})})
        lines,width=N.logic(m)
        self.assertIn('assign b2=env[1];',lines)
        self.assertIn('assign b3=~env[1];',lines)
        self.assertEqual(width,2)
        self.assertNotIn('?', '\n'.join(lines))

    def test_cycles_and_unknown_cells_fail_closed(self):
        m=dict(ports={},cells={'a':dict(type='INVX0',connections={'IN':[2],'QN':[1]}),
                               'b':dict(type='INVX0',connections={'IN':[1],'QN':[2]})})
        with self.assertRaises(ValueError):N.dependency_index(m)
        m['cells']['a']['type']='UNSUPPORTED'
        with self.assertRaises(ValueError):N.logic(m)

    def test_undriven_and_multiply_driven_bits_rejected(self):
        m=dict(ports={'a':dict(direction='input',bits=[1])},
               cells={'a':dict(type='INVX0',connections={'IN':[99],'QN':[2]})})
        with self.assertRaises(ValueError):N.logic(m)
        m['cells']['a']['connections']={'IN':[1],'QN':[1]}
        with self.assertRaises(ValueError):N.logic(m)


if __name__=='__main__':unittest.main()
