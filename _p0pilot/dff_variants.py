
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path
import re
import sys
import time
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

host, inst, recipe = "s38584t100", "injalpha", "ys_abc"
v = P0.find_designs("hosts_bt31", host, inst, [recipe])[0]
top = P0.module_name(v)
logdir = ROOT / "_p0pilot/dff_logs"
logdir.mkdir(parents=True, exist_ok=True)
js = logdir / f"{top}.json"
s0 = "\n".join([f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
                f'write_json "{P0.wsl(js)}"',
                f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]) + "\n"
P0.run_yosys(s0, logdir / f"{top}.struct.log")
g = P0.load_graph(js, top)
drv, _ = P0._graph_maps(g)
out_bits = {b: p for p, info in g["ports"].items()
            if info.get("direction") == "output"
            for b in info.get("bits", []) if isinstance(b, int)}
po = dn = clk = se = None
for b, pname in out_bits.items():
    c = drv.get(b)
    if not c:
        continue
    cell = g["cells"][c]
    if "DFF" not in str(cell.get("type", "")).upper():
        continue
    conns = {p: [P0.net_name(g, x) for x in bs] for p, bs in cell.get("connections", {}).items()}
    dn = (conns.get("D") or [None])[0]
    clk = (conns.get("CLK") or conns.get("CK") or [None])[0]
    se = (conns.get("SE") or [None])[0]
    po = pname
    break
print("[case] po=%s D=%s CLK=%s SE=%s type=%s" % (po, dn, clk, se, g["cells"][drv[next(iter([b for b,p in out_bits.items() if p==po]))]]["type"]))
assert po and dn and clk
simple = lambda s: bool(s and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", s))
base = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
        f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]
se_set = ""
if simple(se):
    se_set = " ".join(f"-set-at {i} {se} 0" for i in range(3))
si = None
for p in ("SI",):
    ns = None
    # SI name is not stored above; leave SI unconstrained only if SE=0 for all steps
dref = "\\U8966.Q"
init = "-set-init-zero"
variants = [
    ("seq2_clk01_D0", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 0 {dref} 1 -prove {po} 1 -timeout 5"),
    ("seq2_clk01_D1", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 1 {dref} 1 -prove {po} 1 -timeout 5"),
    ("seq3_clk01_D1", f"sat -seq 3 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 -set-at 2 {clk} 1 {se_set} -set-at 1 {dref} 1 -prove {po} 1 -timeout 5"),
    ("seq3_clk10_D1", f"sat -seq 3 {init} -set-at 0 {clk} 1 -set-at 1 {clk} 0 -set-at 2 {clk} 0 {se_set} -set-at 1 {dref} 1 -prove {po} 1 -timeout 5"),
    ("seq3_clk01_D01", f"sat -seq 3 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 -set-at 2 {clk} 1 {se_set} -set-at 0 {dref} 1 -set-at 1 {dref} 1 -prove {po} 1 -timeout 5"),
    ("seq2_noclk_D0", f"sat -seq 2 {init} {se_set} -set-at 0 {dref} 1 -prove {po} 1 -timeout 5"),
    ("seq2_muxA1_D1", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 0 g4239 1 -set-at 0 _00860_ 0 -set-at 0 g35 0 -prove {po} 1 -timeout 5"),
    ("seq2_muxA0_D0", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 0 g4239 0 -set-at 0 _00860_ 1 -set-at 0 g35 0 -prove {po} 0 -timeout 5"),
    ("seq2_orA1_D1", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 0 _00364_ 1 -set-at 0 _00375_ 0 -prove {po} 1 -timeout 5"),
    ("seq2_orA0_D0", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 0 _00364_ 0 -set-at 0 _00375_ 0 -prove {po} 0 -timeout 5"),
    ("seq2_scanA1_D1", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 0 \\U8710.Q 1 -prove {po} 1 -timeout 5"),
    ("seq2_scanA0_D0", f"sat -seq 2 {init} -set-at 0 {clk} 0 -set-at 1 {clk} 1 {se_set} -set-at 0 \\U8710.Q 0 -prove {po} 0 -timeout 5"),
]
for name, q in variants:
    t0 = time.time()
    out = P0.run_yosys("\n".join(base + [q]) + "\n", logdir / f"dff_{name}.log")
    ok = ("SUCCESS" in out) or ("no model found" in out)
    print(f"[{name}] {time.time()-t0:.1f}s success={ok}")
    for ln in out.splitlines():
        if "SAT proof finished" in ln or "SAT solving finished" in ln:
            print("   ", ln.strip())
