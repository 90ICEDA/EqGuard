# -*- coding: utf-8 -*-
"""
cec_ab.py —— 决定性 CEC：**干净基底** vs **A/B 型感染网表**。

用来证明 A/B 两型的**功能差别**（不只是"按构造成立"）：
  clean vs A 型  → 预期 **PASS**（A 型只加死线，功能完全等价）
  clean vs B 型  → 预期 **FAIL**（B 型触发选通后劫持真实输出，功能真的变了）

用 WSL 里的 yosys（`generate_trans/cec/direct_cec.py`，state-boundary CEC），
逐对跑并落表 `10.10/results/cec_ab.csv`。

用法：
  py phase2/ys/cec_ab.py --hosts rs232t1000,s35932t200
  py phase2/ys/cec_ab.py --hosts rs232t1000 --instances 2
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

VALI = "/mnt/c/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali"


def parse_args():
    ap = argparse.ArgumentParser(description="clean vs A/B 型 的 CEC")
    ap.add_argument("--hosts", type=str, default="rs232t1000,s35932t200")
    ap.add_argument("--instances", type=int, default=1, help="每个 host 取前 N 个木马实例")
    ap.add_argument("--a-root", type=Path, default=ROOT / "generate_trans" / "hosts")
    ap.add_argument("--b-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "10.10" / "results" / "cec_ab.csv")
    return ap.parse_args()


def wsl(p: Path) -> str:
    p = str(Path(p).resolve()).replace("\\", "/")
    return p.replace("C:/", "/mnt/c/", 1) if p[1:3] == ":/" else p


def main() -> int:
    a = parse_args()
    jobs = []
    for h in [x.strip() for x in a.hosts.split(",") if x.strip()]:
        views = sorted(f.stem for f in (a.a_root / h).glob("*__inj*.v"))[:a.instances]
        base = next((a.a_root / h / "base").glob("*_clean.v"), None)
        for v in views:
            if base is None:
                continue
            for tag, root in (("clean_vs_A", a.a_root), ("clean_vs_B", a.b_root)):
                cand = root / h / f"{v}.v"
                jobs.append((h, v, tag, base, cand))
    print(f"[INFO] {len(jobs)} 对 CEC")
    if not jobs:
        return 1

    L = ["#!/bin/bash", "set +e",
         "cd /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train",
         f"OUT={wsl(a.out)}",
         'echo "host,view,pair,golden,candidate,proven,unproven,status" > $OUT']
    for h, v, tag, base, cand in jobs:
        if not cand.exists():
            L.append(f'echo "{h},{v},{tag},(missing),(missing),-,-,NOFILE" >> $OUT')
            continue
        nm = f"{h}_{v}_{tag}"
        L += [f"python3 generate_trans/cec/direct_cec.py --golden {wsl(base)} "
              f"--candidate {wsl(cand)} --vali-dir {VALI} --timeout {a.timeout} "
              f"--log /tmp/cec_{nm}.log > /tmp/o_{nm}.txt 2>&1",
              f"P=$(grep -oE 'proven=[0-9]+' /tmp/o_{nm}.txt | tail -1 | cut -d= -f2)",
              f"U=$(grep -oE 'unproven=[0-9]+' /tmp/o_{nm}.txt | tail -1 | cut -d= -f2)",
              f"S=$(grep -aoE 'PASS|FAIL' /tmp/o_{nm}.txt | tail -1)",
              f'echo "{h},{v},{tag},{base.name},{cand.name},${{P:--}},${{U:--}},${{S:-rc?}}" >> $OUT',
              f'echo "[{tag}] {h}/{v} → ${{S:-rc?}}"']
    sh = ROOT / "phase2" / "ys" / "_cec_ab.sh"
    sh.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    r = subprocess.run(["wsl", "-e", "bash", "-c", f"sed 's/\\r$//' {wsl(sh)} | bash"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-4000:])
    if a.out.exists():
        d = pd.read_csv(a.out)
        print("\n=== clean vs A/B 对照 ===")
        print(d.groupby(["pair", "status"]).size().to_string())
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
