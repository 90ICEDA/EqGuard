"""audit_feats_by_op.py —— 按"新类型网表"逐类抽 1 个，验证 parser2 的特征是否正常。

背景（2026-10-17）：v3 的 `feats_trans.npy` 里 `log1p(#in)` 均值只有 0.14（老 fold 1.32）✗，
根因是 `parser2.getlineinfo` 把 `\\U127.Y` 截断成 `\\U127` ✗、`fixassigns` 读不了 yosys 的
`assign A = B ;` ✗、`getprimlist` 只会切老式 `input` 行 ✗（均已修 ✓）。

做法：搭一个**最小工作目录**（`verilog_lib.v` + 两个 gate 映射 + `orig/`1 个 + `trans/`N 个），
直接用 parser2 的 CLI 跑一遍 ✓，再按 `metadata_trans.json.file_ids` 把 `feats_trans.npy`
按视图切开 ✓，逐视图报告 39 维的"结构位是否正常" ✓。

维度约定（`parser2.generate_features`）：前 35 维 = 门类型 one-hot ✓，
最后 4 维依次是 `log1p(#in)`、`log1p(#neighbs)`、`connected_to_prim_inp`、`connected_to_prim_out` ✓。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FOLD = ROOT / "generate_trans" / "folds" / "hosts_bt3"
SCRATCH = ROOT / "_feataudit"
OPS = ["abc", "nand", "aig", "id", "opt", "rt"]


def pick_trans(host: str, op: str) -> Path | None:
    """同一 host 下找 `*__ys_<op>.v`（优先 keepcur ✓，否则 keepnone ✓）。"""
    cands = sorted(FOLD.joinpath("trans").glob(f"{host}__*__ys_{op}.v"))
    for pref in ("keepcur", "keepnone"):
        for p in cands:
            if pref in p.stem:
                return p
    return cands[0] if cands else None


def pick_orig(host: str) -> Path | None:
    cands = sorted(FOLD.joinpath("orig").glob(f"{host}__*.v"))
    return cands[0] if cands else None


def build_scratch(host: str, ops: list[str]) -> list[str]:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    for d in ("orig", "trans", "data/for_train", "data/not_for_train"):
        SCRATCH.joinpath(d).mkdir(parents=True, exist_ok=True)
    for f in ("verilog_lib.v", "gate_full_to_simplified_mapping.json",
              "gatelookup_recommended.json"):
        shutil.copy2(FOLD / f, SCRATCH / f)
    used = []
    o = pick_orig(host)
    if o is None:
        raise SystemExit(f"[ERROR] orig 里找不到 {host}__*.v")
    shutil.copy2(o, SCRATCH / "orig" / o.name)
    for op in ops:
        p = pick_trans(host, op)
        if p is None:
            print(f"[WARN] 找不到 {host} × {op}，跳过")
            continue
        shutil.copy2(p, SCRATCH / "trans" / p.name)
        used.append(op)
    print(f"[scratch] {SCRATCH}  orig=1  trans={len(used)} ({','.join(used)})")
    return used


def main() -> int:
    ap = argparse.ArgumentParser(description="按 op 类型抽 1 个网表验证 parser2 特征")
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--ops", default=",".join(OPS))
    ap.add_argument("--cycle-mode", default="contract", choices=["none", "contract"],
                    help="必须与建 fold 时一致（v3 用 contract → 39 维）；none → 33 维")
    ap.add_argument("--keep-scratch", action="store_true")
    a = ap.parse_args()
    ops = [s.strip() for s in a.ops.split(",") if s.strip()]

    used = build_scratch(a.host, ops)
    cmd = [sys.executable, "-X", "utf8", str(ROOT / "data" / "verilog_data" / "parser2.py"),
           "--out-root", "./data/for_train", "--skip-debug",
           "--cycle-mode", a.cycle_mode]
    print("[run] " + " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(SCRATCH))
    print(f"[parser2] rc={rc}")
    if rc != 0:
        return rc

    meta = json.loads((SCRATCH / "data/for_train/metadata_trans.json")
                      .read_text(encoding="utf-8"))
    feats = np.load(SCRATCH / "data/for_train/feats_trans.npy")
    file_ids = meta["file_ids"]
    idx = {}
    for i, v in enumerate(file_ids):
        idx.setdefault(v, []).append(i)
    rows = []
    n = feats.shape[1]
    for view, ii in sorted(idx.items()):
        f = feats[ii, :]
        last = f[:, -4:]
        ones = f[:, :-4]
        rows.append((view, len(ii),
                     [float(np.mean(last[:, k])) for k in range(4)],
                     [float(last[:, k].max()) for k in range(4)],
                     int((ones.sum(axis=1) > 0).sum())))
    print(f"\n=== 逐视图（dims={n}；末 4 列 = parser2 的结构位）===")
    print(f"{'view':50s} {'nodes':>6s} {'onehot':>6s} | " +
          " ".join(f"{n - 4 + k}:mean/max".rjust(15) for k in range(4)))
    for r in rows:
        cells = " ".join(f"{r[2][k]:6.3f}/{r[3][k]:5.2f}".rjust(15) for k in range(4))
        print(f"{r[0][:50]:50s} {r[1]:6d} {r[4]:6d} | {cells}")

    dead = [j for j in range(n) if np.unique(feats[:, j]).size == 1]
    print(f"\n[列体检] 恒定列 {len(dead)}/{n}：{dead}")
    print("[列体检] 末 4 列 range：" + "  ".join(
        f"{n - 4 + k}={feats[:, n - 4 + k].min():.2f}..{feats[:, n - 4 + k].max():.2f}"
        for k in range(4)))
    bad = [r for r in rows if r[1] and r[4] / r[1] < 0.99]     # 每个 net 有 1 个 "1'b1" 哨兵节点无门类型 ✓
    print(f"[结论] 门类型 one-hot 覆盖不全的视图 {len(bad)}/{len(rows)}"
          + (f"：{[r[0] for r in bad]}" if bad else "（全部覆盖 ✓）"))
    if not a.keep_scratch:
        shutil.rmtree(SCRATCH, ignore_errors=True)
    return 0 if not bad else 2


if __name__ == "__main__":
    raise SystemExit(main())
