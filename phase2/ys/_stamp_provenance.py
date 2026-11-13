# -*- coding: utf-8 -*-
"""_stamp_provenance.py —— 冒烟：**在 yosys 生成阶段就把节点绑定做掉**。

思路（不改动现有数据链，只在旁边试）：
  1) 源网表纯文本改写：每个 `wire` 声明加 `(* keep *)`，每个单元实例加 `(* src_id="<实例名>" *)`；
  2) 用 yosys 跑指定配方，`write_verilog` **不加 -noattr**（属性才会写进输出）；
  3) 量三件事：带 `src_id` 的单元占比、`keep` 住的网名存活率、以及 CEC 是否仍等价。

用法：
    py phase2/ys/_stamp_provenance.py --views rs232t1000__injalpha_d1_s42,rs232t1000__ctlmatcha_d1_s42 \
        --recipes rt,abc,aig
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

WSL_ROOT = _eqguard_path('', wsl=True)
VALI = "/mnt/c/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali"
RECIPES = {
    "rt": "flatten",
    "abc": "flatten\ntechmap\nopt -full\nabc -g AND,OR,XOR,XNOR,MUX",
    "aig": "flatten\ntechmap\nopt -full\naigmap",
}
NO_OPT = {"rt"}
SKIP = re.compile(r"^\s*(module|endmodule|input|output|inout|assign|wire|reg|parameter)\b")
WIRE = re.compile(r"^(\s*)wire\s+([^;]+);")
INST = re.compile(r"^(\s*)([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(")


def stamp(text: str) -> str:
    """给实例打 `src_id`；网不在这里 keep，改由 yosys 的 `setattr -set keep 1 w:*` 批量做
    （多行/逗号分隔的 wire 声明纯文本处理不可靠，实测只 keep 住 2 行）。"""
    out = []
    for ln in text.splitlines():
        m = INST.match(ln)
        if m and not SKIP.match(ln) and not ln.strip().startswith("(*"):
            # 关键：只替换前缀，**保留行尾原来的端口连接**（上次把 `U3(...);` 的括号内容吃掉了）
            out.append(f'{m.group(1)}(* src_id="{m.group(3)}" *) ' + ln[m.start(2):])
            continue
        out.append(ln)
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt2")
    ap.add_argument("--host", type=str, default="rs232t1000")
    ap.add_argument("--views", type=str, required=True)
    ap.add_argument("--recipes", type=str, default="rt,abc,aig")
    ap.add_argument("--out", type=Path, default=ROOT / "generate_trans" / "stamp")
    a = ap.parse_args()

    views = [v.strip() for v in a.views.split(",") if v.strip()]
    recipes = [r.strip() for r in a.recipes.split(",") if r.strip()]
    for d in ("src", "out", "logs"):
        (a.out / d).mkdir(parents=True, exist_ok=True)

    jobs = []
    for v in views:
        src = a.hosts_root / a.host / f"{v}.v"
        if not src.exists():
            print(f"[WARN] 缺 {src}")
            continue
        st = a.out / "src" / f"{v}.v"
        st.write_text(stamp(src.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        n_inst = len([1 for ln in st.read_text(encoding="utf-8").splitlines() if "src_id=" in ln])
        n_keep = len([1 for ln in st.read_text(encoding="utf-8").splitlines() if "(* keep *) wire" in ln])
        print(f"[stamp] {v}: 打标实例 {n_inst} 个、keep 网 {n_keep} 行")
        for r in recipes:
            body = [f"read_verilog -sv {VALI}/verilog_lib.v",
                    f"read_verilog -sv {WSL_ROOT}/generate_trans/stamp/src/{v}.v",
                    f"hierarchy -top {v}", "proc",
                    "setattr -set keep 1 w:*"]      # 全网 keep：让名字在各配方后都活下来
            body += RECIPES[r].split("\n")
            if r not in NO_OPT:
                body += ["opt -full", "opt_clean"]
            body += [f"rename -top {v}__ys_{r}",
                     f"write_verilog {WSL_ROOT}/generate_trans/stamp/out/{v}__ys_{r}.v"]
            ys = a.out / "logs" / f"{v}__ys_{r}.ys"
            ys.write_text("\n".join(body) + "\n", encoding="utf-8")
            jobs.append((v, r, ys))

    sh = ["#!/bin/bash", "set +e", f"cd {WSL_ROOT}"]
    for _v, _r, ys in jobs:
        sh.append(f"yosys -q -s {WSL_ROOT}/generate_trans/stamp/logs/{ys.name} "
                  f"-l {WSL_ROOT}/generate_trans/stamp/logs/{ys.stem}.log")
    cur = a.out / "_gen.sh"
    cur.write_text("\n".join(sh) + "\n", encoding="utf-8", newline="\n")
    print(f"[run] yosys 作业 {len(jobs)} 个")
    rc = subprocess.call(["wsl", "bash", f"{WSL_ROOT}/generate_trans/stamp/_gen.sh"])
    print(f"[run] rc={rc}")

    print(f"\n{'变体':<36}{'单元':>6}{'带src_id':>10}{'保留原名网':>11}")
    for v, r, _ys in jobs:
        f = a.out / "out" / f"{v}__ys_{r}.v"
        if not f.exists():
            print(f"{v}__ys_{r:<10} 生成失败")
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        cells = [ln for ln in txt.splitlines() if INST.match(ln) and not SKIP.match(ln)]
        tagged = [ln for ln in cells if "src_id=" in ln]
        kept = re.findall(r"^\s*\)\s*;\s*$", txt, re.M)
        names = set(re.findall(r'wire\s+([^\s;]+)\s*;', txt))
        print(f"{v.split('__')[1][:14] + '__ys_' + r:<36}{len(cells):>6}"
              f"{100.0*len(tagged)/max(1,len(cells)):>9.1f}%{len(names):>11}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
