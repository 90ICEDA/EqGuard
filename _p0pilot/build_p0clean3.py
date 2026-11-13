"""build_p0clean3.py -- 10-dim SAT feature: functional core + is_S/is_P + covered.

Drop: is_cell/is_cut/is_target_only (identity-ish), p1_proved_log (corr .957).
Keep: n_rel_log, frac_decided/influence/proved, reach_po/dff, p1_ratio.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np

PT = Path(_eqguard_path('generate_trans/folds/hosts_bt31/data/processed'))
SRC = PT / "satrel_node_feats_sat_p0clean2.npy"
MSK = PT / "satrel_node_mask_sat_p0clean2.npy"
OUT = PT / "satrel_node_feats_sat_p0clean3.npy"
OUT_SW = PT / "satrel_node_feats_sat_p0clean3_sw.npy"
META = PT / "satrel_node_feats_sat_p0clean3_meta.json"

IDX = [3, 4, 5, 6, 7, 8, 10]          # n_rel_log, frac_decided, frac_influence,
# frac_proved, reach_po_log, reach_dff_log, p1_ratio
NAMES = ["n_rel_log", "frac_decided", "frac_influence", "frac_proved",
         "reach_po_log", "reach_dff_log", "p1_ratio", "is_S", "is_P", "covered"]


def main() -> int:
    x = np.load(SRC)
    m = np.load(MSK).astype(np.float32)
    assert x.shape[1] == 12 and m.shape[1] >= 2, (x.shape, m.shape)
    core = x[:, IDX].astype(np.float32)
    is_s = (m[:, 0] > 0).astype(np.float32)[:, None]
    is_p = (m[:, 1] > 0).astype(np.float32)[:, None]
    cov = x[:, -1].astype(np.float32)[:, None]
    out = np.concatenate([core, is_s, is_p, cov], axis=1).astype(np.float32)
    np.save(OUT, out)
    # S-weighted variant: 2x functional columns on S rows (S/P/covered flags unchanged)
    sw = out.copy()
    sw[m[:, 0] > 0, :7] *= 2.0
    np.save(OUT_SW, sw)
    meta = dict(source=str(SRC), mask=str(MSK), shape=list(out.shape), names=NAMES,
                n_s=int(is_s.sum()), n_p=int(is_p.sum()), covered=float(cov.mean()),
                note="10-dim: functional core + is_S/is_P + covered; S-weighted variant = 2x S rows on first 7 cols")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[out] {OUT} {out.shape}; S={int(is_s.sum())} P={int(is_p.sum())} cover={cov.mean():.4f}")
    print(f"[out] {OUT_SW} {sw.shape}")
    print(f"[out] {META}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
