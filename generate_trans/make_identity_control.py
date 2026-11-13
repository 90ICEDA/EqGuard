#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_identity_control.py — 任务3 控制实验①：Identity（恒等"改写"）

目的：回答"增强增益来自**真实变换**，还是仅仅来自'多喂了一些视图'"。
做法：构造与 `single_to_composed_d2` **训练视图数/预算完全对齐**、但训练视图是**原网表本身**
      （`edit_count = 0`，逐字节等于 `orig/<stem>.v`）的数据集；test 仍是 d2 的真实组合变换（180 个）。
      → identity 组 AP ≈ G1(Orig-only) ⇒ 增益来自真实变换；≈ 真实变换组 ⇒ 增益只是"多喂视图"的副产物。

产物：
  identity_matrix/verilog/<stem>__identity_d1_sNN.v   （硬链接 orig/<stem>.v；12 个/电路 × 5 电路）
  identity_matrix/verilog/<d2 的 180 个 test 视图>.v   （硬链接 matrix/verilog/…）
  identity_matrix/view_manifest_cec.csv                （identity 行 + d2 test 行）
  matrix/folds/identity_control/views.json             （train=identity, test=d2 真实变换）
  identity_matrix/README.md
用法：
  python make_identity_control.py --fold single_to_composed_d2 --copies 4
"""

import argparse
import json
import os
import shutil
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent          # generate_trans/
STEMS = {"rs232": "rs232t1000", "s15850": "s15850t100",
         "s35932": "s35932t200", "s38417": "s38417t300", "s38584": "s38584t100"}


def link_or_copy(src: Path, dst: Path) -> str:
    if dst.exists():
        return "exists"
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def main():
    ap = argparse.ArgumentParser(description="生成 Identity 控制数据集")
    ap.add_argument("--matrix-root", type=Path, default=CUR / "matrix")
    ap.add_argument("--orig-dir", type=Path, default=CUR / "orig")
    ap.add_argument("--fold", type=str, default="single_to_composed_d2",
                    help="test 视图来源 fold（默认 d2 = 真实组合变换）")
    ap.add_argument("--out-root", type=Path, default=CUR / "identity_matrix")
    ap.add_argument("--copies", type=int, default=4,
                    help="每电路造多少份 identity 视图（对齐 d1 的每电路 12 个 = 4 算子 × 3 seed）")
    ap.add_argument("--seeds", type=str, default="42,43,44")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    man = pd.read_csv(args.matrix_root / "view_manifest_cec.csv", encoding="utf-8-sig")
    tests = json.loads((args.matrix_root / "folds" / args.fold / "views.json")
                       .read_text(encoding="utf-8"))["test_views"]
    vdir = args.out_root / "verilog"
    vdir.mkdir(parents=True, exist_ok=True)

    # 1) identity 视图：硬链接 orig/<stem>.v（逐字节相同 → edit_count=0）
    id_rows, id_views, modes = [], [], {}
    depth_by = man.drop_duplicates("circuit").set_index("circuit")["depth_orig"].to_dict()
    for circ, stem in STEMS.items():
        if not (args.orig_dir / f"{stem}.v").exists():
            print(f"[WARN] 缺 orig/{stem}.v，跳过 {circ}")
            continue
        for k in range(args.copies):
            for sd in seeds:
                view = f"{stem}__identity_d1_s{sd + k * 10}"      # seed 名仅用于区分视图
                modes[view] = link_or_copy(args.orig_dir / f"{stem}.v", vdir / f"{view}.v")
                id_views.append(view)
                id_rows.append({
                    "view_name": view, "circuit": circ, "chain_key": "identity",
                    "family_count": 1, "src_verilog": f"{stem}.v", "dst_verilog": f"{view}.v",
                    "operator_family": "identity", "operator_chain": "identity",
                    "composition_depth": 1, "rule_mode": "identity", "seed": sd + k * 10,
                    "strength": 0.0, "max_rewrites": 0,
                    "edit_count": 0, "gate_expansion": 0, "gate_expansion_ratio": 0.0,
                    "total_added_gates": 0, "successful_rewrite_count": 0,
                    "depth_orig": depth_by.get(circ), "depth_final": depth_by.get(circ),
                    "depth": depth_by.get(circ), "depth_change": 0, "depth_change_ratio": 0.0,
                    "edit_ratio": 0.0, "cec_status": "PASS",
                    "cec_note": "identity control：逐字节等于 orig 网表（sha1 相同），等价性平凡成立，无需 CEC",
                    "freeze_tag": "identity_control_v1"})

    # 2) test 视图：硬链接 d2 的真实变换视图（verilog + mappings）
    mdir = args.out_root / "mappings"
    mdir.mkdir(parents=True, exist_ok=True)
    for v in tests:
        modes[v] = link_or_copy(args.matrix_root / "verilog" / f"{v}.v", vdir / f"{v}.v")
        link_or_copy(args.matrix_root / "mappings" / f"{v}.json", mdir / f"{v}.json")
    test_rows = man[man["view_name"].isin(tests)].to_dict("records")

    # 2b) identity 视图的 mapping：node_alignment 留空 → parser2 的「身份映射」回退会把
    #     同名门自动 1:1 对齐（identity 视图逐字节等于 orig，名字全未变化）。
    for row in id_rows:
        v = row["view_name"]
        (mdir / f"{v}.json").write_text(json.dumps({
            "netlist_id": f"{v}.v", "src_verilog": row["src_verilog"],
            "dst_verilog": f"{v}.v", "operator_family": "identity",
            "operator_chain": ["identity"], "composition_depth": 1, "rule_mode": "identity",
            "seed": row["seed"], "strength": 0.0, "max_rewrites": 0,
            "freeze_tag": "identity_control_v1", "tool_name": "identity_control",
            "tool_version": "1.0.0", "node_alignment": {},
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3) mini matrix 的 manifest（保持与主 manifest 同列）
    full_cols = list(man.columns)
    out_man = pd.concat([pd.DataFrame(id_rows).reindex(columns=full_cols),
                         pd.DataFrame(test_rows).reindex(columns=full_cols)], ignore_index=True)
    out_man.to_csv(args.out_root / "view_manifest_cec.csv", index=False, encoding="utf-8-sig")

    # 4) fold 视图清单（train=identity，test=d2 真实变换）
    def by_circuit(vs):
        d = {}
        for v in vs:
            stem = v.split("__")[0]
            circ = next((c for c, s in STEMS.items() if s == stem), stem)
            d.setdefault(circ, []).append(v)
        return {k: sorted(x) for k, x in sorted(d.items())}

    fj = {"fold": "identity_control", "level": "control", "held_out_operator": "",
          "views_dir": str(vdir), "train_views": sorted(id_views), "test_views": sorted(tests),
          "train_views_by_circuit": by_circuit(id_views),
          "test_views_by_circuit": by_circuit(tests),
          "missing_views": [], "link_modes": modes,
          "note": ("Identity 控制：train = 原网表本身（edit_count=0）× 12/电路（与 d2 的 60 个训练视图、"
                   "每电路 12 个完全对齐），test = d2 的 180 个真实组合变换视图。"
                   "identity 组 AP ≈ G1 ⇒ 增益来自真实变换；≈ 真实变换组 ⇒ 增益只是'多喂视图'。")}
    fdir = args.matrix_root / "folds" / "identity_control"
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "views.json").write_text(json.dumps(fj, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out_root / "README.md").write_text(
        f"# identity_matrix（任务3 控制实验①）\n\n"
        f"- identity 视图：{len(id_views)} 个（5 电路 × {args.copies} 份 × {len(seeds)} seed），"
        f"逐字节等于 `orig/<stem>.v`：`edit_count=0`、`gate_expansion=0`、`depth_change=0`。\n"
        f"- test 视图：{len(tests)} 个（来自 `{args.fold}` 的真实组合变换）。\n"
        f"- fold 清单：`matrix/folds/identity_control/views.json`。\n"
        f"- 构建：`make_dataset.py --matrix-root identity_matrix --orig-dir orig "
        f"--work-dir folds/identity_control --views-list ../matrix/folds/identity_control/views.json "
        f"--fold-json ../matrix/folds/identity_control/views.json --cycle-mode contract --run-parser "
        f"--parser ../data/verilog_data/parser2.py --build-pt`\n"
        f"- 运行：`run_all_folds.py --folds identity_control --amp --tag-suffix _identity --view-budget 4`\n",
        encoding="utf-8")
    print(f"[OK] identity 视图 {len(id_views)} 个（{set(modes.values())}）｜test 视图 {len(tests)} 个")
    print(f"[OK] -> {args.out_root / 'view_manifest_cec.csv'}\n     -> {fdir / 'views.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

