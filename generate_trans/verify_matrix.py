#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
verify_matrix.py — 分任务4 的等价/结构自检（把“CEC PASS”变成可复算的检查）

三层检查：
  A. 规则库自检（truth-table CEC over simplified algebra）
     对规则文件里每条规则，用“原始门类型的布尔语义”对比“规则表达式按 simplified algebra 求值”，
     全输入组合穷举证明等价；输出 rule_table_check.csv。
  B. 视图网表自检（逐 view）
     1) 端口集合、触发器数量与原始网表一致（变换不允许动时序边界/接口）；
     2) 未被改写的门必须原样存在（cell 与连接一致；resub 的网重命名会被显式复原后比较）；
     3) 结构完整性：无多驱动网；所有输入网要么是 PI/常量/assign 左值，要么被唯一门驱动；
     4) 深度/edit/gate_expansion 复算与 manifest 一致；
     5) node_alignment 的 dst 必须真实存在于输出网表，且 src 必须来自原始网表；
     6) 机制纯度：每条 edit 记录里的“规则家族”必须与该规则重新判定的 bucket 一致。
  C. 矩阵自检
     - 每个 (circuit, composition_depth) 的 chain 覆盖数量；
     - strength_matched_sets 非空、每个 matched_set 至少含 2 个 chain；
     - 单步 mechanism 的结构签名差异（edit/expansion/depth/inv/buf），输出 mechanism_signature.csv。

输出：verification_report.csv / rule_table_check.csv / mechanism_signature.csv / verification_summary.txt
退出码：0=全部 PASS；1=存在 FAIL（便于流水线 gate）。

用法：
  python verify_matrix.py --lib verilog_lib.v --map map.txt --rules rule_expand1.txt \
      --orig-dir orig --matrix-root matrix
"""

import argparse
import csv
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from add_gate_test4 import (  # noqa: E402
    ExprCall,
    Expr,
    collect_ports,
    emit_verilog,
    instance_output_ports,
    load_py_dict_from_file,
    netlist_stats,
    parse_equiv_expr,
    parse_gatelevel_verilog,
    parse_lib_info,
    rule_bucket,
    strip_bit_select,
)


# ------------------------------------------------------------
# 参数
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="分任务4：transformation matrix 自检")
    ap.add_argument("--lib", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--orig-dir", type=Path, default=Path("orig"))
    ap.add_argument("--matrix-root", type=Path, default=Path("matrix"))
    ap.add_argument("--limit", type=int, default=0, help="只检查前 N 个视图（0=全部）")
    ap.add_argument("--skip-roundtrip", action="store_true", help="跳过网表 round-trip 结构对比")
    return ap.parse_args()


# ------------------------------------------------------------
# simplified algebra 语义（规则库 truth-table CEC）
# ------------------------------------------------------------

DEFAULT_FORMALS = ["A", "B", "C", "D", "E", "F"]
SPECIAL_FORMALS = {
    "HADD": ["A0", "B0", "C1"],
    "ISOLAND": ["D", "ISO"],
    "LSDNEN": ["D", "ENB"],
    "LSDN": ["D"],
    "NBUFF": ["IN"],
    "MUX2": ["A", "B", "S"],
}


def formals_of(simple_type: str) -> List[str]:
    return list(SPECIAL_FORMALS.get(simple_type, DEFAULT_FORMALS))


def build_arity_table(lib_ports, lib_outs, gate_simplification) -> Dict[str, int]:
    """
    简化门类型 -> 功能输入个数。优先取库中实际单元端口数的众数，
    特殊门（HADD/ISOLAND/LSDNEN/LSDN/NBUFF）用规则库形参约定。
    """
    from add_gate_test4 import simplify_cell
    cand: Dict[str, Counter] = defaultdict(Counter)
    for cell, ports in lib_ports.items():
        st = simplify_cell(cell, gate_simplification)
        ins = [p for p in ports if p not in lib_outs.get(cell, set())]
        if ins:
            cand[st][len(ins)] += 1
    table: Dict[str, int] = {}
    for st, c in cand.items():
        table[st] = int(c.most_common(1)[0][0])
    for st, fl in SPECIAL_FORMALS.items():
        table.setdefault(st, len(fl))
    return table


def arity_of(st: str, arity_table: Dict[str, int]) -> int:
    if st in SPECIAL_FORMALS:
        return len(SPECIAL_FORMALS[st])
    return int(arity_table.get(st, 2))


def gate_eval(st: str, v: Sequence[bool]) -> Optional[bool]:
    """
    原始（简化）门类型的布尔语义。形参顺序 = 规则库 A,B,C,... 的绑定顺序。
    时序门（DFF/SDFFSR）无组合语义，返回 None。
    """
    if st in {"DFF", "SDFFSR"}:
        return None
    if st == "NBUFF" and len(v) == 1:
        return not v[0]          # NBUFFX2 的输出端口是 QN（反相缓冲）
    if st == "INV" and len(v) == 1:
        return not v[0]
    if st == "BUF":
        return v[0]
    if st.startswith("MUX"):
        a, b, s = v[0], v[1], v[2]
        return b if s else a
    m = re.match(r"^(N?AND|N?OR|X?NOR|X?OR)(\d)$", st)
    if m:
        kind, n = m.group(1), int(m.group(2))
        vals = list(v[:n])
        agg_all = all(vals)
        agg_any = any(vals)
        if kind == "AND":
            return agg_all
        if kind == "NAND":
            return not agg_all
        if kind == "OR":
            return agg_any
        if kind == "NOR":
            return not agg_any
        if kind == "XOR":
            r = False
            for x in vals:
                r ^= bool(x)
            return r
        if kind == "XNOR":
            r = False
            for x in vals:
                r ^= bool(x)
            return not r
    # AO / OA / AOI / OAI 组
    m2 = re.match(r"^(AOI|OAI|AO|OA)(\d*)$", st)
    if m2:
        kind, suffix = m2.group(1), m2.group(2)
        # suffix 形如 '21' / '22' / '221' / '222' / ''
        widths = [int(c) for c in suffix] if suffix else [2]
        args = list(v)
        pos = 0
        and_terms: List[bool] = []
        or_terms: List[bool] = []
        for w in widths:
            terms = args[pos:pos + w]
            pos += w
            if not terms:
                return None
            and_terms.append(all(terms))
            or_terms.append(any(terms))
        if kind in ("AO", "AOI"):
            core = any(and_terms)
            return (not core) if kind == "AOI" else core
        core = all(or_terms)
        return (not core) if kind == "OAI" else core
    if st == "NORI3":
        return all(v[:3])
    if st == "HADD":
        r = False
        for x in v[:3]:
            r ^= bool(x)
        return r
    if st == "ISOLAND":
        return bool(v[0]) and bool(v[1])
    if st == "LSDNEN":
        return bool(v[0]) and not bool(v[1])
    if st == "LSDN":
        return bool(v[0])
    return None


def expr_eval(e: Expr, env: Dict[str, bool]) -> Optional[bool]:
    """按 simplified algebra 求表达式值；未知叶子/门类型返回 None。"""
    if isinstance(e, str):
        s = e.strip()
        if s == "1'b0":
            return False
        if s == "1'b1":
            return True
        if s == "1'bz":
            return None
        return env.get(s)
    vals: List[bool] = []
    for a in e.args:
        v = expr_eval(a, env)
        if v is None:
            return None
        vals.append(v)
    return gate_eval(e.fn, vals)


def formals_for_rule(st: str, arity_table: Dict[str, int]) -> List[str]:
    if st in SPECIAL_FORMALS:
        return list(SPECIAL_FORMALS[st])
    n = arity_of(st, arity_table)
    return DEFAULT_FORMALS[:n]


def check_rule_table(gate_equivalences: Dict[str, dict],
                     arity_table: Dict[str, int]) -> List[Dict[str, object]]:
    """对规则库做穷举真值表等价检查（与生成器相同的形参绑定约定）。"""
    rows: List[Dict[str, object]] = []
    for st, rules in gate_equivalences.items():
        eq_list = list(rules.get("equivalent", []) or [])
        if not eq_list:
            continue
        formals = formals_for_rule(st, arity_table)
        n = len(formals)
        if gate_eval(st, [False] * max(1, n)) is None:
            rows.append({
                "gate_type": st, "rule_index": "", "rule_expr": "",
                "bucket": "", "n_inputs": n, "n_vectors": 0,
                "mismatches": "", "status": "SKIP",
                "note": "无组合语义（时序门/未知类型）",
            })
            continue
        for ridx, expr_str in enumerate(eq_list):
            try:
                expr = parse_equiv_expr(expr_str)
            except Exception as e:
                rows.append({
                    "gate_type": st, "rule_index": ridx + 1, "rule_expr": expr_str,
                    "bucket": "", "n_inputs": n, "n_vectors": 0, "mismatches": "",
                    "status": "FAIL", "note": f"表达式解析失败: {e}",
                })
                continue
            mismatches = 0
            for bits in itertools.product([False, True], repeat=n):
                env = dict(zip(formals, bits))
                if "A" in env:          # 与 bind_formals 一致：A 的别名 IN
                    env.setdefault("IN", env["A"])
                expect = gate_eval(st, list(bits))
                got = expr_eval(expr, env)
                if got is None or got != expect:
                    mismatches += 1
            rows.append({
                "gate_type": st,
                "rule_index": ridx + 1,
                "rule_expr": expr_str,
                "bucket": rule_bucket(st, expr_str),
                "n_inputs": n,
                "n_vectors": 2 ** n,
                "mismatches": mismatches,
                "status": "PASS" if mismatches == 0 else "FAIL",
                "note": "" if mismatches == 0 else "规则与原始门功能不等价",
            })
    return rows


# ------------------------------------------------------------
# 视图级结构自检
# ------------------------------------------------------------

RESUB_BUCKETS = {"resub_reuse_buf", "resub_reuse_shrink", "resub_invert", "resub_divisor"}
FAMILY_BUCKETS = {
    "decomp": {"decomp"},
    "balance": {"balance"},
    "refactor": {"refactor"},
    "resub": RESUB_BUCKETS,
}


def _driven_net_map(mod, lib_outs) -> Tuple[Dict[str, str], List[str]]:
    """输出网 -> 驱动门名；同时返回多驱动网列表。"""
    driven: Dict[str, str] = {}
    multi: List[str] = []
    for inst in mod.instances:
        for p in instance_output_ports(inst, lib_outs):
            net = inst.conns.get(p)
            if not net:
                continue
            if net in driven:
                multi.append(net)
            else:
                driven[net] = inst.name
    return driven, multi


def _unleveled_gate_names(mod, lib_outs, gate_simplification) -> set:
    """
    用与 add_gate_test4.compute_netlist_depth 相同的规则做定层，返回“无法定层”的门名集合
    （未驱动网 或 组合环 都会落在这里）。
    """
    from add_gate_test4 import _is_sequential_cell
    consts = {"1'b0", "1'b1", "1'bz"}
    level_net: Dict[str, int] = {}
    for p in mod.ports:
        level_net.setdefault(p, 0)
    for kind, decls in mod.decl_order:
        if kind == "input":
            for d in decls:
                level_net[d.name] = 0
    for a in mod.assigns:
        level_net.setdefault(a.lhs, 0)

    comb = []
    for inst in mod.instances:
        if _is_sequential_cell(inst.cell, gate_simplification):
            for p in instance_output_ports(inst, lib_outs):
                net = inst.conns.get(p)
                if net:
                    level_net[net] = 0
        else:
            comb.append(inst)

    def known(sig: str) -> bool:
        return sig in level_net or strip_bit_select(sig) in level_net or sig in consts

    pending = list(comb)
    progress = True
    while pending and progress:
        progress = False
        nxt = []
        for inst in pending:
            outs = instance_output_ports(inst, lib_outs)
            if not outs:
                continue
            ins = [v for k, v in inst.conns.items() if k not in outs]
            if any(not known(s) for s in ins):
                nxt.append(inst)
                continue
            for p in outs:
                net = inst.conns.get(p)
                if net:
                    level_net[net] = 1
            progress = True
        pending = nxt
    return {i.name for i in pending}



def _signal_diff_pairs(orig_mod, dst_mod, rewritten: set) -> Tuple[List[str], List[str], List[Tuple[str, str]], int]:
    """返回 (missing, cell_diff, diff_pairs, kept)。"""
    orig_by_name = {i.name: i for i in orig_mod.instances}
    dst_by_name = {i.name: i for i in dst_mod.instances}
    missing: List[str] = []
    cell_diff: List[str] = []
    diff_pairs: List[Tuple[str, str]] = []
    kept = 0
    for name, inst in orig_by_name.items():
        if name in rewritten:
            continue
        d = dst_by_name.get(name)
        if d is None:
            missing.append(name)
            continue
        kept += 1
        if d.cell != inst.cell or set(d.conns.keys()) != set(inst.conns.keys()):
            cell_diff.append(name)
            continue
        for port, sig in inst.conns.items():
            if d.conns[port] != sig:
                diff_pairs.append((sig, d.conns[port]))
    return missing, cell_diff, diff_pairs, kept


def check_view(*, matrix_root: Path, row: Dict[str, object], orig_mod, dst_mod,
               lib_ports, lib_outs, gate_simplification,
               gate_equivalences) -> Dict[str, object]:
    """对单个 view 做结构/一致性检查。"""
    view_file = str(row["view_file"])
    meta_path = matrix_root / "meta" / f"{Path(view_file).stem}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    alignment = meta.get("node_alignment", {}) or {}
    edits = meta.get("edits", []) or []

    checks: Dict[str, bool] = {}
    detail: Dict[str, object] = {}

    # 1) 接口与时序边界不变
    checks["ports_match"] = set(orig_mod.ports) == set(dst_mod.ports)
    o_stats = netlist_stats(orig_mod, lib_ports, lib_outs, gate_simplification)
    d_stats = netlist_stats(dst_mod, lib_ports, lib_outs, gate_simplification)
    checks["dff_match"] = int(o_stats["seq_count"]) == int(d_stats["seq_count"])
    detail["n_dff"] = int(d_stats["seq_count"])

    # 2) manifest 指标可复算
    checks["manifest_stats_match"] = (
        int(row.get("orig_gate_count", -1)) == int(o_stats["gate_count"])
        and int(row.get("final_gate_count", -1)) == int(d_stats["gate_count"])
        and int(row.get("depth_orig", -1)) == int(o_stats["depth"])
        and int(row.get("depth_final", -1)) == int(d_stats["depth"])
        and int(row.get("edit_count", -1)) == len(edits)
        and int(row.get("gate_expansion", -10 ** 9)) == int(d_stats["gate_count"]) - int(o_stats["gate_count"])
        and int(row.get("depth_change", -10 ** 9)) == int(d_stats["depth"]) - int(o_stats["depth"])
    )

    # 3) 结构完整性：无多驱动；输入要么是 PI/常量/assign 左值，要么被唯一门驱动
    driven, multi = _driven_net_map(dst_mod, lib_outs)
    checks["no_multi_driven"] = (len(multi) == 0)
    detail["multi_driven"] = len(multi)
    pi = set(dst_mod.ports)
    for kind, decls in dst_mod.decl_order:
        if kind == "input":
            pi |= {d.name for d in decls}
    assign_lhs = {a.lhs for a in dst_mod.assigns}
    consts = {"1'b0", "1'b1", "1'bz"}
    undriven: List[str] = []
    for inst in dst_mod.instances:
        out_ports = instance_output_ports(inst, lib_outs)
        for k, v in inst.conns.items():
            if k in out_ports or v in consts:
                continue
            if v in driven or v in pi or v in assign_lhs or strip_bit_select(v) in pi:
                continue
            undriven.append(f"{inst.name}.{k}={v}")
    checks["no_undriven_inputs"] = (len(undriven) == 0)
    detail["undriven_inputs"] = undriven[:5]

    # 4) 未被改写的门必须原样保留（resub 的网改名必须是一致的一对一映射）
    rewritten = set(alignment.keys())
    missing, cell_diff, diff_pairs, kept = _signal_diff_pairs(orig_mod, dst_mod, rewritten)
    checks["untouched_preserved"] = (len(missing) == 0 and len(cell_diff) == 0)
    detail["kept_untouched"] = kept
    detail["missing_untouched"] = len(missing)
    detail["cell_diff"] = len(cell_diff)
    rename_ok = True
    if diff_pairs:
        fwd: Dict[str, str] = {}
        for o, d in diff_pairs:
            if fwd.setdefault(o, d) != d:   # 允许级联改名导致的“多对一”，但必须是函数关系
                rename_ok = False
        orig_driven, _ = _driven_net_map(orig_mod, lib_outs)
        dst_driven, _ = _driven_net_map(dst_mod, lib_outs)
        dst_pi = set(dst_mod.ports)
        for k, decls in dst_mod.decl_order:
            if k == "input":
                dst_pi |= {d.name for d in decls}
        for o, d in diff_pairs:
            drv = orig_driven.get(o)
            if drv is None or drv not in rewritten:
                rename_ok = False      # 只有被改写门的输出网才允许被改名
            if d not in dst_driven and d not in dst_pi:
                rename_ok = False      # 改名目标必须是真实存在的网（被门驱动或 PI）
    checks["rename_consistent"] = rename_ok
    detail["renamed_signals"] = len({o for o, _ in diff_pairs})

    # 5) node_alignment 合法性
    dst_names = {i.name for i in dst_mod.instances}
    orig_names = {i.name for i in orig_mod.instances}
    bad_dst = [d for ds in alignment.values() for d in ds if d not in dst_names]
    bad_src = [s for s in alignment.keys() if s not in orig_names]
    checks["alignment_valid"] = (len(bad_dst) == 0 and len(bad_src) == 0)
    detail["alignment_entries"] = len(alignment)

    # 6) 机制纯度：edit 的“规则家族”可复算，且属于该算子 family 的 bucket
    rule_mode = str(row.get("rule_mode", ""))
    bad_bucket: List[str] = []
    for rec in edits:
        st = str(rec.get("变换门类型", ""))
        bucket = str(rec.get("规则家族", ""))
        expr_str = str(rec.get("规则表达式", "") or "")
        ridx = rec.get("使用规则序号_原始", rec.get("使用规则序号", ""))
        if bucket.startswith("resub"):
            if bucket not in RESUB_BUCKETS:
                bad_bucket.append(f"{st}:{bucket}")
            continue
        # 优先用记录下来的规则表达式复算（规则列表在算子初始化时会重排，序号不是稳定标识）
        if expr_str:
            raw_list = list((gate_equivalences.get(st) or {}).get("equivalent", []) or [])
            if expr_str not in raw_list:
                bad_bucket.append(f"{st}: 规则表达式不在规则库中 {expr_str}")
                continue
            recomputed = rule_bucket(st, expr_str)
            if recomputed != bucket:
                bad_bucket.append(f"{st}: recorded={bucket} recomputed={recomputed} expr={expr_str}")
            continue
        try:
            idx = int(ridx) - 1
        except Exception:
            bad_bucket.append(f"{st}:{bucket} 无规则信息")
            continue
        eq_list = list((gate_equivalences.get(st) or {}).get("equivalent", []) or [])
        if not (0 <= idx < len(eq_list)):
            bad_bucket.append(f"{st}#{idx + 1} 越界")
            continue
        recomputed = rule_bucket(st, eq_list[idx])
        if recomputed != bucket:
            bad_bucket.append(f"{st}#{idx + 1}: recorded={bucket} recomputed={recomputed}")
    checks["edit_bucket_recomputable"] = (len(bad_bucket) == 0)
    detail["bad_bucket"] = bad_bucket[:5]

    purity_ok = True
    if rule_mode == "partitioned":
        chain = [c for c in str(row.get("operator_chain", "")).split("+") if c]
        for rec in edits:
            b = str(rec.get("规则家族", ""))
            fam = "resub" if b.startswith("resub") else b
            if fam not in chain or b not in FAMILY_BUCKETS.get(fam, set()):
                purity_ok = False
    checks["mechanism_purity"] = purity_ok

    # 7) 组合环：不允许出现“新的”未定层门（原始网表本身可能含组合环，展开环路里的门会让数量增加，
    #    所以这里检查的是：每个未定层门的祖先（溯源）在原始网表里也必须是未定层的）
    orig_unleveled = _unleveled_gate_names(orig_mod, lib_outs, gate_simplification)
    dst_unleveled = _unleveled_gate_names(dst_mod, lib_outs, gate_simplification)
    inv_align: Dict[str, List[str]] = defaultdict(list)
    for o, ds in alignment.items():
        for d in ds:
            inv_align[d].append(o)
    new_cycle: List[str] = []
    for g in dst_unleveled:
        if g in orig_unleveled:
            continue
        if any(o in orig_unleveled for o in inv_align.get(g, [])):
            continue
        new_cycle.append(g)
    checks["no_new_cycle_members"] = (len(new_cycle) == 0)
    detail["unleveled_before"] = len(orig_unleveled)
    detail["unleveled_after"] = len(dst_unleveled)
    detail["new_cycle_members"] = new_cycle[:5]


    out: Dict[str, object] = {
        "view_name": row.get("view_name"),
        "dst_verilog": view_file,
        "circuit": row.get("circuit"),
        "chain_key": row.get("chain_key"),
        "composition_depth": row.get("composition_depth"),
        "rule_mode": rule_mode,
        "edit_count": row.get("edit_count"),
        "gate_expansion": row.get("gate_expansion"),
        "depth_change": row.get("depth_change"),
    }
    out.update({k: ("PASS" if v else "FAIL") for k, v in checks.items()})
    out["n_fail"] = sum(1 for v in checks.values() if not v)
    out["status"] = "PASS" if out["n_fail"] == 0 else "FAIL"
    out["detail"] = json.dumps(detail, ensure_ascii=False)
    return out


# ------------------------------------------------------------
# 矩阵级自检
# ------------------------------------------------------------

def check_matrix(manifest: List[Dict[str, object]], specs_dir: Path,
                 matched_path: Path) -> Tuple[Dict[str, bool], Dict[str, object]]:
    checks: Dict[str, bool] = {}
    detail: Dict[str, object] = {}

    # 1) 每个 (circuit, depth) 的 chain 覆盖
    cover: Dict[Tuple[str, int], set] = defaultdict(set)
    for r in manifest:
        cover[(str(r["circuit"]), int(r["composition_depth"]))].add(str(r["chain_key"]))
    detail["chains_per_circuit_depth"] = {f"{c}|d{d}": len(v) for (c, d), v in sorted(cover.items())}
    checks["chain_coverage"] = bool(cover) and all(len(v) >= 1 for v in cover.values())

    # 2) 强度匹配子集
    matched_rows: List[Dict[str, str]] = []
    if matched_path.exists():
        with open(matched_path, "r", encoding="utf-8-sig", newline="") as f:
            matched_rows = list(csv.DictReader(f))
    sets: Dict[str, set] = defaultdict(set)
    for r in matched_rows:
        sets[str(r["matched_set_id"])].add(str(r["chain_key"]))
    checks["strength_matched_nonempty"] = len(matched_rows) > 0
    checks["strength_matched_multi_chain"] = bool(sets) and all(len(v) >= 2 for v in sets.values())
    detail["matched_sets"] = len(sets)

    # 3) split specs 完整性
    spec_files = sorted(specs_dir.glob("*.json"))
    n_folds = 0
    empty_folds: List[str] = []
    for p in spec_files:
        payload = json.loads(p.read_text(encoding="utf-8"))
        for fold in payload.get("folds", []):
            n_folds += 1
            if fold["n_train"] == 0 or fold["n_test"] == 0:
                empty_folds.append(f"{payload['name']}/{fold['fold']}")
    checks["split_specs_present"] = len(spec_files) >= 3
    checks["split_specs_nonempty"] = len(empty_folds) == 0
    detail["spec_files"] = [p.name for p in spec_files]
    detail["n_folds"] = n_folds
    detail["empty_folds"] = empty_folds
    return checks, detail


def build_mechanism_signature(manifest: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """各 chain 的结构签名（用于确认四种算子机制确实不同）。"""
    groups: Dict[Tuple[str, int], List[Dict[str, object]]] = defaultdict(list)
    for r in manifest:
        groups[(str(r["chain_key"]), int(r["composition_depth"]))].append(r)
    rows: List[Dict[str, object]] = []
    for (chain, dep), rs in sorted(groups.items()):
        n = len(rs)

        def _m(key: str) -> float:
            return sum(float(r.get(key, 0) or 0) for r in rs) / n

        rows.append({
            "chain_key": chain,
            "composition_depth": dep,
            "n_views": n,
            "edit_count_mean": round(_m("edit_count"), 4),
            "edit_ratio_mean": round(_m("edit_ratio"), 6),
            "gate_expansion_mean": round(_m("gate_expansion"), 4),
            "gate_expansion_ratio_mean": round(_m("gate_expansion_ratio"), 6),
            "depth_change_mean": round(_m("depth_change"), 4),
            "depth_change_ratio_mean": round(_m("depth_change_ratio"), 6),
            "strength_score_mean": round(_m("strength_score"), 6),
        })
    return rows


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


# ------------------------------------------------------------
# main
# ------------------------------------------------------------

def main() -> int:
    args = parse_args()
    matrix_root = Path(args.matrix_root)
    manifest_path = matrix_root / "view_manifest.csv"
    if not manifest_path.exists():
        print(f"[ERROR] 找不到 manifest: {manifest_path}，请先跑 matrix_builder.py")
        return 1

    with open(manifest_path, "r", encoding="utf-8-sig", newline="") as f:
        manifest = [dict(r) for r in csv.DictReader(f)]
    if args.limit:
        manifest = manifest[:args.limit]
    print(f"[INFO] 待检查视图: {len(manifest)}")

    lib_ports, lib_outs, lib_ins = parse_lib_info(
        Path(args.lib).read_text(encoding="utf-8", errors="ignore"))
    gate_simplification = load_py_dict_from_file(Path(args.map), "gate_simplification")
    gate_equivalences = load_py_dict_from_file(Path(args.rules), "gate_equivalences")
    arity_table = build_arity_table(lib_ports, lib_outs, gate_simplification)

    # A) 规则库 truth-table CEC
    rule_rows = check_rule_table(gate_equivalences, arity_table)
    n_rule_pass = sum(1 for r in rule_rows if r["status"] == "PASS")
    n_rule_fail = sum(1 for r in rule_rows if r["status"] == "FAIL")
    n_rule_skip = sum(1 for r in rule_rows if r["status"] == "SKIP")
    _write_csv(matrix_root / "rule_table_check.csv", rule_rows)
    for r in rule_rows:
        if r["status"] == "FAIL":
            print(f"[RULE-FAIL] {r['gate_type']}#{r['rule_index']} {r['rule_expr']} "
                  f"mismatch={r['mismatches']}/{r['n_vectors']}")

    # B) 逐视图结构检查
    orig_cache: Dict[str, object] = {}
    view_rows: List[Dict[str, object]] = []
    for row in manifest:
        stem = Path(str(row["src_verilog"])).stem
        if stem not in orig_cache:
            op = Path(args.orig_dir) / f"{stem}.v"
            if op.exists():
                orig_cache[stem] = parse_gatelevel_verilog(
                    op.read_text(encoding="utf-8", errors="ignore"))[1]
            else:
                print(f"[WARN] 缺少原始网表 {op}")
                orig_cache[stem] = None
        orig_mod = orig_cache[stem]
        if orig_mod is None:
            continue
        vpath = matrix_root / "verilog" / str(row["view_file"])
        if not vpath.exists():
            print(f"[WARN] 缺少视图网表 {vpath}")
            continue
        dst_mod = parse_gatelevel_verilog(vpath.read_text(encoding="utf-8"))[1]
        try:
            view_rows.append(check_view(
                matrix_root=matrix_root, row=row, orig_mod=orig_mod, dst_mod=dst_mod,
                lib_ports=lib_ports, lib_outs=lib_outs,
                gate_simplification=gate_simplification, gate_equivalences=gate_equivalences))
        except Exception as e:
            view_rows.append({"view_name": row.get("view_name"), "status": "FAIL", "n_fail": 1,
                              "detail": f"检查异常 {type(e).__name__}: {e}"})
    _write_csv(matrix_root / "verification_report.csv", view_rows)

    # C) 矩阵级检查 + mechanism 签名
    matrix_checks, matrix_detail = check_matrix(
        manifest, matrix_root / "split_specs", matrix_root / "strength_matched_sets.csv")
    sig_rows = build_mechanism_signature(manifest)
    _write_csv(matrix_root / "mechanism_signature.csv", sig_rows)

    n_view_fail = sum(1 for r in view_rows if str(r.get("status")) != "PASS")
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("transformation matrix 自检报告")
    lines.append("=" * 78)
    lines.append(f"[A] 规则库 truth-table CEC: PASS={n_rule_pass} FAIL={n_rule_fail} SKIP={n_rule_skip}")
    lines.append(f"[B] 视图结构/一致性: total={len(view_rows)} "
                 f"PASS={len(view_rows) - n_view_fail} FAIL={n_view_fail}")
    for k, v in matrix_checks.items():
        lines.append(f"[C] {k}: {'PASS' if v else 'FAIL'}")
    lines.append(f"    矩阵细节: {json.dumps(matrix_detail, ensure_ascii=False)}")
    lines.append("-" * 78)
    lines.append("单步 mechanism 结构签名（跨 circuit 未加权，仅看趋势）:")
    for r in sig_rows:
        if int(r["composition_depth"]) != 1:
            continue
        lines.append(f"  {str(r['chain_key']):<10} n={int(r['n_views']):<4} "
                     f"edit_ratio={float(r['edit_ratio_mean']):.4f} "
                     f"gate_exp_ratio={float(r['gate_expansion_ratio_mean']):+.4f} "
                     f"depth_change={float(r['depth_change_mean']):+.2f}")
    lines.append("=" * 78)
    report_text = "\n".join(lines)
    (matrix_root / "verification_summary.txt").write_text(report_text, encoding="utf-8")
    print(report_text)

    ok = (n_rule_fail == 0 and n_view_fail == 0 and all(matrix_checks.values()))
    print(f"\n[VERDICT] {'ALL PASS' if ok else 'HAS FAILURES'} "
          f"(rule_fail={n_rule_fail}, view_fail={n_view_fail})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())







