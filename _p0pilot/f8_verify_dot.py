"""f8_verify_dot.py -- 校验 F8 DOT：孤立节点 / PO' 数 / 端口引用。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TMP = Path.home() / "AppData/Local/Temp"


def check(tag: str) -> None:
    t = (TMP / f"f8g_{tag}.dot").read_text(encoding="utf-8")
    ids = set(re.findall(r"(?m)^(n\d+) \[", t))
    src = set(re.findall(r"(?m)^(n\d+):", t))
    dst = set(re.findall(r"(?m)-> (n\d+):", t))
    po = len(re.findall(r"OUT PO'", t))
    outs = len(re.findall(r"OUT (?:Q|QN|PO')", t))
    print(f"[{tag}] nodes={len(ids)} isolated={sorted(ids - src - dst)} PO'={po} out_ports={outs}")
    # 每个边引用的输出端口必须真的存在
    bad = []
    for m in re.finditer(r"(?m)^(n\d+):(\w+):[ewsn] -> (n\d+):(\w+):[ewsn]", t):
        u, up, c, cp = m.groups()
        line_u = next((ln for ln in t.splitlines() if ln.startswith(f"{u} [")), "")
        line_c = next((ln for ln in t.splitlines() if ln.startswith(f"{c} [")), "")
        if f"<{up}>" not in line_u or f"<{cp}>" not in line_c:
            bad.append((u, up, c, cp))
    print(f"      bad_port_refs={bad}")


if __name__ == "__main__":
    for tag in ("L", "R"):
        check(tag)
