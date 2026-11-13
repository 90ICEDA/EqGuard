# -*- coding: utf-8 -*-
"""_probe_a1f.py —— 对照「图节点数」与「网表实例数/网数」，确认 A1 口径。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from phase2 import netlist_lib as NL  # noqa: E402

LIB = Path("C:/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali/verilog_lib.v")
OUT = Path("10.15/01_数据与标签/A1_变换统计/_probe_a1f.txt")
L = []
lib = NL.load_library(LIB)
files = [
    "hosts_bt2/rs232t1000/base/rs232t1000_clean.v",
    "hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v",
    "hosts_bt2/rs232t1000/rw/rs232t1000__injalpha_d1_s42__rwdecomp3_d1_s42.v",
    "hosts_bt2/rs232t1000/rw/rs232t1000__injalpha_d1_s42__rwbubble_d1_s42.v",
    "hosts_bt2/rs232t1000/rw/rs232t1000__injalpha_d1_s42__ys_rt.v",
    "hosts_bt2/rs232t1000/rw/rs232t1000__injalpha_d1_s42__ys_abc.v",
    "hosts_bt2/rs232t1000/rw/rs232t1000__injalpha_d1_s42__ys_aig.v",
]
L.append(f"{'netlist':<62}{'insts':>8}{'nets':>8}{'assigns':>9}{'lines':>8}")
for f in files:
    p = ROOT / "generate_trans" / f
    if not p.exists():
        L.append(f"{f:<62}  <缺>")
        continue
    nl = NL.parse_netlist(p, lib)
    nets = len({n for i in nl.insts for _p, n in nl.outs(i)})
    L.append(f"{f.split('/')[-1]:<62}{len(nl.insts):>8}{nets:>8}{len(nl.assigns):>9}"
             f"{len(p.read_text(encoding='utf-8', errors='ignore').splitlines()):>8}")

ni = json.loads((ROOT / "generate_trans/folds/hosts_beta2/phase2_name_index.json")
                .read_text(encoding="utf-8"))
L.append("")
L.append("名字索引条目数（= 图节点数）：")
for v in ("rs232t1000__injalpha_d1_s42",
          "rs232t1000__injalpha_d1_s42__rwdecomp3_d1_s42",
          "rs232t1000__injalpha_d1_s42__rwbubble_d1_s42",
          "rs232t1000__injalpha_d1_s42__ys_rt",
          "rs232t1000__injalpha_d1_s42__ys_abc",
          "rs232t1000__injalpha_d1_s42__ys_aig"):
    side = "orig" if v.endswith("_d1_s42") and "__rw" not in v else "trans"
    n = len(ni.get(side, {}).get(v, {}))
    L.append(f"  [{side}] {v:<60} {n}")
OUT.write_text("\n".join(L), encoding="utf-8")
print("done")
