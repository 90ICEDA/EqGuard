"""make_mini_fold.py —— 从 fold v3.1 抽一个小 fold（rs232 训练 → s15850 测试），用于快速试 AP。

目的：GPU 上跑满 100 epoch 只要几分钟（节点 ~20 万 ✓），但仍是**真实 host 级泛化**（rs232 → s15850）✓。
注意：v3/v3.1 原来 `views.json` 的 **val 是 train 的子集** ✗（泄漏 ✗）→ 这里重新划分且**强制不相交** ✓。
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "generate_trans" / "folds" / "hosts_bt31"
OUT = ROOT / "generate_trans" / "folds" / "_mini31"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--train-hosts", default="rs232t1000")
    ap.add_argument("--test-hosts", default="s15850t100")
    ap.add_argument("--val-ratio", type=float, default=0.2)
    a = ap.parse_args()
    W = a.out.resolve()

    m = pd.read_csv(a.src / "views_meta.csv")
    trh = [h.strip() for h in a.train_hosts.split(",") if h.strip()]
    teh = [h.strip() for h in a.test_hosts.split(",") if h.strip()]
    tr_pool = sorted(m[m.host.isin(trh)].view)
    te = sorted(m[m.host.isin(teh)].view)
    n_val = max(1, int(len(tr_pool) * a.val_ratio))
    va = tr_pool[::max(1, len(tr_pool) // n_val)][:n_val]
    tr = [v for v in tr_pool if v not in set(va)]
    assert not (set(tr) & set(va)) and not (set(tr) & set(te)) and not (set(va) & set(te))

    for d in ("orig", "trans", "mappings", "logs", "data/for_train", "data/not_for_train"):
        (W / d).mkdir(parents=True, exist_ok=True)
    for f in ("verilog_lib.v", "gate_full_to_simplified_mapping.json", "gatelookup_recommended.json"):
        if (a.src / f).exists():
            shutil.copy2(a.src / f, W / f)
    sel = set(tr) | set(va) | set(te)
    for v in sel:
        for sub in ("trans", "mappings"):
            p = a.src / sub / (f"{v}.v" if sub == "trans" else f"{v}.json")
            if p.exists():
                shutil.copy2(p, W / sub / p.name)
    for sv in m[m.view.isin(sel)].src_view.unique():
        p = a.src / "orig" / f"{sv}.v"
        if p.exists():
            shutil.copy2(p, W / "orig" / p.name)

    (W / "views.json").write_text(json.dumps(
        {"fold": "mini31", "train_views": tr, "val_views": sorted(va), "test_views": te},
        ensure_ascii=False, indent=1), encoding="utf-8")
    m[m.view.isin(sel)].to_csv(W / "views_meta.csv", index=False, encoding="utf-8-sig")
    ovm = json.loads((a.src / "orig_view_map.json").read_text(encoding="utf-8"))
    ovm2 = {k: [v for v in vs if v in sel] for k, vs in ovm.items()}
    (W / "orig_view_map.json").write_text(
        json.dumps({k: v for k, v in ovm2.items() if v}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"[OK] mini fold: train {len(tr)} / val {len(va)} / test {len(te)}  → {W}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
