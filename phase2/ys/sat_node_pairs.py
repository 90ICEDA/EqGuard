"""sat_node_pairs.py —— B05：**跨实现节点对**的 SAT 等价证明 ✓（`node_pairs.csv` ✓）。

做法 ✓（比逐对 miter 便宜得多 ✓）：
  1. 同一木马实例的**两个实现**（如 `ys_id` ↔ `ys_abc`）一起读入 ✓；
  2. `equiv_make <modA> <modB> equiv` ✓ —— 按**名字**建立 `$equiv` 断言 ✓；
  3. `equiv_simple -undef` ✓（组合）+ `equiv_induct -undef -seq 4` ✓（时序）→ **批量**证明 ✓；
  4. 解析日志里 `Trying to prove $equiv for \\NET: success!/failed` ✓ → 逐网裁决 ✓。

输出 ✓：`node_pairs.csv`（host, inst, pair, net, status ∈ {proved, differ, unknown}, wall_s, log ✓）
口径 ✓：`proved` = SAT 证明两实现在该网**功能等价** ✓；`differ` = 找到反例 ✗；
        `unknown` = 超时/未匹配 ⚠️（**不得**当作等价 ✗）。

⚠️ 名字≠功能 ✓：`proved` 只说明"**同名网**功能一致" ✓，**不能**反推"木马标签可搬运" ✗（那要看 B07 的 `role_status` ✓）。
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
import time
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
WSL_ROOT = _eqguard_path('', wsl=True)
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
PAT_PROVE = re.compile(r"Trying to prove \$equiv for \\+(\S+?):\s*(success!|failed)")


def wsl(p: Path) -> str:
    return f"{WSL_ROOT}/{Path(p).resolve().relative_to(ROOT).as_posix()}"


def module_name(v: Path) -> str:
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*module\s+([\\A-Za-z_][\w\\.$]*)", ln)
        if m:
            return m.group(1).lstrip("\\")
    return v.stem


def find_impl(fold: str, host: str, inst: str, recipe: str) -> Path | None:
    d = ROOT / "generate_trans" / "folds" / fold / "trans"
    cand = sorted(d.glob(f"{host}__{inst}_d1_s42__*{recipe}.v"))
    return cand[0] if cand else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", default="hosts_bt31")
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--pairs", default="ys_id:ys_abc,ys_id:ys_opt,ys_abc:ys_opt")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--induct-seq", type=int, default=4)
    ap.add_argument("--out", default=str(OUT / "tables/node_pairs.csv"))
    ap.add_argument("--logdir", default=str(OUT / "logs"))
    a = ap.parse_args()

    logdir = Path(a.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for pr in [s for s in a.pairs.split(",") if ":" in s]:
        ra, rb = [x.strip() for x in pr.split(":")]
        va, vb = find_impl(a.fold, a.host, a.inst, ra), find_impl(a.fold, a.host, a.inst, rb)
        if not (va and vb):
            print(f"[skip] {pr} 缺文件 ✗")
            rows.append(dict(host=a.host, inst=a.inst, pair=pr, net="", status="missing",
                             wall_s=0.0, log=""))
            continue
        ma, mb = module_name(va), module_name(vb)
        ys = logdir / f"eq_{a.host}_{a.inst}_{ra}__{rb}.ys"
        log = ys.with_suffix(".log")
        ys.write_text("\n".join([
            f'read_verilog "{wsl(va)}"', f'read_verilog "{wsl(vb)}"',
            f"equiv_make {ma} {mb} equiv", "select -module equiv",
            "equiv_simple -undef",
            f"equiv_induct -undef -seq {a.induct_seq}",
            "equiv_status",
        ]) + "\n", encoding="utf-8")
        t0 = time.time()
        try:
            p = subprocess.run(["wsl", "-e", "bash", "-lc",
                                f'cd "{WSL_ROOT}" && timeout {a.timeout} yosys -s "{wsl(ys)}"'],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=a.timeout + 60)
            out = (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            out = "TIMEOUT"
        wall = round(time.time() - t0, 1)
        log.write_text(out, encoding="utf-8")
        hits = PAT_PROVE.findall(out)
        n_ok = sum(1 for _, st in hits if st == "success!")
        n_bad = sum(1 for _, st in hits if st == "failed")
        m = re.search(r"Proved (\d+) previously unproven", out)
        n_bulk = int(m.group(1)) if m else 0
        print(f"  {pr}: nets_proved={n_ok} nets_failed={n_bad} bulk_proved={n_bulk} "
              f"wall={wall}s")
        if not hits:
            rows.append(dict(host=a.host, inst=a.inst, pair=pr, net="", status="unknown",
                             wall_s=wall, log=str(log.relative_to(ROOT))))
            continue
        for net, st in hits:
            rows.append(dict(host=a.host, inst=a.inst, pair=pr, net=net,
                             status="proved" if st == "success!" else "differ",
                             wall_s=wall, log=str(log.relative_to(ROOT))))
    df = pd.DataFrame(rows)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        old = pd.read_csv(out, encoding="utf-8-sig")
        df = pd.concat([old, df], ignore_index=True).drop_duplicates(
            subset=["host", "inst", "pair", "net"], keep="last")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[out] {out}（{len(df)} 行 ✓）")
    if not df.empty and "status" in df:
        print(df["status"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
