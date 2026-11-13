"""Fixed small tests for the round-3 evidence state model."""
from __future__ import annotations

import itertools
import unittest

from sat_evidence import (classify_cut, evaluate_case, pattern_state,
                          schedule, symmetric_entropy)


def mk(cut, statuses, structure="test"):
    pats = list(itertools.product([0, 1], repeat=len(cut)))
    qids = list(range(1, 2 * len(pats) + 1))
    return evaluate_case(cut, pats, qids, statuses, structure=structure)


class TestPatternState(unittest.TestCase):
    def test_forcing(self):
        self.assertEqual(pattern_state("proved", "refuted")["forcing"], 1)
        self.assertEqual(pattern_state("refuted", "proved")["forcing"], 0)
        self.assertEqual(pattern_state("refuted", "refuted")["forcing"], "undecided")

    def test_infeasible(self):
        self.assertEqual(pattern_state("proved", "proved")["feasibility"], "infeasible")

    def test_one_sided(self):
        s = pattern_state("proved", "timeout")
        self.assertEqual(s["one_sided"], 1)
        self.assertEqual(s["feasibility"], "unknown")


class TestCases(unittest.TestCase):
    def test_sufficient_with_influence(self):
        st = {1: "proved", 2: "proved", 3: "proved", 4: "refuted",
              5: "refuted", 6: "proved", 7: "proved", 8: "refuted"}
        r = mk(["a", "b"], st)
        self.assertEqual(r["functional_sufficiency"], "proved")
        self.assertEqual(r["influence_status"], "valid")
        self.assertGreater(r["influence_max"], 0.0)

    def test_sufficient_no_influence(self):
        st = {1: "proved", 2: "proved", 3: "refuted", 4: "proved",
              5: "refuted", 6: "proved", 7: "refuted", 8: "proved"}
        r = mk(["a", "b"], st)
        self.assertEqual(r["functional_sufficiency"], "proved")
        self.assertEqual(r["influence_status"], "valid")
        self.assertEqual(r["influence_mean"], 0.0)
        self.assertEqual(r["influence_per_input"].count("|1|0|1"), 2)

    def test_satisfiable_but_cut_insufficient(self):
        st = {1: "refuted", 2: "refuted", 3: "proved", 4: "refuted",
              5: "refuted", 6: "proved", 7: "refuted", 8: "proved"}
        r = mk(["a", "b"], st)
        self.assertEqual(r["functional_sufficiency"], "not_proved")
        self.assertEqual(r["n_undecided"], 1)

    def test_infeasible_premise(self):
        st = {i: "proved" for i in range(1, 9)}
        r = mk(["a", "b"], st)
        self.assertEqual(r["functional_sufficiency"], "infeasible")
        self.assertEqual(r["n_feasible"], 0)
        self.assertEqual(r["influence_status"], "not_applicable")

    def test_input_without_comparable_pair(self):
        pats = list(itertools.product([0, 1], repeat=3))
        st, qid = {}, 1
        for p in pats:
            if p[2] == 1:
                st[qid] = st[qid + 1] = "proved"
            else:
                st[qid], st[qid + 1] = "proved", "refuted"
            qid += 2
        r = evaluate_case(["a", "b", "c"], pats, list(range(1, 17)), st)
        self.assertEqual(r["functional_sufficiency"], "proved")
        self.assertEqual(r["n_valid_influence_inputs"], 2)
        self.assertTrue(r["influence_per_input"].split(";")[2].endswith("|0"))
        self.assertIsNotNone(r["influence_mean"])

    def test_no_comparison_at_all_is_not_zero(self):
        pats = list(itertools.product([0, 1], repeat=2))
        st = {1: "proved", 2: "proved", 3: "proved", 4: "refuted",
              5: "proved", 6: "proved", 7: "proved", 8: "proved"}
        r = evaluate_case(["a", "b"], pats, [1, 2, 3, 4, 5, 6, 7, 8], st)
        self.assertEqual(r["influence_status"], "not_applicable")
        self.assertIsNone(r["influence_mean"])

    def test_mid_query_timeout(self):
        st = {1: "proved", 2: "proved", 3: "timeout", 4: "refuted",
              5: "refuted", 6: "proved", 7: "refuted", 8: "proved"}
        r = mk(["a", "b"], st)
        self.assertEqual(r["functional_sufficiency"], "unknown")
        self.assertIn("timeout=1", r["query_status"])
        self.assertEqual(r["n_feasibility_unknown"], 1)

    def test_not_enumerated_cannot_be_proved(self):
        pats = [(1, 1), (0, 0)]
        st = {1: "proved", 2: "refuted", 3: "refuted", 4: "proved"}
        r = evaluate_case(["a", "b"], pats, [1, 2, 3, 4], st,
                          enumerated=False)
        self.assertEqual(r["functional_sufficiency"], "not_enumerated")
        self.assertEqual(r["sufficiency_reason"], "patterns_not_enumerated")
        self.assertEqual(r["n_forced"], 2)


class TestCutAndSchedule(unittest.TestCase):
    def test_cut_exceeds_budget_is_partial(self):
        s, why = classify_cut(leaf_total=5, selected=3, truncated=True,
                              sat_sufficient=False)
        self.assertEqual(s, "partial_probe_of_larger_boundary")
        self.assertEqual(why, "leaf_cap_exceeded")

    def test_complete_boundary(self):
        s, _ = classify_cut(3, 3, False, False)
        self.assertEqual(s, "structural_boundary_complete")

    def test_sat_sufficient_overrides_structure(self):
        s, _ = classify_cut(5, 3, True, True)
        self.assertEqual(s, "sat_proven_sufficient")

    def test_po_not_crowded_out(self):
        cands = [("dff_next", {"target": f"d{i}"}) for i in range(10)]
        cands += [("cone", {"target": f"p{i}"}) for i in range(2)]
        r = schedule(cands, dff_budget=2, po_budget=2)
        self.assertEqual(r["accepted"], {"dff_next": 2, "cone": 2})
        cone_attempts = [a for a in r["attempts"] if a["kind"] == "cone"]
        self.assertTrue(any(a["accepted"] for a in cone_attempts))
        self.assertTrue(any(a["reason"] == "budget_exhausted" for a in r["attempts"]))


class TestEntropy(unittest.TestCase):
    def test_zero_is_a_value(self):
        r = symmetric_entropy([0, 0, 1, 1], [False] * 4)
        self.assertEqual(r["unique"], 2)
        self.assertAlmostEqual(r["entropy"], 1.0)

    def test_unknown_is_a_mask(self):
        r = symmetric_entropy([0, 1, 99], [False, False, True])
        self.assertEqual(r["n_known"], 2)
        self.assertEqual(r["n_unknown"], 1)
        self.assertEqual(r["unique"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
