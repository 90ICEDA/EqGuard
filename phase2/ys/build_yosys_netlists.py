# -*- coding: utf-8 -*-
"""
build_yosys_netlists.py —— 用 **yosys（真实综合工具）** 从原网表生成一批
「结构不同但功能等价」的新网表，并逐个做 CEC（state-boundary）验证。

为什么不用我们自己的 decomp3/bubble 算子：
  那两个算子只在"我们实现的那几种改写"上采样；这里改用 yosys 的通用综合变换
  （techmap / opt / abc / aigmap），**不依赖我们的算子**，覆盖面更广、更中立。

配方（都先 `flatten` 成单模块，避免 write_verilog 写出多个模块导致 CEC 重定义）：
  id   : flatten                                  —— 恒等控制（漂移应当 ≈0）
  opt  : flatten; opt -full                       —— 局部逻辑优化
  abc  : flatten; techmap; opt -full; abc -g AND,OR,XOR,XNOR,MUX
  aig  : flatten; techmap; opt -full; aigmap      —— 全部打成 AIG（AND/INV）
  nand : flatten; techmap; opt -full; abc -g NAND,NOR

每个变体都：
  1) `rename -top` 成唯一模块名（否则 CEC 报 Re-definition of module）；
  2) `write_verilog -noattr`；
  3) 用 `generate_trans/cec/direct_cec.py` 对 golden(=原网表) 做 CEC，只有 PASS 才入表。

产物：
  generate_trans/yosys_netlists/<host>/<src_stem>__ys_<recipe>.v
  generate_trans/yosys_netlists/ys_manifest.csv   （含 CEC 结果 / 门数 / 运行秒数）
  generate_trans/yosys_netlists/logs/<...>.log

用法（Windows 侧跑，内部通过 wsl 调 yosys）：
  py phase2/ys/build_yosys_netlists.py --hosts rs232t1000 --recipes id,opt,abc
  py phase2/ys/build_yosys_netlists.py            # 全部 host × 全部 recipe
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import re
import subprocess
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
HOSTS_ROOT = ROOT / "generate_trans" / "hosts"
OUT_ROOT = ROOT / "generate_trans" / "yosys_netlists"
VALI = "/mnt/c/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali"
WSL_ROOT = _eqguard_path('', wsl=True)

NO_OPT = {"rt", "rtc"}          # 纯往返配方：跳过公共 opt -full / opt_clean（否则名字被清掉）

RECIPES = {
    "id": "flatten",
    "rt": "flatten",                 # 纯往返：不做任何 opt（跳过公共 opt -full / opt_clean）
    "rtc": "flatten\nopt -full",     # 只做优化、不做 opt_clean（用来定位名字是被哪一步清掉的）
    "opt": "flatten\nopt -full",
    "abc": "flatten\ntechmap\nopt -full\nabc -g AND,OR,XOR,XNOR,MUX",
    "aig": "flatten\ntechmap\nopt -full\naigmap\nopt_clean",
    "nand": "flatten\ntechmap\nopt -full\nabc -g NAND,NOR",
}


def parse_args():
    ap = argparse.ArgumentParser(description="yosys 生成等价网表 + CEC")
    ap.add_argument("--hosts", type=str, default="",
                    help="逗号分隔；空=generate_trans/hosts 下所有 host")
    ap.add_argument("--recipes", type=str, default="id,opt,abc,aig,nand")
    ap.add_argument("--kinds", type=str, default="clean,trojan,control",
                    help="clean=干净基底；trojan/control=注入视图")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--skip-cec", action="store_true")
    ap.add_argument("--hosts-root", type=Path, default=HOSTS_ROOT,
                    help="感染视图所在目录（默认 generate_trans/hosts；B 型用 hosts_bt）")
    ap.add_argument("--out-root", type=Path, default=OUT_ROOT,
                    help="等价网表输出目录（B 型用 yosys_netlists_beta）")
    return ap.parse_args()


def hosts_of(args):
    if args.hosts:
        return [h.strip() for h in args.hosts.split(",") if h.strip()]
    return sorted(p.name for p in HOSTS_ROOT.iterdir()
                  if p.is_dir() and (p / "base").is_dir())


def source_files(host: str, kinds) -> list:
    """(src_path, kind, stem)：干净基底 + 该 host 下的注入视图。"""
    out = []
    if "clean" in kinds:
        for f in sorted((HOSTS_ROOT / host / "base").glob("*_clean.v")):
            out.append((f, "clean", f.stem))
    if {"trojan", "control"} & set(kinds):
        for f in sorted((HOSTS_ROOT / host).glob("*.v")):
            stem = f.stem
            if "__inj" in stem and "trojan" in kinds:
                out.append((f, "trojan", stem))
            elif "__ctl" in stem and "control" in kinds:
                out.append((f, "control", stem))
    return out


def module_name(p: Path) -> str:
    m = re.search(r"^\s*module\s+([A-Za-z_\\][\w$]*)", p.read_text(encoding="utf-8", errors="replace"),
                  re.M)
    return m.group(1) if m else ""


def wsl(path: Path) -> str:
    p = str(Path(path).resolve()).replace("\\", "/")
    return p.replace("C:/", "/mnt/c/", 1) if p[1:3] == ":/" else p


def main() -> int:
    global HOSTS_ROOT, OUT_ROOT
    args = parse_args()
    HOSTS_ROOT, OUT_ROOT = args.hosts_root.resolve(), args.out_root.resolve()
    recipes = [r.strip() for r in args.recipes.split(",") if r.strip()]
    for r in recipes:
        if r not in RECIPES:
            print(f"[ERROR] 未知 recipe: {r}（可选 {list(RECIPES)}）")
            return 1
    kinds = {k.strip() for k in args.kinds.split(",")}
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "logs").mkdir(exist_ok=True)

    jobs = []
    for host in hosts_of(args):
        for src, kind, stem in source_files(host, kinds):
            mod = module_name(src)
            if not mod:
                print(f"[WARN] 取不到模块名，跳过 {src.name}")
                continue
            for r in recipes:
                jobs.append((host, kind, stem, src, mod, r))
    print(f"[INFO] {len(jobs)} 个 (design, recipe) 任务")
    if not jobs:
        return 1

    sh = OUT_ROOT / "_gen.sh"
    L = ["#!/bin/bash", "set +e",
         f"OUT={wsl(OUT_ROOT)}", f"V={VALI}",
         "echo 'host,kind,stem,recipe,rc,bytes,always,cells,cec,secs'"
         " > $OUT/ys_manifest.csv"]
    for host, kind, stem, src, mod, r in jobs:
        wsrc, new = wsl(src), f"{stem}__ys_{r}"
        outv = f"$OUT/{host}/{new}.v"
        L += [f"mkdir -p $OUT/{host}",
              f'cat > /tmp/ys_{new}.ys <<YSEOF',
              f"read_verilog -sv $V/verilog_lib.v",
              f"read_verilog -sv {wsrc}",
              f"hierarchy -top {mod}",
              "proc",
              *([] if r in NO_OPT else ["opt -full"]),
              *RECIPES[r].split("\n"),
              *([] if r in NO_OPT else ["opt_clean"]),
              f"rename -top {new}",
              f"write_verilog -noattr {outv}",
              "YSEOF",
              "t0=$(date +%s)",
              f"timeout {args.timeout} yosys -q -s /tmp/ys_{new}.ys "
              f"-l $OUT/logs/{new}.log > /dev/null 2>&1",
              "rc=$?; t1=$(date +%s); secs=$((t1-t0))",
              f'if [ -f {outv} ]; then bytes=$(wc -c < {outv}); '
              f'alw=$(grep -c always {outv}); '
              f'cells=$(grep -cE "^  [A-Za-z_\\\\][A-Za-z0-9_\\\\]* " {outv}); '
              f'else bytes=0; alw=0; cells=0; fi']
        if args.skip_cec:
            L.append('cec="SKIP"')
        else:
            L += [f"cd {WSL_ROOT}",
                  f"python3 generate_trans/cec/direct_cec.py --golden {wsrc} "
                  f"--candidate {outv} --vali-dir $V --timeout {args.timeout} "
                  f"--log $OUT/logs/cec_{new}.log > $OUT/logs/cec_{new}.txt 2>&1",
                  f'cec=$(grep -a "CEC" $OUT/logs/cec_{new}.txt | tail -1 | sed "s/,/;/g")']
        L += [f'echo "{host},{kind},{stem},{r},$rc,$bytes,$alw,$cells,$cec,$secs"'
              f" >> $OUT/ys_manifest.csv",
              f'echo "[{host} {stem} {r}] rc=$rc cec=$cec secs=$secs"']
    sh.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[INFO] 脚本 -> {sh}")
    r = subprocess.run(["wsl", "-e", "bash", "-c", f"sed 's/\\r$//' {wsl(sh)} | bash"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-8000:])
    if r.stderr:
        print("[stderr]", r.stderr[-2000:])
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
