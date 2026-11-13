import unittest
import numpy as np
from audit_repair import boundary_check, inclusive_hops, table_pairs


class AuditTests(unittest.TestCase):
    def test_hops_include_seeds_and_previous_hops(self):
        e = np.array([[0, 1], [1, 2]])
        seed = np.array([True, False, False])
        hs = inclusive_hops(seed, e, 2)
        self.assertEqual(np.flatnonzero(hs[2]).tolist(), [0, 1, 2])
        self.assertEqual(np.flatnonzero(hs[1]).tolist(), [0, 1])

    def test_existing_first_hop_is_not_new_second_hop_coverage(self):
        e = np.array([[0, 1], [1, 2]])
        old = inclusive_hops(np.array([False, True, False]), e, 2)[2]
        new = inclusive_hops(np.array([True, False, False]), e, 2)[2]
        self.assertFalse((new & ~old)[2])

    def test_influence_requires_both_sides_forced(self):
        _, pairs = table_pairs('0:feasible:0;1:feasible:undecided', 1)
        self.assertEqual(pairs, [[0, 0]])

    def test_infeasible_is_not_a_blocked_pair(self):
        _, pairs = table_pairs('0:infeasible:not_applicable;1:feasible:1', 1)
        self.assertEqual(pairs, [[0, 0]])

    def test_missing_pattern_rejected(self):
        with self.assertRaises(ValueError):
            table_pairs('0:feasible:0', 1)

    def test_unselected_external_dependency_rejects_full_boundary(self):
        idx = dict(bit_driver={2: {'g'}}, dff_cells={}, cell_inputs={'g': [('A', [0]), ('B', [1])]})
        self.assertFalse(boundary_check(idx, 2, {0})['boundary_closed'])
        self.assertTrue(boundary_check(idx, 2, {0, 1})['boundary_closed'])


if __name__ == '__main__':
    unittest.main()
