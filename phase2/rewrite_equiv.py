# -*- coding: utf-8 -*-
"""
rewrite_equiv.py —— 等价实现生成器（A 步）

目的：给每个受控视图生成 2 个**可证明等价**的实现，用于"跨实现"那一维。

用两类局部重写（**保持输出网名不变**，因此不需要改任何消费者）：
  E1 `decomp3`（拆 3 输入门，制造 1→2 的"split"）：
       NOR3(a,b,c) -> OR2(a,b) + NOR2(·,c)          # ~(a|b|c) = ~((a|b)|c)
       NAND3(a,b,c)-> AND2(a,b) + NAND2(·,c)
       AND3(a,b,c) -> AND2(a,b) + AND2(·,c)
       OR3(a,b,c)  -> OR2(a,b) + OR2(·,c)
  E2 `bubble`（反相门拆成"正相门 + 反相器"）：
       NAND2(a,b) -> AND2(a,b) + INV(·)
       NOR2(a,b)  -> OR2(a,b) + INV(·)

每个改写门都产生 **1→2** 的对象映射（orig 门 → [新门1, 新门2]），
未被改写的门保持身份映射 → 直接得到对象级 `node_alignment`。

用法：
  python phase2/rewrite_equiv.py build --hosts-root generate_trans/hosts \
      --lib ../GraphSAINT-train/vali/verilog_lib.v
  python phase2/rewrite_equiv.py cec  --hosts-root generate_trans/hosts   # 用 WSL+yosys 逐个验证
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import netlist_lib as NL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"
WSL_VALI = "/mnt/c/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali"

DECOMP3 = {"NOR3": ("OR2", "NOR2"), "NAND3": ("AND2", "NAND2"),
           "AND3": ("AND2", "AND2"), "OR3": ("OR2", "OR2")}
BUBBLE = {"NAND2": ("AND2", "INV"), "NOR2": ("OR2", "INV")}


def _suffix(gate: str) -> str:
    m = re.search(r"(_RS|_S\d*)$", gate)
    return m.group(1) if m else ""


def pick(gates, base: str, like: str) -> str | None:
    """在宿主已有门类型里挑一个同族同基名的门。"""
    suf = _suffix(like)
    cand = [g for g in gates if g.startswith(base) and _suffix(g) == suf]
    if not cand:
        cand = [g for g in gates if g.startswith(base)]
    return sorted(cand)[0] if cand else None


def _mk(lib, gate, name, nets):
    ports = lib[gate]["inputs"] + lib[gate]["outputs"]
    if len(ports) != len(nets):
        raise ValueError(f"{gate} 需要 {len(ports)} 端口，给了 {len(nets)}")
    return NL.Inst(gate=gate, name=name, conns=list(zip(ports, nets)))


def emit_and(gates, lib, a, b, out, tag, ctr):
    """产出一个"AND(a,b)"子网。退化顺序：AND2 → AND3(a,b,1'b1) → INV(NAND2)。

    返回 (insts, ctr, 用到的门类型)。
    """
    g = pick(gates, "AND2", "")
    if g:
        return [_mk(lib, g, f"{tag}N{ctr}", [a, b, out])], ctr + 1, g
    g3 = pick(gates, "AND3", "") or pick(gates, "AND4", "")
    if g3:
        w = ["1'b1"] * (len(lib[g3]["inputs"]) - 2)
        return [_mk(lib, g3, f"{tag}N{ctr}", [a, b] + w + [out])], ctr + 1, g3
    gn = pick(gates, "NAND2", "")
    gi = pick(gates, "INV", "") or pick(gates, "NBUFF", "")
    if gn and gi:
        t = f"{tag}T{ctr}"
        return [_mk(lib, gn, f"{tag}N{ctr}", [a, b, t]),
                _mk(lib, gi, f"{tag}I{ctr}", [t, out])], ctr + 1, f"INV+{gn}"
    return None, ctr, None


def emit_or(gates, lib, a, b, out, tag, ctr):
    """产出一个"OR(a,b)"子网。退化顺序：OR2 → INV(NOR2) → NAND2(INV a, INV b)。"""
    g = pick(gates, "OR2", "")
    if g:
        return [_mk(lib, g, f"{tag}N{ctr}", [a, b, out])], ctr + 1, g
    gi = pick(gates, "INV", "") or pick(gates, "NBUFF", "")
    gl = pick(gates, "NOR2", "")
    if gl and gi:
        t = f"{tag}T{ctr}"
        return [_mk(lib, gl, f"{tag}N{ctr}", [a, b, t]),
                _mk(lib, gi, f"{tag}I{ctr}", [t, out])], ctr + 1, f"INV+{gl}"
    gn = pick(gates, "NAND2", "")
    if gn and gi:
        ta, tb = f"{tag}TA{ctr}", f"{tag}TB{ctr}"
        return [_mk(lib, gi, f"{tag}IA{ctr}", [a, ta]),
                _mk(lib, gi, f"{tag}IB{ctr}", [b, tb]),
                _mk(lib, gn, f"{tag}N{ctr}", [ta, tb, out])], ctr + 1, f"{gn}+2INV"
    return None, ctr, None


def rewrite(nl: NL.Netlist, lib, mode: str, tag: str) -> tuple:
    """就地重写；返回 (mapping, n_rewritten, skipped_reasons)。

    对每个目标门，用 emit_and/emit_or 生成"AND(a,b) / OR(a,b)"子网，
    中间结果用临时网名；**最终输出仍用原网名**（消费者不受影响）。
    """
    gates = {i.gate for i in nl.insts}
    table = DECOMP3 if mode == "decomp3" else BUBBLE
    kicker = re.compile(r"^(" + "|".join(table) + r")")
    mapping, n, skipped, ctr = {}, 0, {}, 0
    out_insts = []
    for i in nl.insts:
        m = kicker.match(i.gate)
        if not m or "DFF" in i.gate.upper():
            out_insts.append(i); mapping[i.name] = [i.name]; continue
        kind = m.group(1)
        need = 3 if mode == "decomp3" else 2
        if len(i.conns) - 1 != need:
            out_insts.append(i); mapping[i.name] = [i.name]
            skipped["arity"] = skipped.get("arity", 0) + 1; continue
        ins = [net for _p, net in nl.ins(i)]
        out_net = nl.outs(i)[0][1]
        seg = []
        if mode == "decomp3":
            base1, base2 = table[kind]                       # 例 ("OR2","NOR2")
            # 第一段：OR/AND(a,b) → 临时网（同样先捕获名字，别用会被 ctr 影响的表达式）
            t = f"{tag}S{ctr}"
            fn = emit_or if base1.startswith("OR") else emit_and
            s1, ctr, used1 = fn(gates, lib, ins[0], ins[1], t, tag, ctr)
            if s1 is None:
                out_insts.append(i); mapping[i.name] = [i.name]
                skipped[f"no_{base1}"] = skipped.get(f"no_{base1}", 0) + 1; continue
            seg += s1
            g2 = pick(gates, base2, i.gate)                   # 第二段：用原族的 2 输入门
            if not g2 and base2.startswith(("AND", "OR")):
                fn2 = emit_and if base2.startswith("AND") else emit_or
                s2, ctr, used2 = fn2(gates, lib, t, ins[2], out_net, tag, ctr)
            else:
                s2 = [_mk(lib, g2, f"{tag}N{ctr}", [t, ins[2], out_net])] if g2 else None
                ctr += 1; used2 = g2
            if s2 is None:
                out_insts.append(i); mapping[i.name] = [i.name]
                skipped["no_second_stage"] = skipped.get("no_second_stage", 0) + 1; continue
            seg += s2
        else:                                                 # bubble
            base1, base2 = table[kind]                        # 例 ("AND2","INV")
            fn = emit_and if base1.startswith("AND") else emit_or
            # ★ 必须先捕获临时网名：fn() 会把 ctr 加 1（旧写法用 f"{tag}S{ctr}" 会读到"下一个门的网"）
            out_tmp = f"{tag}S{ctr}"
            s1, ctr, used1 = fn(gates, lib, ins[0], ins[1], out_tmp, tag, ctr)
            if s1 is None:
                out_insts.append(i); mapping[i.name] = [i.name]
                skipped[f"no_{base1}"] = skipped.get(f"no_{base1}", 0) + 1; continue
            seg += s1
            gi = pick(gates, "INV", "") or pick(gates, "NBUFF", "")
            if not gi:
                out_insts.append(i); mapping[i.name] = [i.name]
                skipped["no_INV"] = skipped.get("no_INV", 0) + 1; continue
            seg.append(_mk(lib, gi, f"{tag}I{ctr}", [out_tmp, out_net])); ctr += 1
        out_insts += seg
        mapping[i.name] = [x.name for x in seg]
        n += 1
    nl.insts = out_insts
    return mapping, n, skipped



def build(hosts_root: Path, lib_path: Path) -> int:
    lib = NL.load_library(lib_path)
    rows = []
    for hdir in sorted(p for p in hosts_root.iterdir() if p.is_dir() and p.name != "base"):
        views = sorted(p for p in hdir.glob("*__*_d1_s42.v") if "__rw" not in p.name)
        if not views:
            continue
        (hdir / "rw").mkdir(exist_ok=True)
        (hdir / "rw_mappings").mkdir(exist_ok=True)
        for src in views:
            stem = src.stem
            for k, mode in enumerate(("decomp3", "bubble"), start=1):
                nl = NL.parse_netlist(src, lib)
                tag = f"RW{mode[0].upper()}{k}"
                mp, n_rw, skipped = rewrite(nl, lib, mode, tag)
                rw_view = f"{stem}__rw{mode}_d1_s42"
                mod = rw_view
                nl.head = re.sub(r"\bmodule\s+" + re.escape(nl.module) + r"\b",
                                 "module " + mod, nl.head, count=1)
                nl.module = mod
                dst = hdir / "rw" / f"{rw_view}.v"
                dst.write_text(NL.emit_netlist(nl), encoding="utf-8")
                cov = sum(1 for v in mp.values() if len(v) > 1)
                (hdir / "rw_mappings" / f"{rw_view}.json").write_text(json.dumps({
                    "src_verilog": f"{stem}.v", "operator_family": mode,
                    "src_view": stem, "node_alignment": mp,
                    "n_rewritten": n_rw, "n_split_objects": cov,
                    "skipped": skipped}, ensure_ascii=False), encoding="utf-8")
                rows.append({"host": hdir.name, "src_view": stem, "rw_view": rw_view,
                             "mode": mode, "n_rewritten": n_rw,
                             "n_objects": len(mp), "n_split_1toN": cov,
                             "skip_reasons": json.dumps(skipped, ensure_ascii=False),
                             "rw_netlist": str(dst)})
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(hosts_root / "rewrite_variants.csv", index=False, encoding="utf-8-sig")
    print(f"[OK] 生成等价实现 {len(df)} 个")
    if not df.empty:
        print(df.groupby("mode")[["n_rewritten", "n_split_1toN"]].mean().round(1).to_string())
        print(df.groupby("host")[["n_rewritten"]].sum().to_string())
    print(f"[导出] {hosts_root / 'rewrite_variants.csv'}")
    return 0


def cec(hosts_root: Path) -> int:
    """写一个 WSL bash 脚本，逐个对 (源视图, 等价实现) 做 yosys CEC。"""
    try:                       # 路径必须跟着 hosts-root 走，否则 B 型会指到 A 型目录
        rel = hosts_root.relative_to(ROOT).as_posix()
    except ValueError:
        rel = hosts_root.as_posix()
    lines = ["#!/bin/bash", "cd /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train",
             f"OUT={rel}/rw_cec_results.csv",
             'echo "host,src_view,rw_view,proven,unproven,status" > $OUT']
    import csv as _csv
    df = pd.read_csv(hosts_root / "rewrite_variants.csv") if (hosts_root / "rewrite_variants.csv").exists() else None
    if df is None:
        print("[ERROR] 先跑 build"); return 1
    for r in df.itertuples():
        g = f"{rel}/{r.host}/{r.src_view}.v"
        c = f"{rel}/{r.host}/rw/{r.rw_view}.v"
        log = f"/tmp/rw_{r.host}_{r.rw_view}.log"
        lines.append(
            f'python3 generate_trans/cec/direct_cec.py --golden {g} --candidate {c} '
            f'--vali-dir {WSL_VALI} --timeout 900 --log {log} > /tmp/o.txt 2>&1; '
            f'RC=$?; P=$(grep -oE "proven=[0-9]+" /tmp/o.txt | tail -1); '
            f'U=$(grep -oE "unproven=[0-9]+" /tmp/o.txt | tail -1); '
            f'S=$(grep -oE "PASS|FAIL" /tmp/o.txt | tail -1); '
            f'echo "{r.host},{r.src_view},{r.rw_view},$P,$U,${{S:-rc$RC}}" >> $OUT')
    sh = hosts_root / "rw_cec.sh"
    sh.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] CEC 脚本 -> {sh}（{len(df)} 对）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="等价实现生成 / CEC")
    ap.add_argument("cmd", choices=["build", "cec"])
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    a = ap.parse_args()
    if a.cmd == "build":
        return build(a.hosts_root.resolve(), a.lib)
    return cec(a.hosts_root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())

