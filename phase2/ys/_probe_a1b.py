# -*- coding: utf-8 -*-
"""_probe_a1b.py —— 看 dataset_meta.json 的 per_view 字段（A1 要用）。"""
import json
from pathlib import Path

OUT = Path("10.15/01_数据与标签/A1_变换统计/_probe_a1b.txt")
lines = []
for meta in ("generate_trans/folds/hosts_beta2/data/processed/dataset_meta.json",
             "10.13/group_fold_v2/processed/dataset_meta.json",
             "10.13/group_fold_ys5/processed/dataset_meta.json"):
    p = Path(meta)
    lines.append("=" * 20 + f" {meta} exists={p.exists()}")
    if not p.exists():
        continue
    m = json.loads(p.read_text(encoding="utf-8"))
    lines.append("top keys: " + ", ".join(m.keys()))
    for k in ("orig", "trans", "alignment_pairs", "cec_all_pass", "n_views"):
        v = m.get(k)
        lines.append(f"  {k}: {json.dumps(v, ensure_ascii=False)[:260] if not isinstance(v, int) else v}")
    pv = m.get("per_view")
    lines.append(f"per_view: type={type(pv).__name__}")
    if isinstance(pv, dict) and pv:
        k0 = next(iter(pv))
        lines.append(f"  key sample = {k0!r}")
        lines.append(json.dumps(pv[k0], ensure_ascii=False, indent=1)[:900])
        # 聚合：按 op 统计
        keys = sorted({kk for v in pv.values() if isinstance(v, dict) for kk in v})
        lines.append("  per_view 子字段: " + ", ".join(keys))
    elif isinstance(pv, list) and pv:
        lines.append(json.dumps(pv[0], ensure_ascii=False, indent=1)[:900])
OUT.write_text("\n".join(lines), encoding="utf-8")
print("done")
