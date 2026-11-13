
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path
import sys
import time
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

host, inst, recipe = "s38584t100", "injalpha", "ys_abc"
vs = P0.find_designs("hosts_bt31", host, inst, [recipe])
print("[designs]", [v.name for v in vs])
v = vs[0]
top = P0.module_name(v)
logdir = ROOT / "_p0pilot/bench_logs"
logdir.mkdir(parents=True, exist_ok=True)
js = logdir / f"{top}.json"
s0 = "\n".join([f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
                f'write_json "{P0.wsl(js)}"',
                f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]) + "\n"
t0 = time.time()
P0.run_yosys(s0, logdir / f"{top}.struct.log")
print("[struct] %.1fs" % (time.time() - t0))
g = P0.load_graph(js, top)
cases = P0.pick_case(g) or P0.pick_case_cone(g)
print("[cases] total=%d" % len(cases))
cases = cases[:3]
t0 = time.time()
out = P0.run_yosys(P0.build_script(v, top, cases, js, 15, [16, 64], 15),
                   logdir / f"{top}.sat.log")
dt = time.time() - t0
print("[sat] cases=%d elapsed=%.1fs per_case=%.1fs" % (len(cases), dt, dt / max(len(cases), 1)))
print("[res]", P0.parse_results(out))
