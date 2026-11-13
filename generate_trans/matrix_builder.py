#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
matrix_builder.py — 分任务4：把 rewrite 做成真正的 transformation matrix

核心约定（与总任务一致）：
  - tr42/tr43/tr44 只是同一个算子的不同 seed，不再当作不同 operator；
  - operator family 至少 4 种、机制互不相同：decomp / balance / refactor / resub；
  - 先各自单独跑（composition_depth=1），再做组合（depth=1/2/3）；
  - 每个 view 记录 edit_count / gate_expansion / depth_change，并给出“强度匹配”的可比子集；
  - 额外给出两族泛化 split：held-out operator、single-step → composed。

产出（默认 <out-root> = generate_trans/matrix）：
  verilog/<view>.v            视图网表（label-blind）
  mappings/<view>.json        节点对齐 src→dst
  meta/<view>.json            单 view 完整元数据（含逐条 edit 记录，供等价自检复算）
  view_manifest.csv           view 级 manifest（含全部 view 级指标）
  matrix_summary.csv          按 (circuit, chain, composition_depth) 聚合
  circuit_macro_summary.csv   先按 circuit 求均值、再对 circuit 做 macro 平均（views 不当独立样本）
  strength_matched_sets.csv   跨 chain 的 transformation strength 匹配子集
  split_specs/*.json          泛化划分（held-out operator / single→composed）
  folds/<fold>/views.json     （--materialize-folds 时）每个 fold 的视图清单与 fold 配置模板

用法示例：
  python matrix_builder.py --lib verilog_lib.v --map map.txt --rules rule_expand1.txt \
      --circuits rs232t1000,s15850t100,s35932t200,s38417t300,s38584t100 \
      --seeds 42,43,44 --depths 1,2,3 --max-rewrites 50 --rule-mode partitioned \
      --freeze-tag matrix_v1.0.0
"""

import argparse
import csv
import itertools
import json
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from add_gate_test4 import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    VIEW_METADATA_FIELDS,
    RewriteLimits,
    build_operator,
    build_view_metadata_row,
    emit_verilog,
    file_sha1,
    load_py_dict_from_file,
    netlist_stats,
    parse_gatelevel_verilog,
    parse_lib_info,
)

FAMILIES_DEFAULT = ["decomp", "balance", "refactor", "resub"]
#: 按机制归因用的展示顺序（摘要表）
FAMILY_ORDER = ["decomp", "balance", "refactor", "resub"]

MANIFEST_FIELDS = ["view_file", "circuit", "chain_key", "family_count"] + VIEW_METADATA_FIELDS


def log(msg: str) -> None:
    print(msg, flush=True)


# ------------------------------------------------------------
# 参数
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="分任务4：transformation matrix 生成器")
    ap.add_argument("--lib", required=True, help="verilog_lib.v")
    ap.add_argument("--map", required=True, help="map.txt (gate_simplification)")
    ap.add_argument("--rules", required=True, help="rule_expand1.txt (gate_equivalences)")
    ap.add_argument("--orig-dir", type=Path, default=Path("orig"), help="原始网表目录")
    ap.add_argument("--out-root", type=Path, default=Path("matrix"), help="矩阵输出根目录")
    ap.add_argument("--circuits", type=str, default="rs232t1000,s15850t100,s35932t200,s38417t300,s38584t100",
                    help="参与生成矩阵的电路（orig/ 下的文件名，不含 .v），逗号分隔；all=orig 下全部")
    ap.add_argument("--families", type=str, default=",".join(FAMILIES_DEFAULT),
                    help="算子家族列表，逗号分隔")
    ap.add_argument("--seeds", type=str, default="42,43,44", help="随机种子列表，逗号分隔")
    ap.add_argument("--depths", type=str, default="1,2,3", help="组合层数列表，逗号分隔（1=单算子）")
    ap.add_argument("--max-rewrites", type=int, default=50, help="每步重写预算（单算子即为总预算）")
    ap.add_argument("--step-budgets", type=str, default="",
                    help="组合变换每步预算（逗号分隔）；缺省则每步都用 --max-rewrites")
    ap.add_argument("--strength", type=float, default=1.0, help="每个候选门被重写的概率 (0..1]")
    ap.add_argument("--rule-mode", type=str, default="partitioned", choices=["partitioned", "legacy"],
                    help="规则空间；矩阵实验用 partitioned（机制纯净），legacy 仅用于复现旧视图")
    ap.add_argument("--max-chains", type=int, default=0,
                    help="每层最多生成多少条 chain（0=枚举全部排列）")
    ap.add_argument("--allow-repeats", action="store_true", help="允许 chain 内重复出现同一家族")
    ap.add_argument("--strength-bins", type=int, default=5, help="强度匹配的分箱数")
    ap.add_argument("--materialize-folds", action="store_true",
                    help="把每个 fold 的视图复制到 folds/<fold>/views/ 并写出 fold 配置模板")
    ap.add_argument("--freeze-tag", type=str, default="", help="freeze 标签（写入 manifest/meta）")
    ap.add_argument("--skip-existing", action="store_true", help="若 verilog 已存在则跳过生成")
    ap.add_argument("--limit-views", type=int, default=0, help="调试用：最多生成 view 数（0=不限）")
    return ap.parse_args()


# ------------------------------------------------------------
# 视图命名 / chain 枚举
# ------------------------------------------------------------

def circuit_base(stem: str) -> str:
    """'rs232t1000' -> 'rs232'；'s38584t100' -> 's38584'。"""
    m = re.match(r"^(?P<base>.+?)t\d+$", str(stem))
    return m.group("base") if m else str(stem)


def make_view_name(stem: str, chain: Sequence[str], seed: int) -> str:
    """命名必须保持“电路前缀”可解析，便于下游按前缀划分视图。"""
    return f"{stem}__{'-'.join(chain)}_d{len(chain)}_s{seed}"


def enumerate_chains(families: Sequence[str], depth: int, allow_repeats: bool,
                     max_chains: int, seed: int) -> List[Tuple[str, ...]]:
    """枚举指定层数的算子链；条数超过上限时按确定性随机抽样。"""
    if depth <= 1:
        return [(f,) for f in families]
    if allow_repeats:
        chains = [tuple(c) for c in itertools.product(families, repeat=depth)]
    else:
        chains = [tuple(c) for c in itertools.permutations(families, depth)]
    if max_chains and len(chains) > max_chains:
        import random as _random
        rng = _random.Random(seed * 7919 + depth)
        chains = sorted(rng.sample(chains, max_chains))
    return chains


# ------------------------------------------------------------
# 输入加载
# ------------------------------------------------------------

def load_inputs(args: argparse.Namespace):
    lib_text = Path(args.lib).read_text(encoding="utf-8", errors="ignore")
    lib_ports, lib_outs, lib_ins = parse_lib_info(lib_text)
    gate_simplification = load_py_dict_from_file(Path(args.map), "gate_simplification")
    gate_equivalences = load_py_dict_from_file(Path(args.rules), "gate_equivalences")
    return lib_ports, lib_outs, lib_ins, gate_simplification, gate_equivalences


def resolve_circuits(args: argparse.Namespace) -> List[str]:
    if args.circuits.strip().lower() == "all":
        return sorted(p.stem for p in Path(args.orig_dir).glob("*.v"))
    return [c.strip() for c in args.circuits.split(",") if c.strip()]


def edits_by_step(edits: List[Dict[str, object]]) -> Dict[str, Dict[str, int]]:
    """按 (步序, 算子) 统计 edit 数与 gate 增量（组合变换的逐步归因）。"""
    out: Dict[str, Dict[str, int]] = {}
    for rec in edits:
        key = f"step{rec.get('步序', 1)}_{rec.get('算子', rec.get('规则家族', 'unknown'))}"
        slot = out.setdefault(key, {"edit_count": 0, "gate_delta": 0})
        slot["edit_count"] += 1
        ratio = str(rec.get("变换比例", "1:1"))
        m = re.match(r"^1:(\d+)", ratio)
        if m:
            slot["gate_delta"] += int(m.group(1)) - 1
        elif ratio.startswith("1:0"):
            slot["gate_delta"] -= 1
    return out


# ------------------------------------------------------------
# 单 view 生成
# ------------------------------------------------------------

def build_one_view(*, args, stem, chain, seed, lib_ports, lib_outs, lib_ins,
                   gate_simplification, gate_equivalences, timescale, orig_mod,
                   view_name, verilog_path, mapping_path, meta_path,
                   lib_sha1, map_sha1, rules_sha1) -> Dict[str, object]:
    """生成单个 view（网表 + mapping + meta），返回 manifest 行。"""
    if len(chain) > 1:
        operator = build_operator(
            "compose", lib_ports=lib_ports, lib_outs=lib_outs, lib_ins=lib_ins,
            gate_simplification=gate_simplification, gate_equivalences=gate_equivalences,
            seed=seed, chain=list(chain), step_budgets=args._step_budgets,
            rule_mode=args.rule_mode,
        )
    else:
        operator = build_operator(
            chain[0], lib_ports=lib_ports, lib_outs=lib_outs, lib_ins=lib_ins,
            gate_simplification=gate_simplification, gate_equivalences=gate_equivalences,
            seed=seed, rule_mode=args.rule_mode,
        )

    orig_stats = netlist_stats(orig_mod, lib_ports, lib_outs, gate_simplification)
    limits = RewriteLimits(strength=float(args.strength), max_rewrites=int(args.max_rewrites))
    out_mod, stats, alignment = operator.apply(orig_mod, limits)
    out_stats = netlist_stats(out_mod, lib_ports, lib_outs, gate_simplification)
    out_mod.name = f"{orig_mod.name}_{view_name.replace('-', '_')}"

    verilog_text = emit_verilog(timescale, out_mod, lib_ports)
    verilog_path.parent.mkdir(parents=True, exist_ok=True)
    verilog_path.write_text(verilog_text, encoding="utf-8")

    mapping_payload = {
        "netlist_id": verilog_path.name,
        "src_verilog": f"{stem}.v",
        "dst_verilog": verilog_path.name,
        "operator_family": (chain[0] if len(chain) == 1 else "compose"),
        "operator_chain": list(chain),
        "composition_depth": len(chain),
        "rule_mode": args.rule_mode,
        "seed": seed,
        "strength": args.strength,
        "max_rewrites": args.max_rewrites,
        "freeze_tag": args.freeze_tag,
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "lib_sha1": lib_sha1,
        "map_sha1": map_sha1,
        "rules_sha1": rules_sha1,
        "node_alignment": alignment,
    }
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping_payload, f, indent=4, ensure_ascii=False)

    row = build_view_metadata_row(
        view_name=view_name,
        src_verilog=f"{stem}.v",
        dst_verilog=verilog_path.name,
        operator_family=(chain[0] if len(chain) == 1 else "compose"),
        operator_chain=list(chain),
        seed=seed,
        strength=args.strength,
        max_rewrites=args.max_rewrites,
        orig_stats=orig_stats,
        out_stats=out_stats,
        stats=stats,
        rule_mode=args.rule_mode,
        step_records=getattr(operator, "step_records", None),
        freeze_tag=args.freeze_tag,
        lib_sha1=lib_sha1,
        map_sha1=map_sha1,
        rules_sha1=rules_sha1,
    )
    row["circuit"] = circuit_base(stem)
    row["chain_key"] = "-".join(chain)
    row["family_count"] = len(set(chain))
    row["view_file"] = verilog_path.name
    row["orig_source"] = f"{stem}.v"

    meta_payload = dict(row)
    edits = list(getattr(stats, "csv_records", []) or [])
    meta_payload["edits"] = edits
    meta_payload["edits_by_step"] = edits_by_step(edits)
    meta_payload["node_alignment"] = alignment
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2, ensure_ascii=False)

    return row


# ------------------------------------------------------------
# 变换强度匹配 / 汇总
# ------------------------------------------------------------

STRENGTH_METRICS = ["edit_count", "edit_ratio", "gate_expansion", "gate_expansion_ratio",
                    "depth_change", "depth_change_ratio", "final_gate_count", "strength_score"]


def pct_rank(values: List[float]) -> List[float]:
    """0..1 百分位（并列取平均秩）。"""
    n = len(values)
    if n <= 1:
        return [0.5] * n
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg / (n - 1)
        i = j + 1
    return ranks


def add_strength_scores(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    在每个 (circuit, composition_depth) 组内计算综合变换强度：
        strength_score = 0.5*pct(edit_ratio) + 0.25*pct(gate_expansion_ratio)
                         + 0.25*pct(|depth_change_ratio|)
    之后才能在同一强度水平上比较不同 mechanism 的视图。
    """
    groups: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
    for r in rows:
        groups.setdefault((str(r["circuit"]), int(r["composition_depth"])), []).append(r)
    for _, rs in groups.items():
        er = pct_rank([float(r.get("edit_ratio", 0.0)) for r in rs])
        gr = pct_rank([float(r.get("gate_expansion_ratio", 0.0)) for r in rs])
        dr = pct_rank([abs(float(r.get("depth_change_ratio", 0.0))) for r in rs])
        for r, a, b, c in zip(rs, er, gr, dr):
            r["strength_score"] = round(0.5 * a + 0.25 * b + 0.25 * c, 6)
    return rows


def _mean(xs: List[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (r.get(k) if r.get(k) is not None else "") for k in fields})


def write_summaries(rows: List[Dict[str, object]], out_root: Path
                    ) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """写出 (circuit, chain) 级汇总与 circuit-level macro 汇总。"""
    grouped: Dict[Tuple[str, str, int], List[Dict[str, object]]] = {}
    for r in rows:
        grouped.setdefault((str(r["circuit"]), str(r["chain_key"]), int(r["composition_depth"])), []).append(r)
    summary_rows: List[Dict[str, object]] = []
    for (circ, chain, dep), rs in sorted(grouped.items()):
        row: Dict[str, object] = {
            "circuit": circ, "chain_key": chain, "composition_depth": dep,
            "n_views": len(rs),
            "n_seeds": len(set(int(r["seed"]) for r in rs)),
        }
        for m in STRENGTH_METRICS:
            row[f"{m}_mean"] = round(_mean([float(r.get(m, 0.0)) for r in rs]), 6)
        summary_rows.append(row)

    # circuit-level macro：先按 circuit 求均值，再对 circuit 求平均（不把 views 当独立样本）
    macro_groups: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
    for r in summary_rows:
        macro_groups.setdefault((str(r["chain_key"]), int(r["composition_depth"])), []).append(r)
    macro_rows: List[Dict[str, object]] = []
    for (chain, dep), rs in sorted(macro_groups.items()):
        row = {
            "chain_key": chain, "composition_depth": dep,
            "n_circuits": len(rs),
            "n_views_total": int(sum(int(r["n_views"]) for r in rs)),
        }
        for m in STRENGTH_METRICS:
            row[f"{m}_macro"] = round(_mean([float(r.get(f"{m}_mean", 0.0)) for r in rs]), 6)
        macro_rows.append(row)

    _write_csv(out_root / "matrix_summary.csv", summary_rows)
    _write_csv(out_root / "circuit_macro_summary.csv", macro_rows)
    return summary_rows, macro_rows


def write_strength_matched_sets(rows: List[Dict[str, object]], out_root: Path,
                                bins: int) -> List[Dict[str, object]]:
    """
    按 (circuit, composition_depth) 分组、按 strength_score 等频分箱；每个箱里每个 chain
    取最接近箱中心的视图，形成“变换强度匹配”的跨 mechanism 可比子集。
    """
    if bins < 2:
        bins = 2
    groups: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
    for r in rows:
        groups.setdefault((str(r["circuit"]), int(r["composition_depth"])), []).append(r)

    matched: List[Dict[str, object]] = []
    for (circ, dep), rs in sorted(groups.items()):
        scores = sorted(float(r["strength_score"]) for r in rs)
        edges = [scores[min(len(scores) - 1, int(i * len(scores) / bins))] for i in range(bins + 1)]
        for bi in range(bins):
            lo, hi = edges[bi], edges[bi + 1]
            center = 0.5 * (lo + hi)
            bucket = [r for r in rs if (lo - 1e-9) <= float(r["strength_score"]) <= (hi + 1e-9)]
            by_chain: Dict[str, Dict[str, object]] = {}
            for r in bucket:
                ck = str(r["chain_key"])
                if ck not in by_chain or abs(float(r["strength_score"]) - center) < abs(
                        float(by_chain[ck]["strength_score"]) - center):
                    by_chain[ck] = r
            if len(by_chain) < 2:
                continue
            set_id = f"{circ}_d{dep}_bin{bi}"
            for ck, r in sorted(by_chain.items()):
                matched.append({
                    "matched_set_id": set_id,
                    "circuit": circ,
                    "composition_depth": dep,
                    "strength_bin": bi,
                    "strength_bin_range": f"[{round(lo, 4)}, {round(hi, 4)}]",
                    "strength_score": r["strength_score"],
                    "chain_key": ck,
                    "view_name": r["view_name"],
                    "dst_verilog": r["dst_verilog"],
                    "seed": r["seed"],
                    "edit_count": r["edit_count"],
                    "edit_ratio": r["edit_ratio"],
                    "gate_expansion": r["gate_expansion"],
                    "gate_expansion_ratio": r["gate_expansion_ratio"],
                    "depth_change": r["depth_change"],
                    "depth_change_ratio": r["depth_change_ratio"],
                })
    matched.sort(key=lambda d: (d["circuit"], d["composition_depth"], d["strength_bin"], d["chain_key"]))
    _write_csv(out_root / "strength_matched_sets.csv", matched)
    return matched


# ------------------------------------------------------------
# 泛化划分（held-out operator / single-step → composed）
# ------------------------------------------------------------

def _fold(name: str, level: str, held_out: str,
          train_rows: List[Dict[str, object]], test_rows: List[Dict[str, object]],
          note: str = "") -> Dict[str, object]:
    def by_circuit(rs: List[Dict[str, object]]) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for r in rs:
            out.setdefault(str(r["circuit"]), []).append(str(r["view_name"]))
        return {k: sorted(v) for k, v in sorted(out.items())}

    return {
        "fold": name,
        "level": level,
        "held_out_operator": held_out,
        "train_views": sorted(str(r["view_name"]) for r in train_rows),
        "test_views": sorted(str(r["view_name"]) for r in test_rows),
        "train_views_by_circuit": by_circuit(train_rows),
        "test_views_by_circuit": by_circuit(test_rows),
        "circuits": sorted(set(str(r["circuit"]) for r in test_rows)),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "note": note,
    }


def _spec(name: str, description: str, folds: List[Dict[str, object]],
          freeze: Dict[str, object]) -> Dict[str, object]:
    return {
        "name": name,
        "description": description,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "freeze": freeze,
        "folds": folds,
    }


def build_split_specs(rows: List[Dict[str, object]], families: Sequence[str],
                      freeze: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    """
    两族泛化实验的 train/test 视图划分：
      1) held-out operator（单步）：train=其余 family 的单步视图，test=留出 family 的单步视图；
      2) held-out operator（组合）：train=链条中不含该 family 的组合视图，test=链条中含该 family 的组合视图；
      3) single-step → composed：train=全部单步视图，test=深度 d（d>=2）的组合视图。
    所有划分都保留 circuit 维度，便于下游做 circuit-level macro 平均。
    """
    single = [r for r in rows if int(r["composition_depth"]) == 1]
    composed = [r for r in rows if int(r["composition_depth"]) > 1]
    specs: Dict[str, Dict[str, object]] = {}

    folds: List[Dict[str, object]] = []
    for f in families:
        tr = [r for r in single if str(r["chain_key"]) != f]
        te = [r for r in single if str(r["chain_key"]) == f]
        folds.append(_fold(f"heldout_single_{f}", "single_step", f, tr, te,
                           "train=其余 operator family 的单步视图；test=被留出的 operator（跨算子泛化）"))
    specs["heldout_operator_single"] = _spec(
        "heldout_operator_single", "held-out operator（单步视图）", folds, freeze)

    folds = []
    for f in families:
        tr = [r for r in composed if f not in str(r["chain_key"]).split("-")]
        te = [r for r in composed if f in str(r["chain_key"]).split("-")]
        if not te:
            continue
        folds.append(_fold(f"heldout_composed_{f}", "composed", f, tr, te,
                           "train=链条中不含该算子的组合视图；test=链条中含该算子的组合视图"))
    specs["heldout_operator_composed"] = _spec(
        "heldout_operator_composed", "held-out operator（组合视图）", folds, freeze)

    for d in sorted({int(r["composition_depth"]) for r in composed}):
        if d < 2:
            continue
        te = [r for r in composed if int(r["composition_depth"]) == d]
        folds = [_fold(f"single_to_composed_d{d}", "single_to_composed", "", single, te,
                       f"train=全部单步视图；test=深度 {d} 的组合视图（单步→组合泛化）")]
        specs[f"single_to_composed_d{d}"] = _spec(
            f"single_to_composed_d{d}", f"single-step → composed(depth={d})", folds, freeze)
    return specs


def _link_or_copy(src: Path, dst: Path) -> str:
    """优先硬链接（省磁盘；视图生成后不再改动），失败再复制。"""
    if dst.exists():
        return "exists"
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def materialize_folds(specs: Dict[str, Dict[str, object]], verilog_dir: Path,
                      folds_root: Path) -> List[Dict[str, object]]:
    """
    把每个 fold 的视图链接/复制到 folds/<fold>/views/，并写出 fold_config.yaml 模板。
    这样下游图构建/训练只要指向该目录，就能严格按 fold 的视图集合训练与测试
    （不需要修改现有训练脚本的视图选择逻辑）。
    """
    summary: List[Dict[str, object]] = []
    for spec in specs.values():
        for fold in spec["folds"]:
            fold_dir = folds_root / str(fold["fold"])
            views_dir = fold_dir / "views"
            views_dir.mkdir(parents=True, exist_ok=True)
            missing: List[str] = []
            modes: Dict[str, int] = defaultdict(int)
            for v in list(fold["train_views"]) + list(fold["test_views"]):
                src = verilog_dir / f"{v}.v"
                if src.exists():
                    modes[_link_or_copy(src, views_dir / src.name)] += 1
                else:
                    missing.append(v)
            payload = {
                "fold": fold["fold"],
                "level": fold["level"],
                "held_out_operator": fold["held_out_operator"],
                "views_dir": str(views_dir),
                "train_views": fold["train_views"],
                "test_views": fold["test_views"],
                "train_views_by_circuit": fold["train_views_by_circuit"],
                "test_views_by_circuit": fold["test_views_by_circuit"],
                "missing_views": missing,
                "link_modes": dict(modes),
                "note": fold["note"],
            }
            with open(fold_dir / "views.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            cfg = (
                "# 该 fold 的视图清单（由 matrix_builder.py --materialize-folds 生成）\n"
                f"fold: {fold['fold']}\n"
                f"level: {fold['level']}\n"
                f"held_out_operator: {fold['held_out_operator'] or 'null'}\n"
                f"views_dir: {views_dir.as_posix()}\n"
                f"n_train_views: {fold['n_train']}\n"
                f"n_test_views: {fold['n_test']}\n"
                "# 下游用法：用该 views_dir 作为只看得到这些视图的 trans 目录做图构建，\n"
                "# 再把结果图的 data.trans_path 指给现有训练脚本（config.yaml -> data.trans_path）。\n"
                "training_note: train/test 的节点只来自上面列出的视图，禁止把 test 视图放进训练\n"
            )
            (fold_dir / "fold_config.yaml").write_text(cfg, encoding="utf-8")
            summary.append({
                "fold": fold["fold"], "level": fold["level"],
                "held_out_operator": fold["held_out_operator"],
                "n_train": fold["n_train"], "n_test": fold["n_test"],
                "views_dir": str(views_dir), "missing_views": len(missing),
                "hardlinks": int(modes.get("hardlink", 0)), "copies": int(modes.get("copy", 0)),
            })
    _write_csv(folds_root / "folds_index.csv", summary)
    return summary


def write_manifest(rows: List[Dict[str, object]], out_root: Path) -> None:
    """view_manifest.csv：列顺序固定（先 MANIFEST_FIELDS，再其余扩展列）。"""
    fields = list(MANIFEST_FIELDS)
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    path = out_root / "view_manifest.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (r.get(k) if r.get(k) is not None else "") for k in fields})
    log(f"[OK] view manifest: {path}  (n_views={len(rows)})")


# ------------------------------------------------------------
# 控制台摘要
# ------------------------------------------------------------

def print_summary(macro_rows, matched, specs, fold_idx, rows, out_root: Path, elapsed: float) -> None:
    log("\n" + "=" * 82)
    log("[Layer-1] 单步（depth=1）各 mechanism 的 circuit-macro 指标（views 不当独立样本）")
    log("=" * 82)
    log(f"{'chain':<26}{'n_circ':>7}{'edit':>8}{'edit_ratio':>12}{'gate_exp':>10}{'depth_chg':>11}")
    for r in macro_rows:
        if int(r["composition_depth"]) != 1:
            continue
        log(f"{str(r['chain_key']):<26}{int(r['n_circuits']):>7}"
            f"{float(r['edit_count_macro']):>8.1f}{float(r['edit_ratio_macro']):>12.4f}"
            f"{float(r['gate_expansion_macro']):>10.1f}{float(r['depth_change_macro']):>11.2f}")

    log("\n" + "=" * 82)
    log("[Layer-2] 组合变换（depth>=2）")
    log("=" * 82)
    for dep in sorted({int(r["composition_depth"]) for r in macro_rows if int(r["composition_depth"]) > 1}):
        sub = [r for r in macro_rows if int(r["composition_depth"]) == dep]
        log(f"  depth={dep}: chains={len(sub)}  "
            f"edit_mean={_mean([float(r['edit_count_macro']) for r in sub]):.1f}  "
            f"gate_exp_mean={_mean([float(r['gate_expansion_macro']) for r in sub]):.1f}  "
            f"depth_chg_mean={_mean([float(r['depth_change_macro']) for r in sub]):.2f}")

    log("\n" + "=" * 82)
    log("[Layer-3] 强度匹配子集 / 泛化划分")
    log("=" * 82)
    log(f"  strength_matched_sets: {len(matched)} 行, "
        f"matched_set 数={len(set(str(m['matched_set_id']) for m in matched))}")
    for name, payload in specs.items():
        for fold in payload["folds"]:
            log(f"  {name}/{fold['fold']}: train={fold['n_train']} test={fold['n_test']}")
    if fold_idx:
        log(f"  folds 物化: {len(fold_idx)} 个（folds/<fold>/views/ + views.json + fold_config.yaml）")

    n_by_depth: Dict[int, int] = {}
    for r in rows:
        d = int(r["composition_depth"])
        n_by_depth[d] = n_by_depth.get(d, 0) + 1
    log(f"\n[DONE] 共 {len(rows)} 个视图 {dict(sorted(n_by_depth.items()))}，"
        f"用时 {elapsed:.1f}s，输出根目录: {out_root}")


# ------------------------------------------------------------
# main
# ------------------------------------------------------------

def main() -> int:
    args = parse_args()
    t0 = time.time()
    out_root = Path(args.out_root)
    verilog_dir = out_root / "verilog"
    mappings_dir = out_root / "mappings"
    meta_dir = out_root / "meta"
    specs_dir = out_root / "split_specs"
    folds_root = out_root / "folds"
    for d in (verilog_dir, mappings_dir, meta_dir, specs_dir):
        d.mkdir(parents=True, exist_ok=True)

    families = [f.strip() for f in args.families.split(",") if f.strip()]
    if not families:
        raise ValueError("--families 不能为空")
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    depths = sorted({int(d) for d in args.depths.split(",") if d.strip()}) or [1]
    args._step_budgets = [int(x) for x in args.step_budgets.split(",") if x.strip()] or None

    lib_ports, lib_outs, lib_ins, gate_simplification, gate_equivalences = load_inputs(args)
    lib_sha1 = file_sha1(args.lib)
    map_sha1 = file_sha1(args.map)
    rules_sha1 = file_sha1(args.rules)
    freeze = {
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "freeze_tag": args.freeze_tag,
        "rule_mode": args.rule_mode,
        "families": families,
        "seeds": seeds,
        "depths": depths,
        "max_rewrites": args.max_rewrites,
        "step_budgets": args._step_budgets,
        "strength": args.strength,
        "lib_sha1": lib_sha1,
        "map_sha1": map_sha1,
        "rules_sha1": rules_sha1,
    }
    log(f"[INFO] {TOOL_NAME} v{TOOL_VERSION} | rule_mode={args.rule_mode} | "
        f"families={families} seeds={seeds} depths={depths} max_rewrites={args.max_rewrites}")

    circuits = resolve_circuits(args)
    log(f"[INFO] circuits ({len(circuits)}): {circuits}")

    rows: List[Dict[str, object]] = []
    stopped = False
    for stem in circuits:
        orig_path = Path(args.orig_dir) / f"{stem}.v"
        if not orig_path.exists():
            log(f"[WARN] 找不到原始网表: {orig_path}，跳过")
            continue
        timescale, orig_mod = parse_gatelevel_verilog(
            orig_path.read_text(encoding="utf-8", errors="ignore"))
        ost = netlist_stats(orig_mod, lib_ports, lib_outs, gate_simplification)
        log(f"[CIRCUIT] {stem}: gates={ost['gate_count']} depth={ost['depth']} "
            f"dff={ost['seq_count']} unleveled={ost['cycle_count']}")

        for seed in seeds:
            for depth in depths:
                for chain in enumerate_chains(families, depth, args.allow_repeats,
                                              args.max_chains, seed):
                    view_name = make_view_name(stem, chain, seed)
                    vpath = verilog_dir / f"{view_name}.v"
                    mpath = mappings_dir / f"{view_name}.json"
                    metapath = meta_dir / f"{view_name}.json"
                    if args.skip_existing and vpath.exists() and metapath.exists():
                        with open(metapath, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                        rows.append({k: v for k, v in payload.items()
                                     if k not in ("edits", "node_alignment", "edits_by_step")})
                        continue
                    try:
                        row = build_one_view(
                            args=args, stem=stem, chain=chain, seed=seed,
                            lib_ports=lib_ports, lib_outs=lib_outs, lib_ins=lib_ins,
                            gate_simplification=gate_simplification,
                            gate_equivalences=gate_equivalences,
                            timescale=timescale, orig_mod=orig_mod,
                            view_name=view_name, verilog_path=vpath,
                            mapping_path=mpath, meta_path=metapath,
                            lib_sha1=lib_sha1, map_sha1=map_sha1, rules_sha1=rules_sha1,
                        )
                    except Exception as e:  # 单个视图失败不阻断整个矩阵
                        log(f"[WARN] 生成失败 {view_name}: {type(e).__name__}: {e}")
                        continue
                    rows.append(row)
                    if args.limit_views and len(rows) >= args.limit_views:
                        stopped = True
                        break
                if stopped:
                    break
            if stopped:
                break
        if stopped:
            break
    if stopped:
        log(f"[WARN] 达到 --limit-views={args.limit_views}，提前结束生成（仅用于调试）")

    if not rows:
        log("[ERROR] 没有生成任何视图")
        return 1

    add_strength_scores(rows)
    write_manifest(rows, out_root)
    summary_rows, macro_rows = write_summaries(rows, out_root)
    matched = write_strength_matched_sets(rows, out_root, args.strength_bins)

    specs = build_split_specs(rows, families, freeze)
    for name, payload in specs.items():
        with open(specs_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    log(f"[OK] split specs: {specs_dir} ({len(specs)} 个文件)")

    fold_idx: List[Dict[str, object]] = []
    if args.materialize_folds:
        fold_idx = materialize_folds(specs, verilog_dir, folds_root)
        log(f"[OK] folds 已物化: {folds_root} ({len(fold_idx)} folds)")

    print_summary(macro_rows, matched, specs, fold_idx, rows, out_root, time.time() - t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())







