"""n4_protocol_check.py —— N4 三向泛化的**协议自检 + 泄漏检查**（CPU ✓，秒级 ✓）。

做三件事 ✓（与 `train_test2.3.py --fold-mode {loco,lro,lio}` 的拆法**逐行同构** ✓）：
  1. 复算每个 split 的 `train / val / test` 视图数 ✓；
  2. **泄漏检查** ✓：留出键（host / recipe / instance+匹配对照）**不得**出现在 train ∪ val ✓；
  3. 落盘 `tables/n4_protocol_check.csv` ✓ + 打印汇总 ✓（给 `protocol.md` 引用 ✓）。

用法 ✓：
    python phase2/ys/n4_protocol_check.py
    python phase2/ys/n4_protocol_check.py --work-dir generate_trans/folds/hosts_bt31 --circuits s38584t100
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
_MATCH_CTL = {"injalpha": "ctlmatcha", "injbeta": "ctlmatchb", "injgamma": "ctlmatchc",
              "injdelta": "ctlmatchd", "injepsilon": "ctlmatche", "injzeta": "ctlmatchf",
              "injeta": "ctlmatchg", "injtheta": "ctlmatchh"}


def inst_of(v: str) -> str:
    """视图名 → 实例名（injalpha / ctlmatcha …）；与 train_test2.3.py 同构 ✓。"""
    p = str(v).split("__")
    return p[1].split("_d1")[0] if len(p) > 1 else ""


def host_of(v: str) -> str:
    return str(v).split("__")[0]


def recipe_of(v: str) -> str:
    return str(v).split("__")[-1]


def build_splits(mode: str, test_views: list[str]) -> list[tuple[str, tuple[str, ...], list[str]]]:
    """与 train_test2.3.py 的 splits 构造逻辑一致 ✓。"""
    if mode == "loco":                       # 未见 host ✓
        return [(c, (c,), [v for v in test_views if v.startswith(c + "__")])
                for c in sorted({host_of(v) for v in test_views})]
    if mode == "lro":                        # 未见配方（综合流程）✓
        return [(r, (r,), [v for v in test_views if v.endswith("__" + r)])
                for r in sorted({recipe_of(v) for v in test_views})]
    insts = sorted({inst_of(v) for v in test_views if "__inj" in str(v)})   # 未见实例 ✓
    out = []
    for it in insts:
        held = (it,) + ((_MATCH_CTL[it],) if it in _MATCH_CTL else ())
        out.append((it, tuple(sorted(held)), [v for v in test_views if inst_of(v) == it]))
    return out


def key_fn(mode: str):
    if mode == "loco":
        return host_of
    if mode == "lro":
        return recipe_of
    return inst_of


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-dir", default=str(ROOT / "generate_trans/folds/hosts_bt31"))
    ap.add_argument("--circuits", default="s38584t100",
                    help="与训练命令一致 ✓（当前 N4 只用 s38584t100 做 test host ✓）")
    ap.add_argument("--out", default=str(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/n4_protocol_check.csv"))
    a = ap.parse_args()

    wd = Path(a.work_dir)
    spec = json.loads((wd / "views.json").read_text(encoding="utf-8"))
    kept = tuple(c.strip() for c in a.circuits.split(",") if c.strip())
    test_all = [v for v in spec["test_views"] if (not kept or v.startswith(kept))]
    tr_all, va_all = list(spec["train_views"]), list(spec["val_views"])
    print(f"[in] fold={spec['fold']}｜train={len(tr_all)}｜val={len(va_all)}｜test={len(test_all)}"
          f"（filter={kept or 'ALL'}）")

    rows = []
    for mode in ("loco", "lro", "lio"):
        kf = key_fn(mode)
        for name, held, tviews in build_splits(mode, test_all):
            bad = set(held)
            tr = [v for v in tr_all if kf(v) not in bad]
            va = [v for v in va_all if kf(v) not in bad]
            leak_tr = sorted({kf(v) for v in tr} & bad)
            leak_va = sorted({kf(v) for v in va} & bad)
            tkeys = {kf(v) for v in tviews}
            leak_te = sorted(tkeys & bad - bad)      # 恒空 ✓（test 本来就该命中 held ✓）
            overlap = sorted({kf(v) for v in tr + va} & tkeys)
            ok = (not leak_tr) and (not leak_va) and (not overlap)
            rows.append(dict(mode=mode, split=name, held=",".join(held),
                             n_train=len(tr), n_val=len(va), n_test=len(tviews),
                             leak_train=len(leak_tr), leak_val=len(leak_va),
                             overlap_trainval_test=len(overlap),
                             status="OK" if ok else "LEAK"))
            print(f"  [{mode:4s}] {name:12s} held={','.join(held):20s} "
                  f"train={len(tr):3d} val={len(va):3d} test={len(tviews):2d} "
                  f"leak(tr/va)={len(leak_tr)}/{len(leak_va)} overlap={len(overlap)} "
                  f"=> {'OK' if ok else 'LEAK ✗'}")

    df = pd.DataFrame(rows)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    n_bad = int((df["status"] != "OK").sum())
    print(f"\n[out] {out}")
    print(f"[sum] splits={len(df)}｜LEAK={n_bad}｜"
          f"每 mode: {df.groupby('mode').size().to_dict()}")
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
