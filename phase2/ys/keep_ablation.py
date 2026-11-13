# -*- coding: utf-8 -*-
"""
keep_ablation.py —— **A3 小规模试点**：keep 策略对"生成网表"的影响对照。

任务书 一·3 要求比较三种方案：**全区域 keep / 只 keep 关键边界 / 不 keep**，
并统计 标签覆盖率、变换后结构差异、CEC 成功率（模型效果留给 A3 全量三 seed）。

做法（关键：**同一份源网表 + 同一批 pass，只有 keep 集合不同**）：
    对每个 (视图, 配方) 生成 4 个变体：
      none : 完全不 keep（yosys 默认）
      cur  : 只 keep 木马/对照相关网（= 现状流水线 keep_prep_all 的做法）
      bnd  : 只 keep 边界 = 寄存器输出网(Q) + 主输出网 + 木马/对照相关网
      full : 全网 keep（setattr -set keep 1 w:*）
    keep 指令插在 `proc` 之后、任何优化 pass **之前**（顺序决定名字能否活下来，
    与 _stamp_provenance.py 的实测一致：插早才有 96%）。

每个变体：写网表 → 与原网表做 CEC（direct_cec.py）→ 量 6 组数：
    1) 规模：实例数 / 网数 / 行数 / 字节
    2) 名字存活：实例名存活率、网名存活率
    3) **木马锚点存活**：Trojan/Ctl 前缀的实例名 + 网名 存活数（= 标签能否传过去）
    4) 寄存器边界存活：源 DFF 的 Q 网名存活率
    5) 变换强度代理：变体里"新造实例名"占比（越高 = 改写越彻底）
    6) CEC 结果 + 耗时

用法（小规模先冒烟）：
    py phase2/ys/keep_ablation.py --views rs232t1000__injalpha_d1_s42 --recipes abc
    py phase2/ys/keep_ablation.py --recipes abc,nand --schemes none,cur,bnd,full
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL  # noqa: E402

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"
VALI_WSL = "/mnt/c/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali"
WSL_ROOT = _eqguard_path('', wsl=True)

RECIPES = {
    "id": "flatten",
    "rt": "flatten",
    "opt": "flatten\nopt -full",
    "abc": "flatten\ntechmap\nopt -full\nabc -g AND,OR,XOR,XNOR,MUX",
    "aig": "flatten\ntechmap\nopt -full\naigmap\nopt_clean",
    "nand": "flatten\ntechmap\nopt -full\nabc -g NAND,NOR",
}
NO_OPT = {"rt"}
SCHEMES = ("none", "cur", "bnd", "full")
ANCHOR_PREFIX = ("Trojan", "Ctl")
ABC_SCRIPT: str | None = None      # --abc-script 覆盖：把 abc 的 `-g AND,...` 换成 `-script ...`


def apply_abc_script(script: str | None) -> None:
    """把 `--abc-script` 注入 RECIPES['abc']（D2：未知配方泛化的入口 ✓）。"""
    global ABC_SCRIPT
    ABC_SCRIPT = script.strip() if script else None
    if not ABC_SCRIPT:
        return
    if ";" not in ABC_SCRIPT:
        raise SystemExit("[ERROR] --abc-script 必须是 yosys abc 的分号脚本 ✓（例：+strash;ifraig;scorr;dc2;dretime）")
    RECIPES["abc"] = "flatten\ntechmap\nopt -full\nabc -script " + ABC_SCRIPT


def wsl(path: Path | str) -> str:
    p = str(Path(path).resolve()).replace("\\", "/")
    return p.replace("C:/", "/mnt/c/", 1) if p[1:3] == ":/" else p


def load_prefixes(hosts_root: Path) -> dict:
    """{view: 名字前缀}，从 provenance.json 读。"""
    out = {}
    for hd in sorted(p for p in hosts_root.iterdir() if p.is_dir()):
        pj = hd / "provenance.json"
        if not pj.exists():
            continue
        for rec in json.loads(pj.read_text(encoding="utf-8")):
            out[rec.get("view")] = rec.get("prefix")
    return out


def is_anchor(name: str, prefix: str | None) -> bool:
    """木马/对照锚点：`Trojan*` / `Ctl*` 一族，或该视图自己的前缀（如 TrojanA）。"""
    if name.startswith(ANCHOR_PREFIX):
        return True
    return bool(prefix) and name.startswith(str(prefix))


def nets_of(nl) -> set:
    return {n for i in nl.insts for _p, n in nl.outs(i)}


def keep_sets(src: Path, lib, prefix: str | None) -> dict:
    """三种 keep 集合（full 不用集合，直接 w:*）。"""
    nl = NL.parse_netlist(src, lib)
    nets = nets_of(nl)
    insts = {i.name for i in nl.insts}
    anchor_nets = {n for n in nets if is_anchor(n, prefix)}
    anchor_insts = {i for i in insts if is_anchor(i, prefix)}
    # 木马/对照实例参与的所有网（现状做法）
    for i in nl.insts:
        if is_anchor(i.name, prefix):
            anchor_nets |= {n for _p, n in i.conns}
    dff_q = set()
    for i in nl.insts:
        if "DFF" in i.gate.upper():
            for p, n in i.conns:
                if p.upper() in ("Q", "QN"):
                    dff_q.add(n)
    out_nets = set(nl.outputs)
    return {
        "cur": sorted(anchor_nets | anchor_insts),
        "bnd": sorted(anchor_nets | anchor_insts | dff_q | out_nets),
        "n_anchor_nets": len(anchor_nets), "n_anchor_insts": len(anchor_insts),
        "n_dff_q": len(dff_q), "n_out_ports": len(out_nets), "n_nets": len(nets),
    }


def keep_cmds(scheme: str, sets: dict) -> list:
    if scheme == "none":
        return []
    if scheme == "full":
        return ["setattr -set keep 1 w:*"]
    names = sets[scheme]
    cmds = []
    for i in range(0, len(names), 40):                      # 分块，避免命令行过长
        chunk = " ".join(f"w:{n}" for n in names[i:i + 40])
        cmds.append(f"setattr -set keep 1 {chunk}")
    return cmds


def yosys_script(src: Path, mod: str, recipe: str, scheme: str, sets: dict, outv: Path) -> str:
    body = [f"read_verilog -sv {VALI_WSL}/verilog_lib.v",
            f"read_verilog -sv {wsl(src)}",
            f"hierarchy -top {mod}"]
    # keep 越早插越有效（流水线里 keep 是写在**源网表**里的，等价于在最前面就生效）
    body += keep_cmds(scheme, sets)
    # proc + 一次 opt -full：与 build_yosys_netlists.py 的顺序保持一致
    # （少了这一次，flatten 后的 `\U27.A0` 这类点号网名会残留 → 转换产物非法 → CEC 建不起 miter）
    body += ["proc", "opt -full"]
    body += RECIPES[recipe].split("\n")
    if recipe not in NO_OPT:
        # 只 opt_clean（与 build_yosys_netlists.py 一致）：别再补一次 `opt -full`，
        # 它会在 abc 之后继续利用 X 条件做优化，实测会让转换后产物 CEC 出现 unproven。
        body += ["opt_clean"]
    body += [f"rename -top {outv.stem}", f"write_verilog -noattr {wsl(outv)}"]
    return "\n".join(body) + "\n"


def tokens_has(text: str, name: str) -> bool:
    """名字是否以独立标识符形式出现在产物文本里。

    两个坑：
      · 不能只看子串（`n12` 会被 `n123` 命中）；
      · yosys 会为**被删掉的单元**留下端口网 `\\TrojanAT1.A` / `assign \\TrojanAT1.A = 1'hx;`，
        只看词边界会把它们当成"锚点活下来了"→ 必须同时排除前后紧跟 `.` 的情况。
    """
    return re.search(r"(?<![\w.])" + re.escape(name) + r"(?![\w.])", text) is not None


def text_token_set(text: str) -> set:
    """把文本切成"词袋"，供 O(1) 查表（等价于 `tokens_has` 的语义 ✓）。

    规则与 `tokens_has` 一致：
      · 名字是**完整 token**（`n12` 不会被 `n123` 命中）；
      · 前后紧邻 `.` 的 token 视为"被删单元的端口网"（`\\TrojanAT1.A`），**不算存活**；
      · 允许名字里带 `[...]` 下标（`mem[3]`）。
    """
    out = set()
    for m in re.finditer(r"[\w$]+(?:\[[^\]\n]*\])?", text):
        s, e = m.span()
        if (s > 0 and text[s - 1] == ".") or (e < len(text) and text[e] == "."):
            continue
        out.add(m.group())
    return out


def text_surv(src: Path, cand: Path, lib, prefix: str | None, nl=None) -> dict:
    """**按文本**的名字存活（对应"标签能否绑定"；不受 yosys 内部单元影响）。

    yosys 的 abc/aig 产物是内部单元（`$_AND_`）+ `_000_` 网，直接解析实例只能看到
    残余的 DFF → 会得出"存活 7%"的假象。真实流水线随后要过 `assign_to_gates.py`
    把内部单元换成库单元，而**被 keep 的网名会以 assign 别名保留** → 所以按文本量才对。

    性能：早先对每个名字跑一次全文正则 ✗（8.7k 名字 × 2.5 MB ≈ 数十 GB 扫描 ✗），
    现在文档只切一次词袋 ✓ 再查表 ✓（语义与 `tokens_has` 相同 ✓）。
    """
    text = cand.read_text(encoding="utf-8", errors="replace")
    tok = text_token_set(text)
    nl = nl if nl is not None else parse_cached(src, lib)
    io = {i.name for i in nl.insts}
    no = nets_of(nl)
    dff_q = set()
    for i in nl.insts:
        if "DFF" in i.gate.upper():
            dff_q |= {n for p, n in i.conns if p.upper() in ("Q", "QN")}
    a_i = {x for x in io if is_anchor(x, prefix)}
    a_n = {x for x in no if is_anchor(x, prefix)}
    return {
        "surv_inst_text": sum(x in tok for x in io) / max(1, len(io)),
        "surv_net_text": sum(x in tok for x in no) / max(1, len(no)),
        "anchor_inst_text": sum(x in tok for x in a_i),
        "anchor_net_text": sum(x in tok for x in a_n),
        "anchor_text_alive": sum(x in tok for x in a_i | a_n),
        "anchor_text_surv": (sum(x in tok for x in a_i | a_n)
                             / max(1, len(a_i | a_n))),
        "dffq_text_surv": sum(x in tok for x in dff_q) / max(1, len(dff_q)),
    }


def measure(src: Path, cand: Path, lib, sets: dict, prefix: str | None) -> dict:
    """量 6 组数：规模 / 名字存活 / 木马锚点 / 寄存器边界 / 变换强度代理 / 门类型。"""
    nso, nsc = parse_cached(src, lib), NL.parse_netlist(cand, lib)
    io, it = {i.name for i in nso.insts}, {i.name for i in nsc.insts}
    no, nt = nets_of(nso), nets_of(nsc)
    a_i = {x for x in io if is_anchor(x, prefix)}
    a_n = {x for x in no if is_anchor(x, prefix)}
    dff_q = set()
    for i in nso.insts:
        if "DFF" in i.gate.upper():
            dff_q |= {n for p, n in i.conns if p.upper() in ("Q", "QN")}
    kinds = pd.Series([i.gate for i in nsc.insts]).value_counts()
    return {
        "src_insts": len(io), "src_nets": len(no),
        "out_insts": len(it), "out_nets": len(nt),
        "inst_ratio": len(it) / max(1, len(io)),
        "surv_inst": len(io & it) / max(1, len(io)),
        "surv_net": len(no & nt) / max(1, len(no)),
        "anchor_inst_total": len(a_i), "anchor_inst_alive": len(a_i & it),
        "anchor_net_total": len(a_n), "anchor_net_alive": len(a_n & nt),
        "anchor_alive": len(a_i & it) + len(a_n & nt),
        "anchor_total": len(a_i) + len(a_n),
        "anchor_surv": (len(a_i & it) + len(a_n & nt)) / max(1, len(a_i) + len(a_n)),
        "dffq_total": len(dff_q), "dffq_alive": len(dff_q & nt),
        "dffq_surv": len(dff_q & nt) / max(1, len(dff_q)),
        "new_name_ratio": 1 - len(it & io) / max(1, len(it)),
        "top_cells": " ".join(f"{k}:{v}" for k, v in kinds.head(3).items()),
        "n_cells": int(kinds.sum()),
    }


def cec_status(txt: Path) -> str:
    if not txt.exists():
        return "MISSING"
    ls = [ln for ln in txt.read_text(encoding="utf-8", errors="replace").splitlines() if "CEC" in ln]
    return "?" if not ls else ("PASS" if any("PASS" in ln for ln in ls) else "FAIL")


def names_of(p: Path, lib) -> set:
    return {i.name for i in NL.parse_netlist(p, lib).insts} if p.exists() else set()


_PARSE_CACHE: dict = {}


def parse_cached(p: Path, lib):
    """按 (路径, 大小, mtime) 缓存解析结果 ✓ —— 单行要解析 src 两次 ✗（慢 ✗）。"""
    st = p.stat()
    key = (str(p), st.st_size, int(st.st_mtime))
    hit = _PARSE_CACHE.get(key)
    if hit is None:
        hit = NL.parse_netlist(p, lib)
        if len(_PARSE_CACHE) > 12:
            _PARSE_CACHE.clear()
        _PARSE_CACHE[key] = hit
    return hit


def measure_all(jobs: list, sets_cache: dict, prefixes: dict, lib, a) -> pd.DataFrame:
    """在**转换后**的网表上量（转换器才是真正改写名字的那一步）。"""
    rows = []
    for j in jobs:
        new = f"{j['stem']}__ys_{j['recipe']}"
        secs, sf = 0, a.out / "logs" / f"{new}.secs"
        if sf.exists():
            try:
                secs = int(sf.read_text().strip() or 0)
            except ValueError:
                secs = 0
        rc, rf = -1, a.out / "logs" / f"{new}.rc"
        if rf.exists():
            try:
                rc = int(rf.read_text().strip())
            except ValueError:
                rc = -1
        conv = j.get("conv")
        # D2 ✓：名字存活必须在**配方原产物**上量 ✗→✓（转换器会重命名全部节点 ✗，
        # 在 conv 产物上量会让所有配方得到同一个数 ✗ —— 2026-10-19 实测踩过 ✗）
        if getattr(a, "measure_raw", False):
            use = j["outv"]
        else:
            use = conv if (conv is not None and conv.exists()) else j["outv"]
        rec = {"view": j["view"], "recipe": j["recipe"], "scheme": j["scheme"],
               "abc_script": (ABC_SCRIPT if j["recipe"] == "abc" else ""),
               "cec_raw": cec_status(a.out / "logs" / f"cec_{new}.txt"),
               "cec": cec_status(a.out / "logs" / f"cecconv_{new}.txt"),
               "conv_ok": bool(conv is not None and conv.exists()),
               "secs": secs, "yosys_rc": rc,
               "bytes": use.stat().st_size if use.exists() else 0,
               "lines": (len(use.read_text(encoding="utf-8", errors="replace").splitlines())
                         if use.exists() else 0),
               "keep_list": len(sets_cache[j["view"]].get(j["scheme"]) or [])}
        if use.exists():
            rec.update(measure(j["src"], use, lib, sets_cache[j["view"]],
                               prefixes.get(j["view"])))
            rec.update(text_surv(j["src"], use, lib, prefixes.get(j["view"]),
                                 nl=parse_cached(j["src"], lib)))
        rows.append(rec)
    d = pd.DataFrame(rows)
    cm = a.out / "conv" / "convert_manifest.csv"     # 转换器自己的体检表
    if cm.exists():
        c = pd.read_csv(cm).rename(columns={"stem": "stem_key"})
        d["stem_key"] = d["view"] + "__keep" + d["scheme"]
        d = d.merge(c[["stem_key", "recipe", "n_assign_in", "n_converted", "n_inst_out",
                       "clean", "dangling", "multi", "undriven_out"]],
                    on=["stem_key", "recipe"], how="left")
    return d


def summarize(d: pd.DataFrame, a, lib) -> int:
    """加一列「与同配方 none 变体的实例名重合度」= keep 究竟把结构改了多少。"""
    ov = []
    for (v, r), gg in d.groupby(["view", "recipe"]):
        base = a.out / "conv" / a.host / f"{v}__keepnone__ys_{r}.v"
        if not base.exists():
            base = a.out / "out" / a.host / f"{v}__keepnone__ys_{r}.v"
        nb = names_of(base, lib)
        for rec in gg.to_dict("records"):
            cand = a.out / "conv" / a.host / f"{v}__keep{rec['scheme']}__ys_{r}.v"
            if not cand.exists():
                cand = a.out / "out" / a.host / f"{v}__keep{rec['scheme']}__ys_{r}.v"
            ns = names_of(cand, lib)
            ov.append({"view": v, "recipe": r, "scheme": rec["scheme"],
                       "overlap_with_none": (len(ns & nb) / max(1, len(ns))) if nb else float("nan")})
    d = d.merge(pd.DataFrame(ov), on=["view", "recipe", "scheme"], how="left")
    d.to_csv(a.tables / "a3_keep_pilot.csv", index=False, encoding="utf-8-sig")
    keys = [k for k in ["yosys_rc", "conv_ok", "surv_inst_text", "surv_net_text",
                        "anchor_text_surv", "anchor_text_alive", "dffq_text_surv",
                        "n_assign_in", "n_converted", "n_inst_out", "dangling", "multi",
                        "undriven_out", "overlap_with_none", "inst_ratio", "new_name_ratio",
                        "out_insts", "lines", "bytes", "secs"] if k in d.columns]
    if d.empty or not keys:
        print("[WARN] 没有可汇总的数据（先看日志里 yosys / 转换 / CEC 是否成功）")
        return 1
    g = d.groupby(["recipe", "scheme"])
    s = (g[keys].mean()
         .join(g.cec.apply(lambda x: f"{int((x == 'PASS').sum())}/{len(x)}").rename("cec_conv"))
         .join(g.cec_raw.apply(lambda x: f"{int((x == 'PASS').sum())}/{len(x)}").rename("cec_raw"))
         .reset_index())
    s.to_csv(a.tables / "a3_keep_pilot_summary.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 240)
    print("\n=== A3 试点汇总（按 配方 × keep 方案）===")
    print(s.round(3).to_string(index=False))
    print(f"[导出] {a.tables}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="A3 试点：keep 策略对照（none / cur / bnd / full）")
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt2")
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--views", default="rs232t1000__injalpha_d1_s42,rs232t1000__ctlmatcha_d1_s42")
    ap.add_argument("--recipes", default="abc")
    ap.add_argument("--schemes", default="none,cur,bnd,full")
    ap.add_argument("--out", type=Path, default=ROOT / "generate_trans" / "keepab")
    ap.add_argument("--tables", type=Path,
                    default=ROOT / "10.15" / "01_数据与标签" / "A3_keep三方案" / "tables")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--abc-script", default=None,
                    help="D2：覆盖 abc 配方（yosys `abc -script` 的分号脚本 ✓）")
    ap.add_argument("--measure-raw", action="store_true",
                    help="D2：在**配方原产物**（yosys 输出）上量名字存活 ✓（默认在转换器产物上 ✗）")
    ap.add_argument("--skip-cec", action="store_true")
    a = ap.parse_args()
    apply_abc_script(a.abc_script)

    lib = NL.load_library(LIB_DEFAULT)
    prefixes = load_prefixes(a.hosts_root)
    views = [v.strip() for v in a.views.split(",") if v.strip()]
    recipes = [r.strip() for r in a.recipes.split(",") if r.strip()]
    schemes = [s.strip() for s in a.schemes.split(",") if s.strip()]
    for d in ("out", "logs"):
        (a.out / d).mkdir(parents=True, exist_ok=True)
    a.tables.mkdir(parents=True, exist_ok=True)

    jobs, sets_cache = [], {}
    for v in views:
        src = a.hosts_root / a.host / f"{v}.v"
        if not src.exists():
            print(f"[WARN] 缺 {src}")
            continue
        sets = keep_sets(src, lib, prefixes.get(v))
        sets_cache[v] = sets
        print(f"[keep集] {v}: 木马/对照 网{int(sets['n_anchor_nets'])} "
              f"实例{int(sets['n_anchor_insts'])}｜cur {len(sets['cur'])} 名｜"
              f"bnd {len(sets['bnd'])} 名（DFF-Q {int(sets['n_dff_q'])} + "
              f"输出接口 {int(sets['n_out_ports'])}）｜总网 {sets['n_nets']}")
        for r in recipes:
            for s in schemes:
                stem = f"{v}__keep{s}"
                outv = a.out / "out" / a.host / f"{stem}__ys_{r}.v"
                ys = a.out / "logs" / f"{stem}__ys_{r}.ys"
                ys.write_text(yosys_script(src, v, r, s, sets, outv),
                              encoding="utf-8", newline="\n")
                jobs.append({"view": v, "recipe": r, "scheme": s, "src": src,
                             "stem": stem, "outv": outv, "ys": ys,
                             "conv": a.out / "conv" / a.host / f"{stem}__ys_{r}.v"})
    if not jobs:
        print("[ERROR] 没有任务")
        return 1

    # 转换器（assign_to_gates.py）按约定从 <ys-root>/<host>/<stem>__ys_<recipe>.v 读文件，
    # 并且只处理 cec 列含 PASS 的行。这里的 cec 是"放过闸门"的哨兵值：
    # **真正的 CEC 按流水线的口径在转换之后跑**（转换器会把内部单元换成库单元，
    # 等价性以转换后为准），结果记在同一行的 cec_after_conv 列里。
    (a.out / "out" / a.host).mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"host": a.host,
                   "kind": ("trojan" if "__inj" in j["view"] else "control"),
                   "stem": j["stem"], "recipe": j["recipe"], "rc": 0, "bytes": 0,
                   "always": 0, "cells": 0, "cec": "PASS(bypass-gate)", "secs": 0}
                  for j in jobs]).to_csv(a.out / "ys_manifest.csv", index=False,
                                         encoding="utf-8-sig")

    sh = ["#!/bin/bash", "set +e", f"cd {WSL_ROOT}"]
    for j in jobs:
        new = j["outv"].stem
        sh += ["t0=$(date +%s)",
               f"timeout {a.timeout} yosys -q -s {wsl(j['ys'])} "
               f"-l {wsl(a.out)}/logs/{new}.log > {wsl(a.out)}/logs/{new}.stdout 2>&1",
               f"echo $? > {wsl(a.out)}/logs/{new}.rc",
               f"t1=$(date +%s); echo $((t1-t0)) > {wsl(a.out)}/logs/{new}.secs",
               f'echo "[{new}] yosys_rc=$(cat {wsl(a.out)}/logs/{new}.rc) secs=$((t1-t0))"']
        if not a.skip_cec:
            sh.append(f"python3 generate_trans/cec/direct_cec.py --golden {wsl(j['src'])} "
                      f"--candidate {wsl(j['outv'])} --vali-dir {VALI_WSL} "
                      f"--timeout {a.timeout} --log {wsl(a.out)}/logs/cec_{new}.log "
                      f"> {wsl(a.out)}/logs/cec_{new}.txt 2>&1")
    gen = a.out / "_run.sh"
    gen.write_text("\n".join(sh) + "\n", encoding="utf-8", newline="\n")
    print(f"[run] {len(jobs)} 个作业（yosys{' + CEC' if not a.skip_cec else ''}）")
    r = subprocess.run(["wsl", "-e", "bash", "-c", f"sed 's/\\r$//' {wsl(gen)} | bash"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "")[-4000:])
    if r.stderr:
        print("[stderr]", r.stderr[-1500:])

    # ② 转换器（必须在 **Windows 侧** 跑：它用 pandas，WSL 的 python3 没装）
    cv = subprocess.run([sys.executable, "-X", "utf8",
                         str(ROOT / "phase2" / "ys" / "assign_to_gates.py"),
                         "--manifest", str(a.out / "ys_manifest.csv"),
                         "--ys-root", str(a.out / "out"),
                         "--out-root", str(a.out / "conv")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    (a.out / "logs" / "convert.txt").write_text((cv.stdout or "") + (cv.stderr or ""),
                                                encoding="utf-8")
    print(f"[convert] rc={cv.returncode}（日志 logs/convert.txt）"
          + ((cv.stdout or "").strip().splitlines()[-1] if (cv.stdout or "").strip() else ""))

    # ③ 转换**之后**再 CEC（流水线口径：等价性以转换后为准）
    if not a.skip_cec:
        sh2 = ["#!/bin/bash", "set +e", f"cd {WSL_ROOT}"]
        for j in jobs:
            new = f"{j['stem']}__ys_{j['recipe']}"
            sh2.append(f"python3 generate_trans/cec/direct_cec.py --golden {wsl(j['src'])} "
                       f"--candidate {wsl(j['conv'])} --vali-dir {VALI_WSL} "
                       f"--timeout {a.timeout} --log {wsl(a.out)}/logs/cecconv_{new}.log "
                       f"> {wsl(a.out)}/logs/cecconv_{new}.txt 2>&1")
        gen2 = a.out / "_run_cec.sh"
        gen2.write_text("\n".join(sh2) + "\n", encoding="utf-8", newline="\n")
        r2 = subprocess.run(["wsl", "-e", "bash", "-c", f"sed 's/\\r$//' {wsl(gen2)} | bash"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"[cec-after-conv] rc={r2.returncode}")

    d = measure_all(jobs, sets_cache, prefixes, lib, a)
    return summarize(d, a, lib)
if __name__ == "__main__":
    sys.exit(main())
