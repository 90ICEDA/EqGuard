# -*- coding: utf-8 -*-
"""检查：删除 Trojan 门后，是否有良性门的输入来自 Trojan 门 → 决定 benign 反事实是否可安全构造。"""
import re
from pathlib import Path

CUR = Path(__file__).resolve().parent
for name in ["rs232t1000.v", "s15850t100.v", "s35932t200.v", "s38417t300.v", "s38584t100.v"]:
    p = CUR / "generate_trans" / "orig" / name
    txt = p.read_text(encoding="utf-8", errors="replace")
    stmts = [s for s in txt.split(";") if s.strip()]
    troj, benign = [], []
    for s in stmts:
        (troj if "trojan" in s.lower() else benign).append(s)
    # Trojan 门的输出 wire
    troj_out = set()
    for s in troj:
        for m in re.finditer(r"\.\w+\s*\(\s*([A-Za-z_]\w*)\s*\)", s):
            troj_out.add(m.group(1))
    # 实际上输出端口通常是最后一个；这里保守：所有连接到的 wire 都算“Trojan 相关”
    troj_wires = set()
    for s in troj:
        troj_wires |= set(re.findall(r"[A-Za-z_]\w*", s))
    # 良性门输入里引用了 Trojan 命名 wire 的
    leaked = []
    for s in benign:
        for w in re.findall(r"\.\w+\s*\(\s*([A-Za-z_]\w*)\s*\)", s):
            if "trojan" in w.lower():
                leaked.append((w, s.strip()[:70]))
    # Trojan 门的「最后一个端口」（= 输出）被良性门引用？
    troj_last = set()
    for s in troj:
        conns = re.findall(r"\.(\w+)\s*\(\s*([^)]*)\)", s)
        if not conns:
            continue
        out_port, out_wire = conns[-1]
        out_wire = out_wire.strip()
        if re.fullmatch(r"[A-Za-z_]\w*", out_wire):
            troj_last.add(out_wire)
    used_in_benign = []
    for s in benign:
        for w in re.findall(r"\.\w+\s*\(\s*([A-Za-z_]\w*)\s*\)", s):
            if w in troj_last:
                used_in_benign.append((w, s.strip()[:70]))
    print(f"{name}: stmts={len(stmts)} trojan_stmts={len(troj)} benign={len(benign)} "
          f"trojan_last_ports={len(troj_last)} USED_IN_BENIGN={len(used_in_benign)}")
    for x in used_in_benign[:4]:
        print("     ", x)
    if not used_in_benign and troj_last:
        print("      trojan outputs:", sorted(troj_last)[:6])
