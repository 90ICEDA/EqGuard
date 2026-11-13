
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
from pathlib import Path
import pandas as pd

ROOT = Path(_eqguard_path(''))
OLD = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1"
q = pd.read_csv(OLD / "log_qualification.csv", encoding="utf-8-sig")
bad = set(q[~q.accepted.astype(bool)].log)
ag = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv", encoding="utf-8-sig").fillna("")
ag = ag[ag.kind.isin(["cone", "dff_next"])]
ag["bad"] = ag.log.isin(bad)
for col in ["sat_q1", "sat_q2", "sat_q3", "sat_q4", "status"]:
    print(col)
    print(pd.crosstab(ag.bad, ag[col]).to_string())
print("\nrows in bad logs:", int(ag.bad.sum()), "rows in good:", int((~ag.bad).sum()))
print("complex rows in bad logs with any definite:",
      int((ag.bad & ag[["sat_q1", "sat_q2", "sat_q3", "sat_q4"]].isin(["proved", "refuted"]).any(axis=1)).sum()))
print("\nstatus of the 186-pass partial log:")
print(ag[ag.log.str.contains("rs232t1000__ctlxor_d1_s42__ys_opt")][["kind", "status", "sat_q1", "sat_q2", "sat_q3", "sat_q4"]].to_string())
