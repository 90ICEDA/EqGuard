#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
freeze_manifest.py — 生成 freeze 清单（数据 / split / 脚本 / 检查点报告 的版本与哈希）

输出：
    matrix/FREEZE_MANIFEST.md   人读清单：输入哈希、目录聚合哈希、检查点结论、复算命令、未完成项
    matrix/freeze_hashes.csv    机器可读：path, kind, bytes, sha1, rows（供后续 diff 校验）

用法（Windows 或 WSL 都能跑，纯 Python）：
    python freeze_manifest.py --root .. --matrix matrix
"""

import argparse
import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def dir_aggregate_sha1(d: Path, pattern: str = "*") -> Tuple[str, int, int]:
    """目录聚合哈希：对 sorted(name sha1) 求哈希；同时返回字节数与文件数。"""
    entries: List[str] = []
    total = 0
    n = 0
    if not d.exists():
        return "", 0, 0
    for p in sorted(d.rglob(pattern)):
        if not p.is_file():
            continue
        entries.append(f"{p.relative_to(d).as_posix()} {sha1_of(p)}")
        total += p.stat().st_size
        n += 1
    return hashlib.sha1("\n".join(entries).encode("utf-8")).hexdigest(), total, n


def count_rows(path: Path) -> Optional[int]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return None
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return sum(1 for _ in csv.DictReader(f))
    except OSError:
        return None


def status_counts(path: Path, col: str = "status") -> Dict[str, int]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            out: Dict[str, int] = {}
            for r in csv.DictReader(f):
                v = str(r.get(col, ""))
                out[v] = out.get(v, 0) + 1
            return out
    except OSError:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 freeze 清单")
    ap.add_argument("--root", type=Path, default=Path(".."), help="项目根（generate_trans 的上级）")
    ap.add_argument("--gen-dir", type=Path, default=None)
    ap.add_argument("--matrix", type=Path, default=None)
    ap.add_argument("--vali-dir", type=Path, default=None)
    ap.add_argument("--skip-view-hash", action="store_true", help="跳过视图网表聚合哈希（更快）")
    args = ap.parse_args()

    root = args.root.resolve()
    gen = (args.gen_dir or (root / "generate_trans")).resolve()
    mat = (args.matrix or (gen / "matrix")).resolve()
    vali = (args.vali_dir or (root.parent / "GraphSAINT-train" / "vali")).resolve()

    rows: List[Dict[str, object]] = []

    def add(path: Path, kind: str) -> None:
        if not path.exists():
            rows.append({"path": str(path), "kind": kind, "exists": 0, "bytes": 0,
                         "sha1": "", "rows": "", "note": "MISSING"})
            return
        rows.append({"path": str(path), "kind": kind, "exists": 1,
                     "bytes": path.stat().st_size, "sha1": sha1_of(path),
                     "rows": count_rows(path) if path.suffix.lower() == ".csv" else "",
                     "note": ""})

    # 输入：生成器侧
    for p in ["rule_expand1.txt", "map.txt", "verilog_lib.v",
              "add_gate_test4.py", "matrix_builder.py", "verify_matrix.py",
              "make_dataset.py", "freeze_manifest.py",
              "make_identity_control.py", "make_view_metadata.py",
              "check_cycle_features.py", "check_dataset_coverage.py",
              "plot_robustness.py", "plot_robustness_compare.py"]:
        add(gen / p, "input")
    for p in sorted((gen / "cec").glob("*.py")):
        add(p, "input")
    # 输入：vali 侧
    for p in ["verilog_lib.v", "sdff_formal_map.v", "config_state_boundary.sby", "pairwise_verify_sb.sh"]:
        add(vali / p, "input_vali")
    # 输入：训练/数据侧
    for p in ["config.yaml", "train_test2.2.py", "train_test2.3.py", "process_pt.py", "process_pt2.py",
              "run_fold_groups.py", "run_all_folds.py", "build_fold_datasets.py",
              "run_budget_sweep.py", "summarize_folds.py", "summarize_loco.py", "summarize_loco_all.py",
              "summarize_seeds.py", "analyze_groups.py", "analyze_identity_control.py",
              "analyze_labelgated_control.py", "analyze_budget_sweep.py",
              "rebuild_groups_macro.py", "make_plots.py", "bench_device.py"]:
        add(root / p, "input_training")
    # 输入：fold 数据集与 fold 规格（10 个 fold）
    for d in sorted((gen / "folds").glob("*/data/processed/dataset_meta.json")):
        add(d, "fold_dataset_meta")
    for d in sorted((gen / "matrix" / "folds").glob("*/views.json")):
        add(d, "fold_spec")
    for p in ["parser1.py", "parser2.py", "parser_trans_test.py"]:
        add(root / "data" / "verilog_data" / p, "input_parser")
    # 数据
    for p in ["data/processed/orig_graph.pt", "data/processed/trans_graph.pt"]:
        add(root / p, "data")
    for p in ["class_map_orig.json", "class_map_trans.json", "role_orig.json", "role_trans.json",
              "alignment.json", "metadata_orig.json", "metadata_trans.json"]:
        add(root / "data" / "verilog_data" / "data" / "for_train" / p, "data")
    # 产物与检查点
    for p in ["view_manifest.csv", "matrix_summary.csv", "circuit_macro_summary.csv",
              "strength_matched_sets.csv", "verification_report.csv", "rule_table_check.csv",
              "mechanism_signature.csv", "verification_summary.txt",
              "view_manifest_cec.csv", "TASK4_REPORT.md"]:
        add(mat / p, "output")
    for p in sorted((mat / "cec").glob("*.csv")):
        add(p, "checkpoint_cec")
    for p in sorted((mat / "split_specs").glob("*.json")):
        add(p, "output")
    add(mat / "folds" / "folds_index.csv", "output")

    # 目录聚合哈希
    agg: Dict[str, Tuple[str, int, int]] = {}
    if not args.skip_view_hash:
        agg["verilog"] = dir_aggregate_sha1(mat / "verilog", "*.v")
        agg["mappings"] = dir_aggregate_sha1(mat / "mappings", "*.json")
        agg["meta"] = dir_aggregate_sha1(mat / "meta", "*.json")
    if (mat / "folds").exists():
        agg["folds"] = dir_aggregate_sha1(mat / "folds", "*.json")

    # 检查点结论
    cec_status = status_counts(mat / "cec" / "cec_results.csv")
    ver_status = status_counts(mat / "verification_report.csv")
    rule_status = status_counts(mat / "rule_table_check.csv")
    neg_path = mat / "cec" / "negative_control_results.csv"
    neg_status = status_counts(neg_path)
    neg_kinds: Dict[str, Dict[str, int]] = {}
    if neg_path.exists():
        with open(neg_path, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                neg_kinds.setdefault(str(r.get("kind")), {})
                neg_kinds[str(r.get("kind"))][str(r.get("status"))] = \
                    neg_kinds[str(r.get("kind"))].get(str(r.get("status")), 0) + 1

    # 机器可读哈希表
    out_csv = mat / "freeze_hashes.csv"
    mat.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "kind", "exists", "bytes", "sha1", "rows", "note"])
        w.writeheader()
        w.writerows(rows)
        for name in sorted(agg):
            h, b, n = agg[name]
            w.writerow({"path": f"matrix/{name}", "kind": f"agg_{name}", "exists": 1,
                        "bytes": b, "sha1": h, "rows": n, "note": f"aggregate of {n} files"})
    write_markdown(mat, root, gen, vali, rows, agg, cec_status, ver_status, rule_status,
                   neg_status, neg_kinds)
    print(f"[OK] {mat / 'FREEZE_MANIFEST.md'}")
    print(f"[OK] {out_csv}")
    print(f"     CEC={cec_status} 预门禁={ver_status} 规则={rule_status} 负对照/复核={neg_status}")
    return 0


def write_markdown(mat: Path, root: Path, gen: Path, vali: Path,
                   rows: List[Dict[str, object]], agg: Dict[str, Tuple[str, int, int]],
                   cec_status: Dict[str, int], ver_status: Dict[str, int],
                   rule_status: Dict[str, int], neg_status: Dict[str, int],
                   neg_kinds: Dict[str, Dict[str, int]]) -> None:
    md: List[str] = []
    md.append("# FREEZE MANIFEST — 分任务4 数据/脚本/检查点冻结清单\n")
    md.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    md.append(f"项目根 `{root}` ｜ generate_trans `{gen}` ｜ vali `{vali}`\n")

    md.append("## 1. 输入与哈希（其中任何一项改动都应视为需要重新冻结）\n")
    md.append("| 文件 | 类别 | 字节 | SHA1(前16) | 行数 |")
    md.append("|---|---|---|---|---|")
    for r in rows:
        if str(r["kind"]).startswith("input") or r["kind"] == "data":
            md.append(f"| `{Path(str(r['path'])).name}` | {r['kind']} | {r['bytes']} | "
                      f"`{str(r['sha1'])[:16]}` | {r['rows']} |")

    md.append("\n## 2. 目录聚合哈希（检测视图集合/对齐文件是否被改动）\n")
    md.append("| 目录 | 文件数 | 字节 | 聚合 SHA1 |")
    md.append("|---|---|---|---|")
    for name in sorted(agg):
        h, b, n = agg[name]
        md.append(f"| `matrix/{name}` | {n} | {b} | `{h}` |")

    md.append("\n## 3. 检查点报告与结论\n")
    md.append("| 检查点 | 文件 | 行数 | 结论 |")
    md.append("|---|---|---|---|")
    md.append(f"| 规则库 truth-table CEC | `matrix/rule_table_check.csv` | "
              f"{count_rows(mat / 'rule_table_check.csv')} | {rule_status} |")
    md.append(f"| 视图预门禁（结构/溯源/机制/强度） | `matrix/verification_report.csv` | "
              f"{count_rows(mat / 'verification_report.csv')} | {ver_status} |")
    md.append(f"| 真·等价性 CEC（state-boundary） | `matrix/cec/cec_results.csv` | "
              f"{count_rows(mat / 'cec' / 'cec_results.csv')} | {cec_status} |")
    md.append(f"| CEC chain×depth 汇总 | `matrix/cec/cec_summary.csv` | "
              f"{count_rows(mat / 'cec' / 'cec_summary.csv')} | — |")
    md.append(f"| CEC 并回 manifest | `matrix/view_manifest_cec.csv` | "
              f"{count_rows(mat / 'view_manifest_cec.csv')} | 含 `cec_status` 列 |")
    md.append(f"| 负对照 + 旧数据复核 | `matrix/cec/negative_control_results.csv` | "
              f"{count_rows(mat / 'cec' / 'negative_control_results.csv')} | {neg_status} |")
    if neg_kinds:
        md.append("")
        md.append("负对照明细（期望：`neg_mutant` 全 FAIL、`legacy_equiv` 全 PASS）：\n")
        md.append("| kind | 结果 |")
        md.append("|---|---|")
        for k in sorted(neg_kinds):
            md.append(f"| {k} | {neg_kinds[k]} |")

    md.append("\n## 4. 复算命令\n")
    md.append("```bash")
    md.append("# (1) matrix 生成 + 自检（Windows/WSL 均可）")
    md.append("python matrix_builder.py --lib verilog_lib.v --map map.txt --rules rule_expand1.txt \\")
    md.append("  --seeds 42,43,44 --depths 1,2,3 --max-rewrites 50 --rule-mode partitioned \\")
    md.append("  --strength-bins 5 --freeze-tag task4_matrix_v1.0.0 --skip-existing --materialize-folds")
    md.append("python verify_matrix.py --lib verilog_lib.v --map map.txt --rules rule_expand1.txt \\")
    md.append("  --orig-dir orig --matrix-root matrix          # 期望 ALL PASS")
    md.append("")
    md.append("# (2) CEC（Linux/WSL，yosys 0.51）")
    md.append("python3 cec/matrix_cec.py --matrix-root matrix --orig-dir orig \\")
    md.append("  --vali-dir ../../../GraphSAINT-train/vali --out matrix/cec \\")
    md.append("  --log-dir ~/cec_logs --jobs 8 --emit-json-regex _d1_ --timeout 1800 --resume")
    md.append("python3 cec/join_cec.py --matrix-root matrix")
    md.append("python3 cec/negative_control.py --vali-dir ../../../GraphSAINT-train/vali \\")
    md.append("  --legacy-trans-dir ../../data/verilog_data/trans --legacy-orig-dir ../orig \\")
    md.append("  --out matrix/cec/negative_control_results.csv --jobs 4")
    md.append("")
    md.append("# (3) 重新生成本清单")
    md.append("python freeze_manifest.py --root .. --matrix matrix")
    md.append("```")

    md.append("\n## 5. 进度（v1.2 · 2026-09-26）\n")
    md.append("**已完成**：\n")
    md.append("- 任务4 矩阵本体 + 真·等价性 CEC（600/600 PASS；负对照 7 个非等价变异体正确 FAIL）；"
              "CEC 比较点分类已有**机器可读表** `cec/comparison_point_stats.csv`（63 视图）与"
              "**日志索引** `cec/log_index.csv`（WSL 1,222 文件 / 1.43 GB）。")
    md.append("- 任务1：label-free provenance + 独立 label transport + 组合环特征（`--cycle-mode contract`，39 维）"
              "+ Prediction-Hard 的 fold 内合法实现（`--view-policy pred_hard`）。")
    md.append("- 任务4 泛化实验：**10 个 fold × 4 组 × 3 seed = 120 次运行**（GPU + bf16-AMP）；"
              "AP 增益 10/10 fold 全为正（跨 fold +0.0442/+0.0483/+0.0617）。")
    md.append("- 任务2：ORIG/TRANS 两侧指标 + 旧形态 `loco_summary.csv` + d2 的 LOCO + 10 fold 两侧汇总。")
    md.append("- 任务3 控制①（Identity）：AP 增益主要来自 trans 侧训练本身，一致性指标才依赖真实变换。")
    md.append("- 任务3 控制②（Label-agnostic）：**通过** —— 血缘只差 3/969,181 对（0.0003%）；"
              "4 组 × 3 seed 的 3-seed 聚合 |ΔAP| ≤ 0.0011 < 同配置跑间噪声 0.0020。")
    md.append("- 视图预算扫描（budget 1/2/4/8 × 4 组 × 3 seed = 48 次运行）：增益随预算上升、budget 4→8 饱和；"
              "G4 只在紧预算下领先；一致性项需 ≥2 视图。")
    md.append("- 论文图链路：`make_view_metadata.py` + `plot_robustness*.py --runs-glob` + `make_plots.py`"
              "（`results/figures/<fold>/`，60 张图 + 同名 csv）。")
    md.append("\n**未完成**：\n")
    md.append("- 任务3 控制③（AIG normalization）：ABC/yosys 与门库均已就绪，阻塞点是**归一化破坏逐门血缘**"
              "（需先做「导线级溯源」+ CEC 复核），方案见 `GIN_train/TASK4_D2_GROUPS_REPORT.md` §11。")
    md.append("- LOCO 仅覆盖 `single_to_composed_d2`；其余 9 个 fold 的 LOCO 未跑。")
    md.append("- 5 seed 的正式表（当前 3 seed）。")
    md.append("- 历史结果 CSV 的 AP 命名统一（`PR-AUC_*` → `AP_*`）；旧数据链路已废弃（历史结果原样保留）。")
    md.append("- 任务1：`parser2.py` 的 label-free provenance 改造、Prediction-Hard 的 fold 内合法实现、"
              "历史结果 CSV 的 AP 命名统一，均未开始。")
    md.append("- 任务2：`results/` 中无 `trainv0.13*`（2.2/2.3 从未跑过）；Anchor AP、Recall@1/2/5% 列缺失。")
    md.append("- 任务3：Identity / Label-agnostic rewrite / AIG normalization 三个 control 未实现。")
    md.append("- CEC 比较点分类仅覆盖 63/600 视图（depth-1 + smoke），其余视图有 CEC PASS 但无 PO/nextD 分类。")
    md.append("- 原始 CEC 日志在 WSL `~/cec_logs`（约 1.4GB，不在项目内）；如需随项目冻结请用 `--log-dir` 指向项目。")

    (mat / "FREEZE_MANIFEST.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())


