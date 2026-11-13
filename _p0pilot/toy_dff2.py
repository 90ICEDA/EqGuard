
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

ld = ROOT / "_p0pilot/toy"
toy = ld / "toy.v"
toy.write_text(
    "module toy(input clk, input d, input se, input si, output q);\n"
    "  SDFFX1 r (.CLK(clk), .D(d), .Q(q), .SE(se), .SI(si));\n"
    "endmodule\n", encoding="utf-8")
js = ld / "toy_post.json"
base = "\n".join([
    f'read_verilog "{P0.wsl(toy)}"', "hierarchy -top toy", "proc",
    f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]) + "\n"
P0.run_yosys(base + f'write_json "{P0.wsl(js)}"\n', ld / "toy_post.log")
d = json.loads(js.read_text(encoding="utf-8"))
mod = d["modules"][list(d["modules"])[0]]
print("[cells]", mod["cells"])

variants = [
    ("seq2_q1", "sat -seq 2 -set-init-zero -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 1 -timeout 5"),
    ("seq2_q0", "sat -seq 2 -set-init-zero -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 0 -timeout 5"),
    ("seq2_si_q1", "sat -seq 2 -set-init-zero -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 si 0 -set-at 1 si 0 -set-at 0 d 1 -prove q 1 -timeout 5"),
    ("seq2_clk10_q1", "sat -seq 2 -set-init-zero -set-at 0 clk 1 -set-at 1 clk 0 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 1 -timeout 5"),
    ("seq3_q1", "sat -seq 3 -set-init-zero -set-at 0 clk 0 -set-at 1 clk 1 -set-at 2 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 2 se 0 -set-at 0 d 1 -set-at 1 d 1 -set-at 2 d 1 -prove q 1 -timeout 5"),
    ("seq2_qinit0_d1_q1", "sat -seq 2 -set-at 0 q 0 -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 1 -timeout 5"),
    ("seq2_qinit0_d1_q0", "sat -seq 2 -set-at 0 q 0 -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 0 -timeout 5"),
    ("seq2_qinit0_d0_q0", "sat -seq 2 -set-at 0 q 0 -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 0 -prove q 0 -timeout 5"),
    ("seq2_qinit1_d1_q1", "sat -seq 2 -set-at 0 q 1 -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 1 -timeout 5"),
    ("seq2_qinit1_d1_q0", "sat -seq 2 -set-at 0 q 1 -set-at 0 clk 0 -set-at 1 clk 1 -set-at 0 se 0 -set-at 1 se 0 -set-at 0 d 1 -prove q 0 -timeout 5"),
]
for name, q in variants:
    out = P0.run_yosys(base + q + "\n", ld / f"toy2_{name}.log")
    ok = ("SUCCESS" in out) or ("no model found" in out)
    print(f"[{name}] success={ok}")
