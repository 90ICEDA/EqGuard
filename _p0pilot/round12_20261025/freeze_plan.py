"""Freeze up to four blocking samples with local candidate mappings (no SAT)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"
AUDIT = T12 / "blocker_audit.json"

SELECT = [
    dict(relation_id="r7|s38417t100__ctlmatchb_d1_s42__ys_abc.v|g24734",
         role="val", source_view="s38417t100__ctlmatchb_d1_s42__ys_abc",
         partner="s38417t100__ctlmatchb_d1_s42__ys_aig",
         source_nets=["_00375_", "U6460.ISO", "DFF_146_n1", "U6460.D", "g24734"],
         preferred=["_00375_", "U6460.ISO", "DFF_146_n1", "U6460.D", "g24734"],
         alternatives=[["_00375_", "n__00375___g829"], ["U6460.ISO", "_09306_"],
                       ["DFF_146_n1", "_10740_"], ["U6460.D", "_09305_"],
                       ["g24734", "g24734__g24741"]],
         reason="legacy slot2 _10740_ is INVX0; same DFF_146_Q_reg output is DFF_146_n1"),
    dict(relation_id="r7|s38417t100__injalpha_d1_s42__ys_id.v|U6927.Q",
         role="val", source_view="s38417t100__injalpha_d1_s42__ys_id",
         partner="s38417t100__injalpha_d1_s42__ys_opt",
         source_nets=["U6300.IN6", "U4234.IN3", "_01360_", "U4305.QN", "U6927.Q"],
         preferred=["U6927.IN1", "U4234.IN3", "_01360_", "U4305.QN", "U6927.Q"],
         alternatives=[["U6927.IN1", "U6299.IN2"], ["U4234.IN3", "U4366.IN"],
                       ["_01360_", "n__01360___g5261"], ["U4305.QN", "U5049.IN2"],
                       ["U6927.Q", "g27264"]],
         reason="legacy slot0 U6299.IN2 is DFF_1304; same DFF_953 output is U6927.IN1"),
    dict(relation_id="r5|rs232t1000__injzeta_d1_s42__ys_abc.v|U58.Y",
         role="train", source_view="rs232t1000__injzeta_d1_s42__ys_abc",
         partner="rs232t1000__injzeta_d1_s42__ys_nand",
         source_nets=["U222.A", "_085_", "_086_", "_077_", "U58.Y"],
         preferred=["U222.A", "n__085___g576", "_086_", "n__077___g554", "U58.Y"],
         alternatives=[["U222.A", "U59.A1"], ["n__085___g576", "_085_"],
                       ["_086_", "_172_"], ["n__077___g554", "_077_"],
                       ["U58.Y", "n214"]],
         reason="two legacy candidates have type mismatch; local same-cell-base outputs used"),
    dict(relation_id="r6|rs232t1000__injzeta_d1_s42__ys_abc.v|U12.Y",
         role="train", source_view="rs232t1000__injzeta_d1_s42__ys_abc",
         partner="rs232t1000__injzeta_d1_s42__ys_nand",
         source_nets=["U228.A", "_043_", "U106.A0", "_041_", "U12.Y"],
         preferred=["U228.A", "_043_", "U106.A0", "_041_", "U12.Y"],
         alternatives=[["U228.A", "_187_"], ["_043_", "n__043___g449"],
                       ["U106.A0", "TrojanFP4.B"], ["_041_", "_041_"],
                       ["U12.Y", "n109"]],
         reason="two legacy candidates are INVX0; same DFF/same-name candidates used"),
]


def main() -> int:
    audit = {x["relation_id"]: x for x in json.loads(AUDIT.read_text(encoding="utf-8"))}
    chosen = []
    for s in SELECT:
        a = audit[s["relation_id"]]
        assert a["role"] == s["role"] and a["partner"] == s["partner"]
        slots = []
        for j, (src, pref, alts) in enumerate(zip(s["source_nets"], s["preferred"],
                                                   s["alternatives"])):
            names = [pref] + [x for x in alts if x != pref]
            names = names[:2]
            slots.append(dict(slot=j, source=src, preferred=pref, alternatives=names))
        chosen.append(dict(**{k: s[k] for k in
                              ("relation_id", "role", "source_view", "partner",
                               "source_nets", "reason")},
                           slots=slots,
                           audit_category=a["category"],
                           audit_failed_slot=a["failed_slot"]))
    plan = dict(
        created=datetime.now().astimezone().isoformat(timespec="seconds"),
        context_id="70e2dd53372b9913ceb53c29420a85d23b8a8ec8ea39cb2ec96807a55532e1da",
        context="native_unrestricted_combinational_physical_Q_v1",
        selection=("2 val + 2 train from the 29 blockers; val first; only the fixed "
                   "partner and its raw snapshot/local same-cell-base candidates; "
                   "no labels, test views or new targets"),
        selected=chosen,
        budget=dict(correspondence_max=48, tables_max=128, review_max=16,
                    total_max=192, timeout_s=5, wall_s=1800),
        training_runs=0, training_loader_compatible=False,
        no_label_transfer=True, old_P1_is_locator_only=True,
        full_circuit_equivalence_not_inferred=True,
    )
    blob = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    plan["plan_sha256"] = hashlib.sha256(blob.encode()).hexdigest()
    (T12 / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    print(json.dumps(dict(created=plan["created"], sha=plan["plan_sha256"],
                          selected=[x["relation_id"] for x in chosen]),
                     ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())