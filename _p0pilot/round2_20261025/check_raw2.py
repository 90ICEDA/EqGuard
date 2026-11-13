
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
from pathlib import Path
import pandas as pd

ROOT = Path(_eqguard_path(''))
q = pd.read_csv(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1/log_qualification.csv", encoding="utf-8-sig")
print(q[q.log.str.contains("rs232t1000__ctldup_d1_s42__ys_abc")].to_string())
print(q[q.log.str.contains("rs232t1000__ctldup")][["log", "accepted", "reason", "queries", "complex_rows", "qualified_rows"]].to_string(index=False))
p = ROOT / "_p0pilot/full_logs/rs232t1000"
names = sorted(x.name for x in p.glob("*ctldup*"))
print(len(names))
for n in names[:30]:
    print(n)
