"""Fixed tests for round-4 enumeration and traceability rules."""
from __future__ import annotations

import io
import unittest

import pandas as pd

from sat_evidence_v4 import (aggregate_records, enumeration_status,
                             evaluate_case_v4, normalize_cut, parse_pattern)


class TestEnumeration(unittest.TestCase):
    def test_single_input_two_patterns_is_complete(self):
        e = enumeration_status(1, ["1", "0"], [1, 2, 3, 4])
        self.assertTrue(e["complete"])
        self.assertEqual(e["expected"], 2)

    def test_two_input_two_patterns_is_incomplete(self):
        e = enumeration_status(2, ["11", "00"], [1, 2, 3, 4])
        self.assertFalse(e["complete"])
        self.assertEqual(sorted(e["missing"]), ["01", "10"])

    def test_duplicate_pattern(self):
        e = enumeration_status(2, ["00", "00", "01", "10", "11"], list(range(1, 11)))
        self.assertFalse(e["complete"])
        self.assertEqual(e["duplicates"], 1)

    def test_qid_duplicate(self):
        e = enumeration_status(1, ["0", "1"], [1, 1, 3, 4])
        self.assertFalse(e["complete"])
        self.assertEqual(e["reason"], "qid_count_or_duplicate")

    def test_integer_pattern_rejected(self):
        with self.assertRaises(ValueError):
            parse_pattern(0, 2)


class TestEvaluate(unittest.TestCase):
    def test_incomplete_but_all_observed_forced_is_not_proved(self):
        st = {1: "proved", 2: "refuted", 3: "refuted", 4: "proved"}
        r = evaluate_case_v4(["a", "b"], ["11", "00"], [1, 2, 3, 4], st)
        self.assertEqual(r["functional_sufficiency"], "not_enumerated")
        self.assertEqual(r["n_forced"], 2)

    def test_complete_two_patterns_proved(self):
        st = {1: "proved", 2: "refuted", 3: "refuted", 4: "proved"}
        r = evaluate_case_v4(["a"], ["1", "0"], [1, 2, 3, 4], st)
        self.assertTrue(r["enum_complete"])
        self.assertEqual(r["functional_sufficiency"], "proved")
        self.assertEqual(r["influence_status"], "valid")
        self.assertEqual(r["influence_max"], 1.0)

    def test_premise_known_but_unfinished_not_upgraded(self):
        # 0: prove1 proved, prove0 timeout; 1: both proved (infeasible)
        st = {1: "proved", 2: "timeout", 3: "proved", 4: "proved"}
        r = evaluate_case_v4(["a"], ["1", "0"], [1, 2, 3, 4], st)
        self.assertEqual(r["functional_sufficiency"], "unknown")
        self.assertEqual(r["n_premise_feasible_known"], 0)
        self.assertEqual(r["n_one_sided"], 1)

    def test_refuted_plus_timeout_marks_premise_known(self):
        st = {1: "refuted", 2: "timeout", 3: "proved", 4: "proved"}
        r = evaluate_case_v4(["a"], ["1", "0"], [1, 2, 3, 4], st)
        self.assertEqual(r["n_premise_feasible_known"], 1)
        self.assertEqual(r["functional_sufficiency"], "unknown")
        self.assertEqual(r["n_forced"], 0)

    def test_complete_but_undecided_has_valid_influence(self):
        st = {1: "refuted", 2: "proved", 3: "refuted", 4: "refuted",
              5: "proved", 6: "refuted", 7: "proved", 8: "refuted"}
        r = evaluate_case_v4(["a", "b"], ["00", "01", "10", "11"],
                             list(range(1, 9)), st)
        self.assertTrue(r["enum_complete"])
        self.assertEqual(r["functional_sufficiency"], "not_proved")
        self.assertEqual(r["influence_status"], "valid")


class TestNormalize(unittest.TestCase):
    def test_alias_and_constant(self):
        netbits = {"a": (1,), "b": (1,), "c": (2,), "0": (), "t": (3,)}
        r = normalize_cut(["a", "b", "c", "0"], netbits, "t")
        self.assertTrue(r["ok"])
        self.assertEqual(r["k"], 2)
        self.assertEqual(r["constants"], ["0"])
        self.assertEqual([x["name"] for x in r["canonical"]], ["a", "c"])
        self.assertEqual(r["aliases"][0]["alias_of"], "a")

    def test_target_in_cut_dropped(self):
        netbits = {"a": (1,), "t": (1,)}
        r = normalize_cut(["a"], netbits, "t")
        self.assertEqual(r["k"], 0)
        self.assertFalse(r["ok"])
        self.assertTrue(r["target_in_cut"])

    def test_missing_net_rejected(self):
        r = normalize_cut(["nope"], {"a": (1,), "t": (2,)}, "t")
        self.assertFalse(r["ok"])
        self.assertEqual(r["invalid"][0]["reason"], "missing_net")


class TestRoundTrip(unittest.TestCase):
    def test_pattern_survives_csv(self):
        df = pd.DataFrame([{"pattern": "00"}, {"pattern": "01"}])
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        back = pd.read_csv(buf, dtype={"pattern": str})
        self.assertEqual(back.pattern.tolist(), ["00", "01"])
        self.assertEqual(parse_pattern(back.pattern.iloc[0], 2), (0, 0))
        self.assertEqual(parse_pattern(back.pattern.iloc[1], 2), (0, 1))

    def test_aggregate_masks_or_and_conflict(self):
        a = dict(cond_fact=1, suff_proved=0, influence_valid=1, determinism=1.0,
                 n_inputs=1, truth_table="0:feasible:0")
        b = dict(cond_fact=1, suff_proved=1, influence_valid=0, determinism=0.5,
                 n_inputs=2, truth_table="00:feasible:0;01:infeasible:na")
        r = aggregate_records([a, b])
        self.assertEqual((r["cond_fact"], r["suff_proved"], r["influence_valid"]),
                         (1, 1, 1))
        self.assertEqual(r["determinism"], 1.0)
        self.assertEqual(r["n_inputs"], 2)
        self.assertEqual(r["conflicts"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
