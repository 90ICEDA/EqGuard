"""build_fold_v31.py —— 用 B1-1 的重转产物建 fold v3.1（trojan 绑定 = 1.000）。

与 v3 的差别只有两处：
  1. `ys_abc` / `ys_nand` 的 trans 换成 `generate_trans/b1bind/<tag>/conv/.../*.v`
     （`keep=bnd` ✓ + 当前 `assign_to_gates` ✓ → 带 `inst_prov` ✓）；
  2. 剔除"keep 也绑不上"的 6 个视图（29 个 view×recipe）✗ —— 见
     `10.15/01_数据与标签/B1_可信标签/tables/b1_excluded_views.csv` ✓。
其余（orig / id / aig / opt / rt 视图）**原样沿用 v3** ✓（保证只有被改的部分变化 ✓）。

用法：
  python -X utf8 phase2/ys/build_fold_v31.py            # prep
  # 然后：cd <fold> && parser2 ... ; process_pt2 ...
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase2" / "ys"))
import make_inst_alignment as MIA  # noqa: E402

V3 = ROOT / "generate_trans" / "folds" / "hosts_bt3"
V31 = ROOT / "generate_trans" / "folds" / "hosts_bt31"
BIND = ROOT / "generate_trans" / "b1bind"
EXCL = ROOT / "10.15" / "01_数据与标签" / "B1_可信标签" / "tables" / "b1_excluded_views.csv"
RECIPE_OF = {"ys_abc": "abc", "ys_nand": "nand", "ys_aig": "aig",
             "ys_id": "id", "ys_opt": "opt", "ys_rt": "rt"}


def main() -> int:
    ap = argparse.ArgumentParser(description="建 fold v3.1（B1-1 重转 + 剔除绑不上的视图）")
    ap.add_argument("--src", type=Path, default=V3)
    ap.add_argument("--out", type=Path, default=V31)
    ap.add_argument("--excluded", type=Path, default=EXCL)
    ap.add_argument("--lib", type=Path, default=MIA.LIB_DEFAULT)
    a = ap.parse_args()
    W = a.out.resolve()
    lib = MIA.NL.load_library(a.lib)

    meta = pd.read_csv(a.src / "views_meta.csv")
    excl = pd.read_csv(a.excluded).view.astype(str).tolist()
    keep = meta[~meta.src_view.isin(excl)].copy()
    print(f"[INFO] v3 视图 {len(meta)} → 剔除 {len(meta) - len(keep)} 行（{len(excl)} 个视图）→ {len(keep)}")

    for d in ("orig", "trans", "mappings", "logs", "data/for_train", "data/not_for_train"):
        (W / d).mkdir(parents=True, exist_ok=True)
    for f in ("verilog_lib.v", "gate_full_to_simplified_mapping.json",
              "gatelookup_recommended.json"):
        if (a.src / f).exists():
            shutil.copy2(a.src / f, W / f)

    rows, n_bind = [], 0
    for r in keep.itertuples():
        viewer, host = str(r.view), str(r.host)
        srcv, op = str(r.src_view), str(r.op)
        recipe = RECIPE_OF.get(op, op)
        root = "hosts_a4" if str(r.batch) in ("a4", "a4b") else "hosts_bt2"
        src = ROOT / "generate_trans" / root / host / f"{srcv}.v"
        if recipe in ("abc", "nand"):
            tag = f"{'a4' if root == 'hosts_a4' else 'bt2'}_{host}"
            cand = BIND / tag / "conv" / host / f"{srcv}__keepbnd__ys_{recipe}.v"
            n_bind += 1
        else:
            cand = a.src / "trans" / f"{viewer}.v"
        if not (src.exists() and cand.exists()):
            print(f"[WARN] 缺文件，跳过 {viewer}（src={src.exists()} cand={cand.exists()}）")
            continue
        mp = cand.with_suffix(".map.json")
        ip = ({str(k): str(v) for k, v in
               (json.loads(mp.read_text(encoding="utf-8")).get("inst_prov") or {}).items()}
              if mp.exists() else {})
        srcf, candf = MIA.src_facts(src, lib), MIA.cand_facts(cand)
        align, _lg, hits = MIA.build_align(srcf, candf, ip)
        (W / "mappings" / f"{viewer}.json").write_text(json.dumps({
            "src_verilog": f"{srcv}.v", "src_view": srcv, "rw_view": viewer,
            "operator_family": op, "mode": op, "generator": "yosys+assign_to_gates",
            "node_alignment": align, "n_rewritten": max(0, len(candf["gates"]) - len(align)),
            "n_split_objects": 0, "skipped": {},
            "hit_by_instprov": hits["instprov"], "hit_by_base": hits["base"],
            "hit_by_port": hits["port"], "hit_by_net": hits["net"],
            "hit_by_name": hits["name"], "batch": str(r.batch),
            "source": "b1bind" if recipe in ("abc", "nand") else "v3",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copy2(cand, W / "trans" / f"{viewer}.v")
        shutil.copy2(src, W / "orig" / f"{srcv}.v")
        rows.append({"view": viewer, "host": host, "src_view": srcv, "inst_id": str(r.inst_id),
                     "kind": str(r.kind), "family": str(r.family), "op": op,
                     "label1": int(getattr(r, "label1", 0) or 0),
                     "label_usable": int(getattr(r, "label_usable", 0) or 0),
                     "batch": str(r.batch),
                     "source": "b1bind" if recipe in ("abc", "nand") else "v3"})
    nm = pd.DataFrame(rows)
    nm.to_csv(W / "views_meta.csv", index=False, encoding="utf-8-sig")

    # views.json：沿用 v3 的 split，只保留仍存在的视图 ✓
    old = json.loads((a.src / "views.json").read_text(encoding="utf-8"))
    present = set(nm.view)
    new = {"fold": "hosts_bt31", "level": old.get("level")}
    for k in ("train_views", "val_views", "test_views"):
        new[k] = [v for v in old.get(k, []) if v in present]
    (W / "views.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")

    # CEC 状态：沿用 v3（重转视图在 keep_ablation 里已逐个 CEC PASS ✓）
    cec_old = pd.read_csv(Path(str(a.src)) / "view_manifest_cec.csv")
    cec_old[cec_old["view_name"].isin(present)].to_csv(W / "view_manifest_cec.csv",
                                                  index=False, encoding="utf-8-sig")

    ovm = json.loads((a.src / "orig_view_map.json").read_text(encoding="utf-8"))
    ovm2 = {k: [v for v in vs if v in present] for k, vs in ovm.items()}
    ovm2 = {k: v for k, v in ovm2.items() if v}
    (W / "orig_view_map.json").write_text(json.dumps(ovm2, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

    print(f"[OK] 视图 {len(nm)}（abc/nand 用 b1bind 重转 {n_bind} 个 ✓）"
          f"｜train/val/test = {len(new['train_views'])}/{len(new['val_views'])}/{len(new['test_views'])}")
    print(f"[OK] trans={len(list((W/'trans').glob('*.v')))} "
          f"orig={len(list((W/'orig').glob('*.v')))} "
          f"mappings={len(list((W/'mappings').glob('*.json')))}")
    print(f"     输出 {W}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
