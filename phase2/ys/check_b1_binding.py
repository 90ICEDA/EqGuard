"""check_b1_binding.py —— B1-1 的**绑定断言**：重转后的 trojan 门是否 100% 绑上。

判据与 `make_a2_anchors.cov()` 完全一致 ✓（方向 **源 → 变换后** ✓）：
  · `core` = `provenance.json` 里该视图的 `new_gates`（注入门实例名 ✓）；
  · `align` = `make_inst_alignment.build_align(srcf, candf, inst_prov, focus=core)` 的返回（`src门 → cand门` ✓）；
  · **绑定率 = |core ∩ align| / |core|** ✓；要求 **1.000** ✓，否则该视图不能进训练集 ✓。

输入：`generate_trans/b1bind/<tag>/conv/{convert_manifest.csv,<host>/*.v,*.map.json}`
      `generate_trans/{hosts_a4,hosts_bt2}/<host>/provenance.json`
输出：`10.15/01_数据与标签/B1_可信标签/tables/b1_binding_after.csv`（逐视图×配方）
      同目录 `b1_binding_after_summary.csv`
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase2" / "ys"))
import make_inst_alignment as MIA  # noqa: E402

BIND = ROOT / "generate_trans" / "b1bind"
OUT = ROOT / "10.15" / "01_数据与标签" / "B1_可信标签" / "tables"


def load_prov(root: str) -> dict:
    out = {}
    for f in sorted((ROOT / "generate_trans" / root).glob("*/provenance.json")):
        for rec in json.loads(f.read_text(encoding="utf-8")):
            out[rec["view"]] = rec
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="B1-1 绑定断言（core 是否 100% 绑上）")
    ap.add_argument("--lib", type=Path, default=MIA.LIB_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()
    lib = MIA.NL.load_library(a.lib)

    rows = []
    for tag_dir in sorted(p for p in BIND.iterdir() if (p / "conv" / "convert_manifest.csv").exists()):
        tag = tag_dir.name
        root = "hosts_a4" if tag.startswith("a4_") else "hosts_bt2"
        prov = load_prov(root)
        man = pd.read_csv(tag_dir / "conv" / "convert_manifest.csv")
        for r in man.itertuples():
            stem, recipe = str(r.stem), str(r.recipe)
            view = stem.split("__keep")[0]
            rec = prov.get(view) or {}
            core = set(rec.get("new_gates") or []) if rec.get("kind") == "trojan" else set()
            if not core:
                continue
            cand = Path(str(r.file))
            src = ROOT / "generate_trans" / root / str(r.host) / f"{view}.v"
            if not (cand.exists() and src.exists()):
                continue
            mp = cand.with_suffix(".map.json")
            ip = ({str(k): str(v) for k, v in
                   (json.loads(mp.read_text(encoding="utf-8")).get("inst_prov") or {}).items()}
                  if mp.exists() else {})
            srcf, candf = MIA.src_facts(src, lib), MIA.cand_facts(cand)
            align, _legacy, _hits = MIA.build_align(srcf, candf, ip, focus=core)
            bound = len(core & set(align))
            rows.append({"tag": tag, "view": view, "host": str(r.host), "recipe": recipe,
                         "n_core": len(core), "n_bound": bound,
                         "bind_rate": round(bound / max(1, len(core)), 4),
                         "full": bound == len(core),
                         "missing": ",".join(sorted(core - set(align)))[:200]})
        print(f"[{tag}] 累计 {len(rows)} 行")

    d = pd.DataFrame(rows)
    if d.empty:
        print("[ERROR] 没有数据")
        return 1
    a.out_dir.mkdir(parents=True, exist_ok=True)
    d.sort_values(["full", "bind_rate", "view"]).to_csv(
        a.out_dir / "b1_binding_after.csv", index=False, encoding="utf-8-sig")
    s = (d.groupby("recipe").agg(views=("view", "size"), core=("n_core", "sum"),
                                 bound=("n_bound", "sum"),
                                 views_ok=("full", lambda x: int(x.sum())))
         .reset_index())
    s["bind_rate"] = (s.bound / s.core).round(4)
    s.to_csv(a.out_dir / "b1_binding_after_summary.csv", index=False, encoding="utf-8-sig")

    print(f"\n[结论] 视图×配方 {len(d)}｜core 合计 {int(d.n_core.sum())}｜已绑 {int(d.n_bound.sum())}"
          f"（{d.n_bound.sum() / max(1, d.n_core.sum()):.4f}）｜100% 绑定 {int(d.full.sum())}/{len(d)}")
    print(s.to_string(index=False))
    bad = d[~d.full]
    if len(bad):
        print("\n[仍缺] 前 10：")
        print(bad.head(10)[["view", "recipe", "n_core", "n_bound", "missing"]].to_string(index=False))
    print(f"\n[导出] {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
