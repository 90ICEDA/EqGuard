"""Probe yosys `sat -show` witness format on one existing candidate."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import sys
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

WORK = ROOT / "generate_trans/folds/hosts_bt31"
OUT = ROOT / "_p0pilot/round3_20261025/probe"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    v = WORK / "trans/rs232t1000__ctlmatcha_d1_s42__ys_abc.v"
    top = P0.module_name(v)
    cut = ["U106.A0", "U111.B", "U25.A0"]
    target = "U16.Y"
    lines = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten",
             "proc -noopt", f"select -module {top}"]
    refs = {}
    for i, nm in enumerate(cut):
        refs[nm] = f"fb_{i}"
        lines.append(f"rename {P0.sat_ref(nm)} {refs[nm]}")
    lines.append(f"rename {P0.sat_ref(target)} fb_t")
    lines.append("setattr -set keep 1 " + " ".join(
        f"w:{x}" for x in list(refs.values()) + ["fb_t"]))
    lines += ["techmap -autoproc -map phase2/ys/sat_cells_map.v", "opt -fast"]
    sets = " ".join(f"-set {refs[n]} 1" for n in cut)
    shows = " ".join(f"-show {n}" for n in refs.values()) + " -show fb_t"
    lines += ["log QRY00001",
              f"sat -seq 1 {sets} -prove fb_t 1 -timeout 3 {shows} -dump_json {P0.wsl(OUT/'q1.json')}"]
    lines += ["log QRY00002",
              f"sat -seq 1 {sets} -prove fb_t 0 -timeout 3 {shows}"]
    script = "\n".join(lines) + "\n"
    out = P0.run_yosys(script, OUT / "probe.sat.log")
    tail = out.splitlines()
    idx = max(i for i, l in enumerate(tail) if l.startswith("QRY"))
    print("\n".join(tail[max(0, idx - 5):idx + 40]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
