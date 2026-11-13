"""Record what the existing transform maps do and do not cover (offline)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
ITEMS = [
    ("r7|s38417t100__ctlmatchb_d1_s42__ys_abc.v|g24734", "s38417t100", ["g24734"]),
    ("r7|s38417t100__injalpha_d1_s42__ys_id.v|U6927.Q", "s38417t100", ["U6927"]),
    ("r5|rs232t1000__injzeta_d1_s42__ys_abc.v|U58.Y", "rs232t1000", ["U58"]),
    ("r6|rs232t1000__injzeta_d1_s42__ys_abc.v|U12.Y", "rs232t1000", ["U12"]),
]


def main() -> int:
    rows = []
    for rid, host, keys in ITEMS:
        cands = sorted((ROOT / "generate_trans/mappings").glob(f"{host}*.JSON"))
        if not cands and host.startswith("s38417"):
            cands = sorted((ROOT / "generate_trans/mappings").glob("s38417t300*.JSON"))
        p = cands[0] if cands else None
        info = json.loads(p.read_text(encoding="utf-8")) if p else {}
        align = info.get("node_alignment", {})
        matched = sorted(k for k in align for want in keys
                         if k == want or k.startswith(want + "_"))
        rows.append(dict(
            relation_id=rid, host=host,
            map_file=str(p.relative_to(ROOT)) if p else "",
            map_sha256=hashlib.sha256(p.read_bytes()).hexdigest() if p else "",
            src_verilog=info.get("src_verilog", ""),
            dst_verilog=info.get("dst_verilog", ""),
            original_cell_keys=";".join(matched),
            temporary_net_covered=False,
            note=("node_alignment maps original cells only; it does not provide "
                  "temporary-net or physical-Q correspondence")))
    pd.DataFrame(rows).to_csv(T12 / "transform_map_audit.csv", index=False,
                              encoding="utf-8-sig")
    print(pd.DataFrame(rows).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())