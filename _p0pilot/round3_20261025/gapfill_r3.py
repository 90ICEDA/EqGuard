"""Gap-fill and target-count details for the round-3 report."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
R3 = ROOT / "_p0pilot/round3_20261025"
sys.path.insert(0, str(R3))
from r3_nets import build_index, load_module  # noqa: E402


def main() -> int:
    rel = pd.concat([pd.read_csv(TAB / "r3_recovery_relations.csv", encoding="utf-8-sig"),
                     pd.read_csv(TAB / "r3_graded_relations.csv", encoding="utf-8-sig")],
                    ignore_index=True)
    nodes = pd.concat([pd.read_csv(TAB / "r3_recovery_nodes.csv", encoding="utf-8-sig"),
                       pd.read_csv(TAB / "r3_graded_nodes.csv", encoding="utf-8-sig")],
                      ignore_index=True)
    rel2 = rel[["relation_id", "role", "host", "recipe", "kind", "target_id"]].rename(
        columns={"role": "rel_role"})
    m = nodes.merge(rel2, on="relation_id", how="left")
    print(m.groupby(["rel_role", "host", "recipe"]).agg(
        relations=("relation_id", "nunique"), nodes=("node_index", "nunique"),
        views=("view", "nunique")).to_string(), flush=True)
    print("\nunique target_id", rel.target_id.nunique(), "relations", len(rel),
          "unique target+driver", len(rel[["target_id", "driver"]].drop_duplicates()),
          flush=True)
    # PO pool reason for s38417
    for design in ("s38417t100__ctlmatcha_d1_s42__ys_aig",
                   "s38417t100__injzeta_d1_s42__ys_aig"):
        raw = R3 / "struct_raw" / f"{design}.json"
        mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
        mod = next(iter(mods.values()))
        idx = build_index(mod)
        pos = [p for p, v in idx["ports"].items() if v.get("direction") == "output"]
        single = [p for p in pos if len([b for b in idx["ports"][p]["bits"]
                                         if isinstance(b, int)]) == 1]
        dffdrv = [p for p in single if all(
            c in idx["dff_cells"] for c in idx["bit_driver"].get(
                idx["ports"][p]["bits"][0], set()))]
        comb = [p for p in single if p not in dffdrv]
        print(f"\n{design}: ports={len(pos)} single_bit={len(single)} "
              f"dff_driven={len(dffdrv)} combinational={len(comb)}", flush=True)
    # attempted fill for cut rejections
    a = pd.read_csv(TAB / "r3_graded_attempts.csv", encoding="utf-8-sig")
    mask = a.attempted.isna() & ~a.reason.isin(["budget_exhausted", "scan_cap",
                                                "query_cap", "skipped_wall_cap"])
    a.loc[mask, "attempted"] = True
    a["accepted"] = a.accepted.fillna(False)
    a.to_csv(TAB / "r3_graded_attempts.csv", index=False, encoding="utf-8-sig")
    print("\nfilled attempted rows:", int(mask.sum()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
