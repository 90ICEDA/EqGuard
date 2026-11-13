
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path
import sys
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

ld = ROOT / "_p0pilot/toy"
ld.mkdir(parents=True, exist_ok=True)
toy = ld / "toy.v"
toy.write_text(
    "module toy(input clk, input d, input se, input si, output q);\n"
    "  SDFFX1 r (.CLK(clk), .D(d), .Q(q), .SE(se), .SI(si));\n"
    "endmodule\n", encoding="utf-8")

variants = [
    ("seq2", "sat -seq 2 -set-init-zero -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 1 -timeout 5"),
    ("seq3", "sat -seq 3 -set-init-zero -set-at 0 clk 0 -set-at 1 clk 1 -set-at 2 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 2 se 0 -set-at 1 d 1 -prove q 1 -timeout 5"),
    ("seq2_noinit", "sat -seq 2 -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 1 -timeout 5"),
]
for name, q in variants:
    s = "\n".join([
        f'read_verilog "{P0.wsl(toy)}"', "hierarchy -top toy", "proc",
        f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast", q]) + "\n"
    out = P0.run_yosys(s, ld / f"toy_{name}.log")
    ok = ("SUCCESS" in out) or ("no model found" in out)
    print(f"[{name}] success={ok}")
    for ln in out.splitlines():
        if "SAT proof finished" in ln or "SAT solving finished" in ln:
            print("   ", ln.strip())
