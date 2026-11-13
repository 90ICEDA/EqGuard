"""Load-check the round-5 candidate feature array with train_test2.3 semantics."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
R5 = ROOT / "_p0pilot/round5_20261025"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"


def main() -> int:
    C = np.load(R5 / "features/r5_extra_real.npy")
    x = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True).x
    assert C.shape[0] == x.shape[0]
    assert np.isfinite(C).all()
    assert C.min() >= 0.0 and C.max() <= 1.0
    assert set(np.unique(C[:, -1]).tolist()) <= {0.0, 1.0}
    mask_any = C[:, -1] > 0
    norm_n = C.shape[1] - 1
    cat = torch.cat([x.cpu(), torch.from_numpy(C).float()], 1)
    info = dict(extra_shape=list(C.shape), base_shape=list(x.shape),
                cat_shape=list(cat.shape), mask_any=int(mask_any.sum()),
                extra_norm_n=int(norm_n), min=float(C.min()), max=float(C.max()),
                last_column_unique=sorted(set(np.unique(C[:, -1]).tolist())),
                bounded_ok=True, ordinal_signature_present=False)
    (TAB5 / "r5_feature_load_check.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
