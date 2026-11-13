
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path
import json
import sys
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

v = ROOT / "generate_trans/folds/hosts_bt31/trans/s38584t100__injalpha_d1_s42__ys_abc.v"
top = P0.module_name(v)
ld = ROOT / "_p0pilot/dff_logs"
js = ld / "post.json"
s = "\n".join([f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
               f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast",
               f'write_json "{P0.wsl(js)}"']) + "\n"
P0.run_yosys(s, ld / "post.log")
d = json.loads(js.read_text(encoding="utf-8"))
mod = d["modules"][list(d["modules"])[0]]
print("[cells]", len(mod["cells"]))
for cn, c in mod["cells"].items():
    t = c.get("type", "")
    if t.startswith("$dff") or t.startswith("$adff") or t.startswith("$sdff") or "DFF" in t.upper():
        print(" ", cn, t, c.get("connections"))
print("[netnames bit4]", mod.get("netnames", {}).get("g10122"))
