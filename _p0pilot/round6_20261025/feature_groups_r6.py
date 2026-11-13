"""Per-group permutation impact: output determinism vs feasibility vs influence."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
R6 = ROOT / "_p0pilot/round6_20261025"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"

GROUPS = dict(determinism=[3, 11, 12, 13, 14, 15, 16, 17, 18],
              feasibility=[1, 2, 4, 5, 19, 20, 21, 22],
              influence=[6, 7, 8, 10],
              structure=[0, 9, 23, 24])


def main() -> int:
    real = np.load(R6 / "features/r6_extra_real.npy", mmap_mode="r")
    perm = np.load(R6 / "features/r6_extra_permuted.npy", mmap_mode="r")
    support = np.where(np.asarray(real[:, -1]) > 0)[0]
    role = {}
    for p in (TAB5 / "r5_nodes.csv", TAB6 / "r6_nodes.csv"):
        d = pd.read_csv(p, encoding="utf-8-sig")
        role.update({int(n): str(r) for n, r in zip(d.node_index, d.role)})
    rows = []
    for r in ("train", "val"):
        ids = np.array([i for i in support if role.get(int(i)) == r], dtype=np.int64)
        for name, cols in GROUPS.items():
            diff = np.asarray(real[ids][:, cols]) != np.asarray(perm[ids][:, cols])
            rows.append(dict(role=r, group=name, support=len(ids),
                             changed_nodes=int(np.any(diff, axis=1).sum()),
                             changed_columns=int(np.any(diff, axis=0).sum()),
                             columns=len(cols)))
    out = pd.DataFrame(rows)
    out.to_csv(TAB6 / "r6_feature_diff_groups.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())