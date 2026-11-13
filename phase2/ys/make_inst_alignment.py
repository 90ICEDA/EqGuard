# -*- coding: utf-8 -*-
"""
make_inst_alignment.py —— **P2：实例级**标签对齐（A3 收尾）。

为什么要有它（取代 `make_name_alignment.py` 在 ys 变体上的用法）：
    下游图网络的**节点 = 实例（门）**，信号名本身不是特征。
    老脚本靠「实例名相同」+「输出网名相同」两条路建 `node_alignment`，
    于是覆盖率被名字绑死：A1 实测 abc 22.2% / aig 11.6% / nand·opt 0%（见 `a1_labeling.csv`）✗。
    但实测（`meas_a3_inst_ident.py`）木马实例其实**能 5/5 找回** ✓ —— 缺的是对齐脚本没走溯源：

      A｜`map.json.inst_prov`：门实例 → 它驱动的**原始网名**（P1 新加 ✓，最可靠）
      B｜门名 `g_{base}_{k}` 的 base → 原网名（无 inst_prov 时的等价回退 ✓）
      C｜`\\实例.端口` 遗留端口名 → 源网表里该端口连的网 → 源驱动实例 ✓
      （另保留老的两条路：输出网名同名 D、实例名同名 E，便于对照与兼容）

输出与老脚本**同构**（`node_alignment: {源实例名: [转换后实例名, ...]}` + 其余字段），
所以可以直接放进 fold 的 `rw_mappings/`（配 `register_into_fold.py`）。

用法（A3 的 keep 对照盘子）：
    py phase2/ys/make_inst_alignment.py \
        --hosts-root generate_trans/hosts_bt2 \
        --manifest generate_trans/keepab/conv/convert_manifest.csv \
        --out-dir generate_trans/keepab/mappings \
        --stem-strip "__keep(none|cur|bnd|full)$" \
        --report 10.15/01_数据与标签/A3_keep三方案/tables/a3_inst_alignment.csv
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL  # noqa: E402

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"
GEN_RE = re.compile(r"^g_(?P<base>.+)_(?P<k>\d+)$")       # Conv.cell: f"g_{base}_{k}"
GATE_RE = re.compile(r"^\s*(\w+)\s+([\\\w.$\[\]]+)\s*\((.*)\)\s*$", re.S)
CONN_RE = re.compile(r"\.\s*(\w+)\s*\(\s*([^)]*)\)")
KW = {"module", "wire", "assign", "input", "output", "reg"}


def norm(n: str) -> str:
    n = str(n).strip()
    return n[1:] if n.startswith("\\") else n


class UF:
    """并查集：把 `assign a = b;` 的别名网并成一组（等价网）。"""

    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def src_facts(src: Path, lib: dict) -> dict:
    """源视图：网（含别名归一）→ 驱动实例；`实例.端口` → 该端口连的网。"""
    nl = NL.parse_netlist(src, lib)
    uf = UF()
    for lhs, rhs in nl.assigns:
        uf.union(norm(lhs), norm(rhs))
    net2inst, port2net = {}, {}
    for i in nl.insts:
        for port, n in i.conns:
            port2net[f"{i.name}.{port}"] = uf.find(norm(n))
        for _p, n in nl.outs(i):                  # 需要 lib 才能认出输出端口
            net2inst.setdefault(uf.find(norm(n)), i.name)
    return {"nl": nl, "uf": uf, "net2inst": net2inst, "port2net": port2net,
            "names": {str(i.name) for i in nl.insts}}


def cand_facts(cand: Path) -> dict:
    """转换后变体：门实例（**文本级**解析，容忍 `g__X.A_12` 这种点号名）+ 输出网 → 驱动门。"""
    text = cand.read_text(encoding="utf-8", errors="replace")
    gates = []
    for st in text.split(";"):
        m = GATE_RE.match(st)
        if not m or m.group(1) in KW:
            continue
        conns = CONN_RE.findall(m.group(3))
        if conns:                                  # Conv.cell 保证末位连接是输出
            gates.append((m.group(2), conns[-1][1].strip()))
    net2gate = {}
    for name, out in gates:
        net2gate.setdefault(norm(out), name)
    # 顺着别名 assign 追到底（转换器会给改写保留 `assign TrojanA_p0 = TrojanA_p0__g213;`）
    alias = {norm(l): norm(r) for l, r in NL.parse_netlist(cand, None).assigns
             if re.fullmatch(r"[\\\w/$\[\]:.]+", str(r).strip())}
    for l, r in alias.items():
        cur, k = r, 0
        while cur in alias and k < 6:
            cur, k = alias[cur], k + 1
        if l not in net2gate and cur in net2gate:
            net2gate[l] = net2gate[cur]
    return {"gates": gates, "net2gate": net2gate, "names": {n for n, _ in gates}}


def resolve(net: str, srcf: dict) -> str | None:
    """一个名字（网名 或 `实例.端口`）→ 源侧驱动实例名。"""
    if not net:
        return None
    x = norm(net)
    if x in srcf["port2net"]:                      # ③ 遗留端口名
        return srcf["net2inst"].get(srcf["port2net"][x])
    r = srcf["uf"].find(x)
    return srcf["net2inst"].get(r)


def build_align(srcf: dict, candf: dict, inst_prov: dict, focus: set | None = None,
                pair_routes: dict | None = None) -> tuple:
    """→ (align, legacy_align, hits)：全部路线的对齐 + 只有老路线(网名/实例名)的对齐。

    `focus` 非空时：**只统计「源实例落在 focus 内」的路线命中**（用于"只看注入区"的归因 ✓）；
    `align` / `legacy` 本身**不受影响** ✗ → 既有产物（A3 的 mapping 与表）不变 ✓。
    """
    align, legacy, hits = {}, {}, {"instprov": 0, "base": 0, "port": 0, "net": 0, "name": 0}
    # pair_routes（可选 ✓）：记录每个 (源实例, 变换后实例) 对命中的**全部**路线 ✓
    #   → 用来算「某个源门是否**只能**靠某条路线绑上」✓（必要性 ✓；A2 的 only_* / core_only_* ✓）

    def add(tgt, s, t, route):
        if tgt is align and pair_routes is not None:
            pair_routes.setdefault((s, t), set()).add(route)   # 去重前先记路线 ✓
        if t in tgt.setdefault(s, []):
            return
        tgt[s].append(t)
        if tgt is align and (focus is None or s in focus):
            hits[route] += 1

    # D｜输出网名同名（老路线）
    for net in set(srcf["net2inst"]) & set(candf["net2gate"]):
        add(align, srcf["net2inst"][net], candf["net2gate"][net], "net")
        add(legacy, srcf["net2inst"][net], candf["net2gate"][net], "net")
    # E｜实例名同名（老路线；yosys 常把触发器这类实例名保住）
    for nm in srcf["names"] & candf["names"]:
        add(align, nm, nm, "name")
        add(legacy, nm, nm, "name")
    # A/B/C｜**溯源**（新路线，按实例绑，不依赖名字）
    for gname, onet in candf["gates"]:
        if gname in inst_prov:                     # A：P1 的 inst_prov
            s = resolve(inst_prov[gname], srcf)
            if s:
                add(align, s, gname, "instprov")
                continue
        m = GEN_RE.match(gname)                    # B：门名里的 base（无 inst_prov 时的回退）
        if m:
            s = resolve(m.group("base"), srcf)
            if s:
                add(align, s, gname, "base")
                continue
        s = resolve(onet, srcf)                    # C：输出网 / `实例.端口`
        if s:
            add(align, s, gname, "port")
    return align, legacy, hits


def prefix_of(prov_json: Path, view: str) -> str | None:
    """从 `provenance.json` 取该视图的名字前缀（判木马/对照锚点用）。"""
    if not prov_json.exists():
        return None
    try:
        for rec in json.loads(prov_json.read_text(encoding="utf-8")):
            if rec.get("view") == view:
                return rec.get("prefix")
    except Exception:                                            # noqa: BLE001
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--manifest", type=Path,
                    default=ROOT / "generate_trans" / "yslib_keep" / "convert_manifest.csv")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="默认 <hosts-root>/<host>/rw_mappings（与老脚本一致）")
    ap.add_argument("--stem-strip", default="",
                    help=r"正则：从 manifest.stem 去掉后缀定位源视图，如 __keep(none|cur|bnd|full)$")
    ap.add_argument("--report", type=Path, default=None, help="统计表 CSV（含新旧路线对照）")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    lib = NL.load_library(a.lib)
    H = a.hosts_root.resolve()
    d = pd.read_csv(a.manifest)
    d = d[~d.file.astype(str).str.startswith("ERROR")]
    if a.limit:
        d = d.head(a.limit)

    rows = []
    for r in d.itertuples():
        host, stem, recipe = str(r.host), str(r.stem), str(r.recipe)
        sstem = re.sub(a.stem_strip, "", stem) if a.stem_strip else stem
        src, cand = H / host / f"{sstem}.v", Path(str(r.file))
        if not src.exists() or not cand.exists():
            print(f"[跳过] {host}/{stem}/{recipe}：缺源网表或缺产物")
            continue
        mp_p = cand.with_suffix(".map.json")
        mp = json.loads(mp_p.read_text(encoding="utf-8")) if mp_p.exists() else {}
        inst_prov = {str(k): str(v) for k, v in (mp.get("inst_prov") or {}).items()}
        srcf, candf = src_facts(src, lib), cand_facts(cand)
        align, legacy, hits = build_align(srcf, candf, inst_prov)

        pre = prefix_of(H / host / "provenance.json", sstem)

        def is_anchor(nm: str) -> bool:
            return nm.startswith(("Trojan", "Ctl", "Ctrl")) or bool(pre) and nm.startswith(str(pre))

        tro = {n for n in srcf["names"] if is_anchor(n)}
        tro_new, tro_old = {k for k in align if k in tro}, {k for k in legacy if k in tro}
        aligned_src = {k for k in align if k in srcf["names"]}

        out_dir = a.out_dir if a.out_dir else H / host / "rw_mappings"
        out_dir.mkdir(parents=True, exist_ok=True)
        rw_view = f"{stem}__ys_{recipe}"
        obj = {"src_verilog": f"{sstem}.v", "operator_family": f"ys_{recipe}",
               "src_view": sstem, "node_alignment": align,
               "n_rewritten": max(0, len(candf["names"]) - len(align)),
               "n_split_objects": 0, "skipped": {},
               "note": ("实例级对齐（make_inst_alignment.py）：inst_prov / 门名 base / `\\实例.端口` "
                        "三条溯源路 + 老路线（输出网名、实例名同名）"),
               "hit_by_instprov": hits["instprov"], "hit_by_base": hits["base"],
               "hit_by_port": hits["port"], "hit_by_net": hits["net"], "hit_by_name": hits["name"]}
        (out_dir / f"{rw_view}.json").write_text(
            json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")

        rows.append({"host": host, "stem": stem, "recipe": recipe, "rw_view": rw_view,
                     "n_src_inst": len(srcf["names"]), "n_cand_gates": len(candf["gates"]),
                     "n_inst_prov": len(inst_prov),
                     "n_align_keys": len(align), "n_legacy_keys": len(legacy),
                     "n_src_inst_aligned": len(aligned_src),
                     "cov_src_inst": round(len(aligned_src) / max(1, len(srcf["names"])), 4),
                     "n_trojan_src": len(tro), "n_trojan_aligned": len(tro_new),
                     "n_trojan_legacy": len(tro_old),
                     "by_instprov": hits["instprov"], "by_base": hits["base"],
                     "by_port": hits["port"], "by_net": hits["net"], "by_name": hits["name"]})
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    print(f"\n[OK] 写了 {len(t)} 个 mapping；"
          f"木马/对照实例：新旧路线 {int(t.n_trojan_aligned.sum())} vs 老路线 {int(t.n_trojan_legacy.sum())}")
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        t.to_csv(a.report, index=False, encoding="utf-8-sig")
        print(f"[导出] {a.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


