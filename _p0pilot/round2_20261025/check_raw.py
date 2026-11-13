
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
from pathlib import Path
import pandas as pd

ROOT = Path(_eqguard_path(''))
d = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv", encoding="utf-8-sig")
d = d[d.kind.isin(["cone", "dff_next"])]
rows = []
for host, g in d.groupby(d.design.str.split("__").str[0]):
    for design in g.design.unique():
        stem = Path(design).stem
        raw = ROOT / "_p0pilot/full_logs" / host / (stem + ".struct_raw.json")
        rows.append((host, design, raw.exists(), raw.stat().st_size if raw.exists() else 0))
out = pd.DataFrame(rows, columns=["host", "design", "raw", "bytes"])
print(out.groupby("host").agg(n=("design", "size"), raw=("raw", "sum")).to_string())
print(out[~out.raw].head(20).to_string(index=False))
print("total designs", len(out), "raw", int(out.raw.sum()))
