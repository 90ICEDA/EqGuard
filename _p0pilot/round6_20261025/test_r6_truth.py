"""Regression checks for the corrected function classifier."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import sys
from pathlib import Path

R6 = Path(_eqguard_path('_p0pilot/round6_20261025'))
sys.path.insert(0, str(R6))
from r6_truth import classify  # noqa: E402


def case(tt, k, complete=True, status="timeout=0;error=0;no_result=0"):
    return classify(tt, k, complete, status)


def main() -> int:
    # partial same-value: must never become a constant
    tt = "00:feasible:0;01:feasible:0;10:feasible:undecided;11:feasible:undecided"
    assert case(tt, 2)["function_status"] == "partial_forced"
    assert case(tt, 2)["function_class"] == "partial_forced"
    # complete constant
    tt = "".join(f"{i:02b}:feasible:0;" for i in range(4)).rstrip(";")
    assert case(tt, 2)["function_class"] == "constant0"
    # restricted domain: all feasible forced but one pattern infeasible
    tt = "00:feasible:0;01:feasible:0;10:feasible:0;11:infeasible:undecided"
    c = case(tt, 2)
    assert c["function_status"] == "domain_restricted_function"
    assert c["function_class"] == "domain_restricted_constant0"
    assert c["domain_restricted"] == 1
    # no feasible pattern
    tt = "00:infeasible:undecided;01:infeasible:undecided;" \
         "10:infeasible:undecided;11:infeasible:undecided"
    assert case(tt, 2)["function_status"] == "infeasible"
    # unfinished query
    assert case(tt, 2, status="timeout=1")["function_status"] == "unknown"
    # incomplete enumeration
    assert case(tt, 2, complete=False)["function_status"] == "not_enumerated"
    # complete other function
    tt = "00:feasible:0;01:feasible:1;10:feasible:1;11:feasible:1"
    assert case(tt, 2)["function_class"] == "or"
    print("r6 truth regression: 7/7 OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())