"""Independent exhaustive Boolean oracles and protocol failure regressions."""
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'phase2/ys'))
import sat_functional_relations as P0
import sat_functional_relations_v3 as V3
from sat_boundary_semantics import classify, input_influence, summarize


def parsed(k, outputs, kind='gate', patterns=None):
    pats = list(itertools.product((0, 1), repeat=k)) if patterns is None else patterns
    case = dict(kind=kind, cut={('S0' if i == 0 and kind == 'mux' else f'c{i}'): f'n{i}'
                                for i in range(k)}, _patterns=pats, _nq=2*len(pats))
    pairs = {0: ['refuted', 'proved'], 1: ['proved', 'refuted'],
             None: ['refuted', 'refuted'], 'impossible': ['proved', 'proved'],
             'unknown': ['unknown', 'refuted']}
    return V3.parse_case(case, [s for value in outputs for s in pairs[value]])


class SemanticsTests(unittest.TestCase):
    def test_all_two_and_three_input_functions(self):
        for k in (2, 3):
            pats = list(itertools.product((0, 1), repeat=k))
            lookup = {p: j for j, p in enumerate(pats)}
            for values in itertools.product((0, 1), repeat=2**k):
                out = parsed(k, values)
                expected = []
                for i in range(k):
                    changed = sum(values[j] != values[lookup[p[:i]+(1,)+p[i+1:]]]
                                  for j, p in enumerate(pats) if p[i] == 0)
                    expected.append(changed)
                self.assertEqual(out['influence_changed_i'], ';'.join(map(str, expected)))
                self.assertEqual(out['influence'], int(any(expected)))
                self.assertEqual(out['decided'], 1)

    def test_mux_selector_coordinate(self):
        values = [b if s else a for s, a, b in itertools.product((0, 1), repeat=3)]
        self.assertEqual(parsed(3, values, 'mux')['influence_changed_i'], '2;2;2')
        # Input positions differ: Y=S0 must not be mistaken for Y=B.
        out = parsed(3, [s for s, a, b in itertools.product((0, 1), repeat=3)], 'mux')
        self.assertEqual(out['influence_changed_i'], '4;0;0')
        self.assertEqual(out['control_influence'], 1)

    def test_mux_data_influence_not_rejected_for_constant_selector_effect(self):
        out = parsed(3, [a for s, a, b in itertools.product((0, 1), repeat=3)], 'mux')
        self.assertEqual(out['control_influence'], 0)
        self.assertEqual(out['status'], 'proved')

    def test_partial_table_pairs_by_coordinates_not_row_xor(self):
        out = parsed(3, [0, 1], patterns=[(0, 0, 0), (1, 1, 1)])
        self.assertEqual(out['influence'], 0)
        self.assertEqual(out['influence_valid'], 0)
        self.assertEqual(out['decided'], 0)

    def test_pattern_budget_is_a_real_cap(self):
        for k in range(1, 6):
            for cap in range(1, 18):
                pats = V3.pattern_list(k, cap)
                self.assertLessEqual(len(pats), cap)
                self.assertEqual(len(set(pats)), len(pats))
        with self.assertRaises(ValueError):
            V3.pattern_list(4, 0)

    def test_reordered_partial_table_has_correct_input(self):
        out = parsed(3, [0, 1, 0], patterns=[(1, 0, 0), (0, 0, 0), (1, 0, 1)])
        self.assertEqual(out['influence_changed_i'], '1;0;0')

    def test_infeasible_and_undetermined_are_not_unknown(self):
        self.assertEqual(classify('proved', 'proved'), ('infeasible', 'not_applicable'))
        self.assertEqual(classify('refuted', 'refuted'), ('feasible', 'undecided'))
        self.assertEqual(parsed(2, ['impossible']*4)['status'], 'infeasible_domain')
        self.assertEqual(parsed(2, [None]*4)['forced_patterns'], 0)
        # A restricted domain with no comparable input pair proves no absence.
        out = parsed(2, [0, 'impossible', 'impossible', 0])
        self.assertEqual(out['decided'], 1)
        self.assertEqual(out['status'], 'functional_influence_unassessed')

    def test_unknown_never_creates_influence_or_complete_function(self):
        out = parsed(2, [0, 'unknown', None, 'impossible'])
        self.assertEqual(out['influence'], 0)
        self.assertEqual(out['decided'], 0)
        self.assertGreater(out['q_unknown'], 0)

    def test_missing_or_invalid_complete_descriptor_rejected(self):
        with self.assertRaises(ValueError):
            summarize({'00': ('feasible', '0')}, 2)
        with self.assertRaises(ValueError):
            input_influence({'0?': ('feasible', '0')}, 2)

    def test_timeout_in_middle_preserves_all_query_slots(self):
        log = ('SATQ000000\nno model found: SUCCESS\n'
               'SATQ000001\nTIMEOUT\nSATQ000002\nmodel found: FAIL\n')
        self.assertEqual(P0.parse_results(log), ['proved', 'unknown', 'refuted'])
        self.assertEqual(P0.parse_results('SATQ000000\nERROR: x\n'), ['error'])

    def test_duplicate_marker_rejected(self):
        with self.assertRaises(ValueError):
            P0.parse_results('SATQ000000\nSATQ000000\n')

    def test_alias_self_cut_and_vector_rejected_before_direct_set(self):
        g = dict(names={1:'a', 2:'b', 3:'y'}, netnames={'alias':dict(bits=[1])})
        for c in [dict(cut={'a':'a', 'b':'alias'}, target='y'),
                  dict(cut={'a':'a'}, target='a')]:
            with self.assertRaises(ValueError):
                V3.validate_case_boundary(g, c)

    def test_structural_reach_counts_d_pins_not_clock_reset_or_bits(self):
        g = dict(names={1:'a', 2:'b', 3:'q', 4:'qn'},
                 netnames={'alias':dict(bits=[1])},
                 ports={'out':dict(direction='output', bits=[3])},
                 cells={'ff1':dict(type='DFFX1', connections={'D':[1], 'CLK':[2], 'Q':[3]}),
                        'ff2':dict(type='DFFX1', connections={'D':[1], 'RN':[2], 'QN':[4]})})
        ix = P0.forward_index(g)
        self.assertEqual(P0.forward_reach(g, ['alias'], index=ix), (0, 2))
        self.assertEqual(P0.forward_reach(g, ['b'], index=ix), (0, 0))
        self.assertEqual(P0.forward_reach(g, ['q'], index=ix), (1, 0))


if __name__ == '__main__':
    unittest.main()
