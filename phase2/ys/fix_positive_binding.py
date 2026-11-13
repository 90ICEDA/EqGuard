"""fix_positive_binding.py —— B1-1：重转 abc/nand 视图，让 trojan 节点**必然可绑**。

为什么（2026-10-17 审计结论）：
  · 186 个 trojan 视图里只有 103 个 100% 绑定 ✓，83 个缺 522/2101 个 core ✗
    （`ys_abc` 0.226 ✗ / `ys_nand` 0.167 ✗，而 `id/rt` = 1.000 ✓）；
  · 根因不是"名字被抹"这么简单 ✗：`yslib_test` 这批转换是**老流水线**做的 ✗，
    `<stem>.map.json` 里**没有 `inst_prov`** ✗ → 实例级对齐无从谈起 ✓
    （对照：A4 批有 `inst_prov` ✓，`n_inst_prov` 2583/3096 = 83% ✓）；
  · 修法（按用户要求"**木马节点一定要绑定好，绑不好就 keep**"）：
    用当前 `keep_ablation.py`（`--schemes bnd` ✓）重转 abc/nand ✓ →
    它会调 `assign_to_gates.py` ✓ 产出 `.map.json`（含 `prov` / `inst_prov`）✓，
    且 `bnd` 保住了 DFF-Q 与主输出网名 ✓ → `by_net` 路线可用 ✓。

用法：
  python -X utf8 phase2/ys/fix_positive_binding.py --workers 2
  python -X utf8 phase2/ys/fix_positive_binding.py --only-batch yslib_test   # 只跑 bt2 那批
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FOLD = ROOT / "generate_trans" / "folds" / "hosts_bt3"
OUT_ROOT = ROOT / "generate_trans" / "b1bind"
LOG_DIR = ROOT / "_b1bind"
RECIPES = "abc,nand"


def jobs(only_batch: str = "") -> list[dict]:
    m = pd.read_csv(FOLD / "views_meta.csv")
    m = m[m.op.isin(["ys_abc", "ys_nand"])].copy()
    if only_batch:
        m = m[m.batch == only_batch]
    m["root"] = m.batch.map(lambda b: "hosts_a4" if b in ("a4", "a4b") else "hosts_bt2")
    out = []
    for (root, host), g in m.groupby(["root", "host"]):
        bases = sorted(g.src_view.unique())
        out.append({"root": root, "host": host, "views": bases,
                    "tag": f"{root.split('_')[-1]}_{host}"})
    return out


def run_one(j: dict) -> tuple[str, int, float]:
    tag = j["tag"]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"{tag}.log"
    cmd = [sys.executable, "-X", "utf8", "-u", str(ROOT / "phase2" / "ys" / "keep_ablation.py"),
           "--hosts-root", str(ROOT / "generate_trans" / j["root"]),
           "--host", j["host"],
           "--views", ",".join(j["views"]),
           "--recipes", RECIPES,
           "--schemes", "bnd",
           "--out", str(OUT_ROOT / tag),
           "--tables", str(LOG_DIR / "tables" / tag)]
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as f:
        f.write("[cmd] " + " ".join(cmd) + "\n")
        f.flush()
        rc = subprocess.call(cmd, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT)
    return tag, rc, round(time.time() - t0, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description="B1-1 重转 abc/nand（keep=bnd）以恢复 trojan 绑定")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only-batch", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    js = jobs(a.only_batch)
    total = sum(len(j["views"]) for j in js) * 2
    print(f"[计划] {len(js)} 组 / {sum(len(j['views']) for j in js)} 个基础视图 × 2 配方 = {total} 次转换")
    for j in js:
        print(f"  {j['tag']:24s} {j['root']:11s} {j['host']:12s} views={len(j['views'])}")
    if a.dry_run:
        return 0

    ok = 0
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        futs = {ex.submit(run_one, j): j for j in js}
        for fu in as_completed(futs):
            tag, rc, secs = fu.result()
            ok += rc == 0
            print(f"[done] {tag:24s} rc={rc} {secs}s")
    print(f"[汇总] {ok}/{len(js)} 组成功｜输出 {OUT_ROOT}｜日志 {LOG_DIR}")
    return 0 if ok == len(js) else 1


if __name__ == "__main__":
    raise SystemExit(main())
