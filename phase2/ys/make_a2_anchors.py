# -*- coding: utf-8 -*-
"""
make_a2_anchors.py —— **A2：锚点与逻辑锥 → 可信标签分级 + 覆盖率（单独一表）**。

思路（不追求一一对应 ✓）：
  ① **锚点**：从注入记录（`generate_trans/<root>/<host>/provenance.json` ✓）拿**确定**的东西：
     `new_gates`（注入实例 ✓）、`payload_wire` / `hijacked_output`（被劫持的输出网 ✓）、
     `payload_target`（载荷去向 ✓）、触发/载荷样式 ✓；再在**源网表**上补结构锚点：
     触发链输出网 ✓、载荷注入点（劫持 mux 的端口 ✓）、区域相邻的寄存器端口/D 端 ✓、触及的主 IO ✓。
  ② **逻辑锥 → 候选区域**：以劫持 mux 为界，**反向锥**（追触发链 ✓）+ **前向锥**（到被劫持输出 ✓）
     → 区域实例集合；区域外 1 跳 = 边界。
  ③ **可信标签分级**（实例级 ✓）：
     `pos_reliable` = 注入实例 ✓（trojan 视图）；`unknown` = 区域内部的非注入实例 + 区域 1 跳边界 ✓；
     `neg_reliable` = 其余 ✓（控制视图按"良性注入"整体算 neg ✓，但仍作锚点参与覆盖率 ✓）。
  ④ **覆盖率**（**单独落在 `a2_coverage.csv`** ✓）：对每个 (视图, 配方) 的**已成产物**，
     用 `make_inst_alignment` 的实例级对齐（inst_prov / 门名 base / `\\实例.端口` / 网名 / 实例名 ✓）
     算：锚点覆盖率、区域覆盖率、pos/neg/unknown 覆盖率、劫持点覆盖率，以及**只名字通道**的对照值 ✓。

用法：
    py phase2/ys/make_a2_anchors.py --hops 2
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import deque
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CUR))

from phase2 import netlist_lib as NL          # noqa: E402
import make_inst_alignment as MIA             # noqa: E402  复用实例级对齐

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"
HOSTS_DEFAULT = ROOT / "generate_trans" / "hosts_bt2"
OUT_DEFAULT = ROOT / "10.15" / "01_数据与标签" / "A2_锚点与逻辑锥" / "tables"
MANIFESTS_DEFAULT = ",".join([
    str(ROOT / "generate_trans" / "yslib_test" / "convert_manifest.csv"),
    str(ROOT / "generate_trans" / "keepab" / "conv" / "convert_manifest.csv"),
])
def norm(n: str) -> str:
    n = str(n).strip()
    return n[1:] if n.startswith("\\") else n


def load_records(hosts_root: Path) -> list:
    """读全部注入记录（每电路一个 provenance.json ✓）。"""
    out = []
    for f in sorted(glob.glob(str(hosts_root / "*" / "provenance.json"))):
        host = Path(f).parent.name
        for r in json.loads(Path(f).read_text(encoding="utf-8")):
            r["host"] = host
            out.append(r)
    return out


class Graph:
    """源网表的**实例级**图：网 → 驱动实例 / 消费实例；支持前向、反向 1 跳。"""

    def __init__(self, nl):
        self.nl = nl
        self.cell = {str(i.name): str(i.gate) for i in nl.insts}
        self.out_ports = {str(i.name): [(p, norm(n)) for p, n in nl.outs(i)] for i in nl.insts}
        self.in_ports = {str(i.name): [(p, norm(n)) for p, n in nl.ins(i)] for i in nl.insts}
        self.drv, self.cons = {}, {}
        for i in nl.insts:
            for _p, n in self.out_ports[str(i.name)]:
                self.drv.setdefault(n, str(i.name))
            for _p, n in self.in_ports[str(i.name)]:
                self.cons.setdefault(n, []).append(str(i.name))

    def back(self, insts: set) -> set:
        out = set()
        for g in insts:
            for _p, n in self.in_ports.get(g, []):
                d = self.drv.get(n)
                if d:
                    out.add(d)
        return out

    def fwd(self, insts: set) -> set:
        out = set()
        for g in insts:
            for _p, n in self.out_ports.get(g, []):
                out |= set(self.cons.get(n, []))
        return out


def region_profile(g: Graph, core: set, hops: int) -> dict:
    """以注入实例为核心，前/后向各扩张 1..hops 跳 → 区域/边界规模。"""
    prof, cur = {}, set(core)
    for h in (1, 2, 3):
        cur = cur | g.back(cur) | g.fwd(cur)
        prof[f"region{h}"] = set(cur)
        prof[f"boundary{h}"] = (g.back(cur) | g.fwd(cur)) - cur
    return prof


def anchors_of(g: Graph, rec: dict, region: set) -> list:
    """锚点表行（确定性来源优先：注入记录 ✓，再补结构锚点 ✓）。"""
    A, kind = [], rec.get("kind")
    for name in rec.get("new_gates") or []:
        cell = g.cell.get(name, "")
        A.append({"anchor_kind": f"{kind}_inst", "anchor": name, "net": "", "cell": cell,
                  "port": "", "dir": "inst"})
        for p, n in g.out_ports.get(name, []):
            A.append({"anchor_kind": "out_net", "anchor": name, "net": n, "cell": cell,
                      "port": p, "dir": "out"})
        for p, n in g.in_ports.get(name, []):
            A.append({"anchor_kind": "in_net", "anchor": name, "net": n, "cell": cell,
                      "port": p, "dir": "in"})
    for key, k in (("payload_wire", "payload_wire"), ("hijacked_output", "hijacked_output")):
        v = rec.get(key)
        if v:
            A.append({"anchor_kind": k, "anchor": g.drv.get(norm(v), ""), "net": norm(v),
                      "cell": "", "port": "", "dir": "net"})
    for name in sorted(region):
        cell = g.cell.get(name, "")
        if "DFF" in cell.upper():
            A.append({"anchor_kind": "region_reg", "anchor": name, "net": "", "cell": cell,
                      "port": "", "dir": "inst"})
    rnets = {n for name in region for _p, n in g.out_ports.get(name, [])}
    for p in list(g.nl.inputs) + list(g.nl.outputs):
        if norm(p) in rnets:
            A.append({"anchor_kind": "io", "anchor": g.drv.get(norm(p), ""), "net": norm(p),
                      "cell": "", "port": "", "dir": "io"})
    return A


def grade_sets(g: Graph, rec: dict, prof: dict, hops: int) -> dict:
    """实例级可信标签分级（pos / unknown / neg ✓）。"""
    core = set(rec.get("new_gates") or [])
    region = prof[f"region{hops}"]
    boundary = prof[f"boundary{hops}"] - region
    pos = {n for n in core if rec.get("kind") == "trojan"}
    unknown = (region | boundary) - core
    neg = set(g.cell) - pos - unknown
    return {"core": core, "region": region, "boundary": boundary,
            "pos": pos, "unknown": unknown, "neg": neg}


def cov(sets_sub: set, src_names: set, align: dict) -> tuple:
    S = {s for s in sets_sub if s in src_names}
    a = {s for s in S if s in align}
    return len(S), len(a), round(len(a) / max(1, len(S)), 4)


def coverage_row(src: Path, cand: Path, lib, gs: dict, label: str) -> dict:
    """一个 (视图, 配方) 的覆盖率（**另表 a2_coverage.csv** ✓）。

    **口径（写清，免得被读成"结构保持率" ✗）**：
      · 分母 = **源网表**里属于该集合的实例数 ✓；分子 = 其中在 `node_alignment`（`align`）里有键的实例数 ✓
        → 方向是 **源 → 变换后** ✓（问的是"原网表的门有没有绑上变换后的门" ✓）。
      · 绑定判据 = 溯源 / 网名·端口回溯 ✓（**不做功能等价验证** ✗，且**一对多** ✓：
        一个源门被复制/拆成多个门只记"有一个绑上" ✓ → `cover=1.0` ≠ 结构保持 ✗）。
      · 另给两组补充量：`core_in_conv_names` / `core_in_conv_text`（注入门在变换网表里**还剩几个**
        ✓ → 区分"整体被优化掉" ✗ 与"在但没绑上" ✓）；`n_conv_bound` / `n_conv_unbound` / `cov_conv`
        （**变换后侧**：有多少门能绑回源门 ✓）。
      · `by_*` = 全图路线命中 ✓；`core_by_*` = **只看注入区**的路线命中 ✓（回答"哪条路线救回了注入门" ✓）。
    """
    mp = cand.with_suffix(".map.json")
    ip = {}
    if mp.exists():
        ip = {str(k): str(v) for k, v in
              (json.loads(mp.read_text(encoding="utf-8")).get("inst_prov") or {}).items()}
    srcf, candf = MIA.src_facts(src, lib), MIA.cand_facts(cand)
    pr = {}
    align, legacy, hits = MIA.build_align(srcf, candf, ip, pair_routes=pr)                        # 全图路线命中
    _al, _lg, core_hits = MIA.build_align(srcf, candf, ip, focus=set(gs["core"]))
    src_routes = {}                       # 源门 → 命中过它的路线集合 ✓
    for (_s, _t), _rs in pr.items():
        src_routes.setdefault(_s, set()).update(_rs)

    def only(key, subset):                # 该集合里「**只能**靠 key 绑上」的源门数 ✓（必要性 ✓）
        return sum(1 for x in subset if x in names and src_routes.get(x) == {key})  # 只看注入区
    names, conv_names = srcf["names"], candf["names"]
    bound = {t for lst in align.values() for t in lst}        # 被绑回源门的变换后门
    n_gates = len(candf["gates"])
    text = cand.read_text(encoding="utf-8", errors="replace")
    core_txt = sum(1 for c in gs["core"]
                   if c in names and re.search(r"(?<![\w.])" + re.escape(str(c)) + r"(?![\w])", text))
    row = {"src_root": label, "n_src_inst": len(names),
           "n_conv_gates": n_gates, "n_inst_prov": len(ip),
           "n_conv_bound": len(bound), "n_conv_unbound": max(0, n_gates - len(bound)),
           "cov_conv": round(len(bound) / max(1, n_gates), 4),
           "core_in_conv_names": len(set(gs["core"]) & conv_names),
           "core_in_conv_text": core_txt}
    for key, S in (("core", gs["core"]), ("region", gs["region"]), ("pos", gs["pos"]),
                   ("neg", gs["neg"]), ("unknown", gs["unknown"])):
        t, al, r = cov(S, names, align)
        row[f"{key}_total"], row[f"{key}_aligned"], row[f"cover_{key}"] = t, al, r
        row[f"cover_{key}_nameonly"] = cov(S, names, legacy)[2]
    row.update({f"by_{k}": v for k, v in hits.items()})
    row.update({f"core_by_{k}": v for k, v in core_hits.items()})
    for _k in ("instprov", "base", "port", "net", "name"):
        row[f"only_{_k}"] = only(_k, names)
        row[f"core_only_{_k}"] = only(_k, gs["core"])
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts-root", type=Path, default=HOSTS_DEFAULT)
    ap.add_argument("--manifests", default=MANIFESTS_DEFAULT)
    ap.add_argument("--labels", default="yslib_test,keepab")
    ap.add_argument("--stem-strip", default=r"__keep\w+$")
    ap.add_argument("--hops", type=int, default=2)
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    lib = NL.load_library(a.lib)

    recs = {r["view"]: r for r in load_records(a.hosts_root)}
    print(f"[注入记录] {len(recs)} 个视图（trojan "
          f"{sum(1 for r in recs.values() if r['kind'] == 'trojan')} / control "
          f"{sum(1 for r in recs.values() if r['kind'] == 'control')}）")

    anchors, grades, inst_rows, cov_rows = [], [], [], []
    for view, rec in sorted(recs.items()):
        src = a.hosts_root / rec["host"] / f"{view}.v"
        if not src.exists():
            print(f"[跳过] 缺源网表 {src}")
            continue
        g = Graph(NL.parse_netlist(src, lib))
        prof = region_profile(g, set(rec.get("new_gates") or []), a.hops)
        gs = grade_sets(g, rec, prof, a.hops)
        for row in anchors_of(g, rec, prof[f"region{a.hops}"]):
            anchors.append({"view": view, "host": rec["host"], "kind": rec["kind"],
                            "prefix": rec.get("prefix"), **row})
        grades.append({"view": view, "host": rec["host"], "kind": rec["kind"],
                       "prefix": rec.get("prefix"), "trig_style": rec.get("trig_style"),
                       "payload_style": rec.get("payload_style"), "n_trig": rec.get("n_trig"),
                       "n_inst": len(g.cell), "n_core": len(gs["core"]),
                       "n_region": len(gs["region"]), "n_boundary": len(gs["boundary"]),
                       "n_pos": len(gs["pos"]), "n_neg": len(gs["neg"]),
                       "n_unknown": len(gs["unknown"]),
                       "region_ratio": round(len(gs["region"]) / max(1, len(g.cell)), 4),
                       "union_ratio": round((len(gs["region"]) + len(gs["boundary"]))
                                            / max(1, len(g.cell)), 4),
                       "region1": len(prof["region1"]), "region2": len(prof["region2"]),
                       "region3": len(prof["region3"]),
                       "hijacked_output": rec.get("hijacked_output")})
        for name in sorted(g.cell):
            inst_rows.append({"view": view, "host": rec["host"], "inst": name,
                              "cell": g.cell[name],
                              "grade": ("pos" if name in gs["pos"] else
                                        "unknown" if name in gs["unknown"] else "neg"),
                              "in_region": int(name in gs["region"]),
                              "in_boundary": int(name in gs["boundary"]),
                              "is_injected": int(name in gs["core"])})

    labels = a.labels.split(",")
    for li, man in enumerate(a.manifests.split(",")):
        try:
            d = pd.read_csv(man)
        except Exception as ex:                                   # noqa: BLE001
            print(f"[跳过] manifest 读不了 {man}: {ex}")
            continue
        d = d[~d.file.astype(str).str.startswith("ERROR")]
        if a.limit:
            d = d.head(a.limit)
        lab = labels[li] if li < len(labels) else Path(man).parent.name
        n = 0
        for r in d.itertuples():
            host, stem, recipe = str(r.host), str(r.stem), str(r.recipe)
            view = re.sub(a.stem_strip, "", stem)
            rec = recs.get(view)
            if rec is None:
                continue
            src, cand = a.hosts_root / host / f"{view}.v", Path(str(r.file))
            if not (src.exists() and cand.exists()):
                continue
            g = Graph(NL.parse_netlist(src, lib))
            prof = region_profile(g, set(rec.get("new_gates") or []), a.hops)
            gs = grade_sets(g, rec, prof, a.hops)
            ms = re.search(r"__keep(\w+)$", stem)
            row = {"host": host, "view": view, "stem": stem, "recipe": recipe,
                   "kind": rec["kind"], "prefix": rec.get("prefix"),
                   "scheme": (ms.group(1) if ms else ""),
                   "n_region": len(gs["region"])}
            row.update(coverage_row(src, cand, lib, gs, lab))
            cov_rows.append(row)
            n += 1
        print(f"[覆盖率] {lab}: {n} 个变体")
    if not cov_rows:
        return 1

    a.out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("a2_anchors.csv", anchors), ("a2_label_grades.csv", grades),
                       ("a2_label_instances.csv", inst_rows), ("a2_coverage.csv", cov_rows)):
        pd.DataFrame(rows).to_csv(a.out_dir / name, index=False, encoding="utf-8-sig")
        print(f"[导出] {name}  {len(rows)} 行")
    c = pd.DataFrame(cov_rows)
    print("\n[覆盖率汇总]（src_root × recipe 均值）")
    print(c.groupby(["src_root", "recipe"])[["cover_core", "cover_region", "cover_pos",
                                             "cover_neg", "cover_unknown"]]
          .mean().round(4).to_string())

    # ---- 路线采用情况（**另表 a2_route_usage.csv** ✓）------------------------------
    ROUTES = ["instprov", "base", "port", "net", "name"]
    g = c.groupby(["src_root", "recipe", "scheme"])
    agg = pd.DataFrame({"n_view": g.size(), "n_conv_gates": g["n_conv_gates"].sum(),
                        "core_total": g["core_total"].sum(),
                        "core_aligned": g["core_aligned"].sum(),
                        "core_in_conv_names": g["core_in_conv_names"].sum(),
                        "core_in_conv_text": g["core_in_conv_text"].sum(),
                        "n_conv_bound": g["n_conv_bound"].sum(),
                        "n_conv_unbound": g["n_conv_unbound"].sum()})
    for r in ROUTES:
        agg[f"by_{r}"] = g[f"by_{r}"].sum()
        agg[f"core_by_{r}"] = g[f"core_by_{r}"].sum()
    for r in ROUTES:
        agg[f"only_{r}"] = g[f"only_{r}"].sum()
        agg[f"core_only_{r}"] = g[f"core_only_{r}"].sum()
    agg = agg.reset_index()
    tot = agg[[f"by_{r}" for r in ROUTES]].sum(axis=1)
    ct = agg[[f"core_by_{r}" for r in ROUTES]].sum(axis=1)
    for r in ROUTES:
        agg[f"share_{r}"] = (agg[f"by_{r}"] / tot.where(tot > 0, 1)).round(4)
        agg[f"core_share_{r}"] = (agg[f"core_by_{r}"] / ct.where(ct > 0, 1)).round(4)
    agg.to_csv(a.out_dir / "a2_route_usage.csv", index=False, encoding="utf-8-sig")
    print(f"[导出] a2_route_usage.csv  {len(agg)} 行")
    ot = agg[[f"only_{r}" for r in ROUTES]].sum(axis=1)
    cot = agg[[f"core_only_{r}" for r in ROUTES]].sum(axis=1)
    for r in ROUTES:
        agg[f"only_share_{r}"] = (agg[f"only_{r}"] / ot.where(ot > 0, 1)).round(4)
        agg[f"core_only_share_{r}"] = (agg[f"core_only_{r}"] / cot.where(cot > 0, 1)).round(4)
    agg.to_csv(a.out_dir / "a2_route_usage.csv", index=False, encoding="utf-8-sig")
    print("\n[唯一路线]（只有该路线能绑上的源门数 ✓ = 必要性 ✓）")
    print(agg[["src_root", "recipe", "scheme"] + [f"only_{r}" for r in ROUTES]
              + [f"core_only_{r}" for r in ROUTES]].to_string(index=False))
    print("\n[路线采用]（src_root × recipe × scheme 求和；core_by_* = 只看注入区 ✓）")
    print(agg[["src_root", "recipe", "scheme", "core_total", "core_aligned",
               "core_in_conv_text"] + [f"core_by_{r}" for r in ROUTES]
              + [f"core_share_{r}" for r in ROUTES]].to_string(index=False))
    print("\n[路线采用·全图]（by_* 求和 / 占比 ✓）")
    print(agg[["src_root", "recipe", "scheme"] + [f"by_{r}" for r in ROUTES]
              + [f"share_{r}" for r in ROUTES]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
