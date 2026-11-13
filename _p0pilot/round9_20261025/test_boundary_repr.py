import itertools
import unittest
import numpy as np
from boundary_repr import COLS, canonical, comparison_gate, parse_table, reindex, summarize
from prepare import drivers


def table(fn,k):
    return {p:('feasible',str(fn(p))) for p in map(''.join,itertools.product('01',repeat=k))}


class BoundaryTests(unittest.TestCase):
    def test_signature_and_descriptor_invariant_to_input_renumbering(self):
        t=table(lambda p:int(p[2] if p[0]=='1' else p[1]),3)
        expected=canonical(t,3)['signature'];values=summarize(t,3)[0]
        for order in itertools.permutations(range(3)):
            z=reindex(t,order)
            self.assertEqual(canonical(z,3)['signature'],expected)
            self.assertEqual(summarize(z,3)[0],values)

    def test_symmetry_does_not_invent_unique_correspondence(self):
        t=table(lambda p:int(p=='111'),3);c=canonical(t,3)
        self.assertFalse(c['unique_order']);self.assertEqual(len(c['orders']),6)
        self.assertEqual(c['slot_candidates'][0],[0,1,2])

    def test_partial_zero_is_not_constant_function(self):
        t=parse_table('0:feasible:0;1:feasible:undecided',1);v,_=summarize(t,1)
        self.assertEqual(v['complete_full_domain'],0);self.assertEqual(v['partial_forcing'],1)
        self.assertEqual(v['influence_valid'],0)

    def test_infeasible_does_not_become_a_forced_zero(self):
        t=parse_table('0:infeasible:not_applicable;1:feasible:1',1);v,p=summarize(t,1)
        self.assertEqual(v['complete_restricted_domain'],1)
        self.assertEqual(v['forced_fraction'],.5);self.assertEqual(p[0]['comparable'],0)

    def test_unknown_has_explicit_masks(self):
        t=parse_table('0:unknown:unknown;1:unknown:unknown',1);v,_=summarize(t,1)
        self.assertEqual(v['determinism_valid'],0);self.assertEqual(v['ones_valid'],0)
        self.assertEqual(v['has_unknown'],1);self.assertEqual(v['complete_full_domain'],0)

    def test_incomplete_duplicate_and_invalid_patterns_rejected(self):
        for text in ['0:feasible:0','0:feasible:0;0:feasible:1','0:feasible:0;2:feasible:1']:
            with self.assertRaises(ValueError):parse_table(text,1)

    def test_signature_similarity_is_not_a_signal_proof(self):
        self.assertFalse(comparison_gate('same','same')['semantic_pair_allowed'])

    def test_context_mismatch_rejects_even_with_proof_and_roles(self):
        self.assertFalse(comparison_gate('mode0','unrestricted',True,True)['training_pair_allowed'])

    def test_bit_equivalence_does_not_transfer_safety_labels(self):
        gate=comparison_gate('same','same',True,False)
        self.assertTrue(gate['semantic_pair_allowed']);self.assertFalse(gate['training_pair_allowed'])

    def test_known_library_pin_schema_not_bare_net_guess(self):
        m={'cells':{'g':{'type':'INVX0','connections':{'IN':[1],'QN':[2]}}}}
        self.assertEqual(drivers(m,2),[('g','QN')]);self.assertEqual(drivers(m,1),[])

    def test_unknown_library_fails_closed(self):
        with self.assertRaises(ValueError):drivers({'cells':{'g':{'type':'unknown','connections':{'Q':[2]}}}},2)

    def test_descriptor_bounded(self):
        t=table(lambda p:int(p=='1111'),4);v,_=summarize(t,4)
        a=np.asarray([v[c] for c in COLS]);self.assertTrue(np.isfinite(a).all())
        self.assertTrue(((a>=0)&(a<=1)).all())


if __name__=='__main__':unittest.main()
