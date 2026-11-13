"""yosys_regions.py —— 用 **yosys** 给网表做"功能区域"人口普查 ✓。

先说边界 ✓（论文里必须这么写 ✗→✓）：
  · yosys **不理解逻辑功能** ✗；它给的是**结构侧**的三样东西 ✓：
      ① 层次/名字前缀族 ✓  —— 例：`iXMIT_state_reg_0_` → 族 `iXMIT`（UART 发送器 ✓）
         仅当网表在综合时**没被全展平**、实例名保留了层次前缀时有效 ✓（rs232 ✓ / ISCAS89 ✗）
      ② DFF 边界锥 ✓ —— 两个寄存器之间的纯组合块 = 一个"结构功能块" ✓
      ③ 单元类型直方图 ✓ —— 每个族里 AND/XOR/DFF 各多少 ✓
  · 因此本脚本输出的是 **结构功能区域（structural functional regions）** ✓，
    不是 RTL 功能名 ✗（ISCAS89 的 `g*`/`U*` 网永远拿不到语义 ✗）。

用法 ✓：
  python phase2/ys/yosys_regions.py \
      --netlist generate_trans/hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v \
      --net rec_readyH --out 10.15/07_论文图表/tables/N1_yosys_regions.csv
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
YOSYS = ROOT / "ginvenv" / "Scripts" / "yowasp-yosys.exe"


def family(name: str) -> str:
    """实例名 → 区域族 ✓（`iXMIT_state_reg_0_`→`iXMIT` ✓；`n223`/`U12`→glue ✗）。"""
    n = re.sub(r"\\$.*$", "", name or "")
    if n.startswith("\\"):
        n = n[1:]
    if "HJ" in n.upper() or "trojan" in n.lower() or n.upper().startswith("TROJAN"):
        return "TROJAN"
    head = n.split("_")[0]
    if len(head) >= 3 and head.isalpha() and head.lower() not in ("n", "u", "net"):
        return head
    return "glue"


def yosys_json(netlist: Path) -> dict:
    """调 yosys 读网表 → write_json ✓（`-q` 压掉日志 ✓）。"""
    with tempfile.TemporaryDirectory() as td:
        js = Path(td) / "net.json"
        cmd = [str(YOSYS), "-q", "-p",
               f"read_verilog -sv {netlist.as_posix()}; hierarchy -auto-top; write_json {js.as_posix()}"]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not js.exists():
            print(r.stdout[-2000:])
            print(r.stderr[-2000:], file=sys.stderr)
            raise SystemExit(f"[ERR] yosys 没产出 json ✗ rc={r.returncode}")
        return json.loads(js.read_text(encoding="utf-8"))


OUT_PORTS = {"Y", "Q", "Z", "QN", "CO", "S", "SO", "O", "OUT", "DO", "G"}


def text_drivers(netlist: Path) -> dict[str, str]:
    """从 Verilog 文本里建 **net → 驱动实例** ✓。

    为什么不用 json ✗：标准单元是**黑盒**（未定义 module ✓）→ yosys 不写 `port_directions` ✗，
    只好按输出端口名约定（Y/Q/Z/QN/CO/S/SO/... ✓）读 ✓。
    """
    txt = netlist.read_text(encoding="utf-8", errors="replace")
    drv: dict[str, str] = {}
    pat = re.compile(r"([A-Za-z_][\w$]*)\s+([A-Za-z_][\w$\\]*)\s*\(([^;]*?)\)\s*;", re.S)
    for m in pat.finditer(txt):
        inst, body = m.group(2), m.group(3)
        for p, net in re.findall(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)", body):
            if p.upper() in OUT_PORTS:
                drv.setdefault(net.strip(), inst)
    return drv


def inst_conns(netlist: Path, inst: str) -> dict[str, str]:
    """取某实例的所有端口连接 ✓（文本解析 ✓ 黑盒也管用 ✓）。"""
    txt = netlist.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\b\S+\s+" + re.escape(inst) + r"\s*\(([^;]*?)\)\s*;", txt, re.S)
    if not m:
        return {}
    return {p: v.strip() for p, v in re.findall(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)", m.group(1))}


def analyse(netlist: Path, net: str = "") -> dict:
    d = yosys_json(netlist)
    mods = d["modules"]
    top = next(iter(mods))
    m = mods[top]
    cells = m.get("cells", {})
    ports = m.get("ports", {})

    driver = text_drivers(netlist)          # ✓ 黑盒单元的驱动关系 ✓

    fam = {c: family(c) for c in cells}
    fams: dict[str, dict] = {}
    for c, cid in fam.items():
        f = fams.setdefault(cid, {"cells": 0, "dff": 0, "types": Counter()})
        f["cells"] += 1
        t = cells[c].get("type", "")
        f["types"][t] += 1
        if "DFF" in t.upper():
            f["dff"] += 1

    # 被劫持网络 → 驱动单元 → （若是注入 mux 则再跳一层 ✓）→ **真正的功能区域** ✓
    hint: dict = {}
    if net:
        dc = driver.get(net)
        hint = {"net": net, "is_port": net in ports,
                "driver_cell": dc or "", "driver_family": fam.get(dc, "") if dc else "",
                "driver_type": cells.get(dc, {}).get("type", "") if dc else "",
                "orig_driver_cell": "", "orig_driver_family": "",
                "orig_net": "", "upstream": []}
        if dc and hint["driver_family"] == "TROJAN":
            cc = inst_conns(netlist, dc)
            for p in ("A", "IN1", "I0", "D"):           # 原数据输入 ✓（被"绕过"的真驱动 ✓）
                if p in cc:
                    hint["orig_net"] = cc[p]
                    o = driver.get(cc[p])
                    if o:
                        hint["orig_driver_cell"] = o
                        hint["orig_driver_family"] = fam.get(o, "")
                        up = inst_conns(netlist, o)
                        for p2, n2 in list(up.items())[:8]:
                            c2 = driver.get(n2)
                            hint["upstream"].append(
                                {"port": p2, "net": n2, "cell": c2 or "",
                                 "family": fam.get(c2, "") if c2 else ""})
                    break

    return dict(top=top, n_cells=len(cells),
                n_dff=sum(1 for c in cells if "DFF" in cells[c].get("type", "").upper()),
                fams=fams, hint=hint, cells=cells)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--netlist", type=Path, required=True)
    ap.add_argument("--net", default="", help="被劫持网络名 ✓（可选 ✓）")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    r = analyse(a.netlist, a.net)
    print(f"\n=== {a.netlist.name} ===")
    print(f"top={r['top']}  cells={r['n_cells']}  dff={r['n_dff']}")
    print(f"{'family':<14s}{'cells':>7s}{'dff':>6s}{'share':>8s}   top cell types")
    rows = []
    for f, v in sorted(r["fams"].items(), key=lambda kv: -kv[1]["cells"]):
        share = 100.0 * v["cells"] / max(1, r["n_cells"])
        tt = ", ".join(f"{k}:{n}" for k, n in v["types"].most_common(3))
        print(f"{f:<14s}{v['cells']:>7d}{v['dff']:>6d}{share:>7.1f}%   {tt}")
        rows.append(dict(netlist=a.netlist.name, family=f, cells=v["cells"],
                         dff=v["dff"], share_pct=round(share, 2), top_types=tt))
    if r["hint"]:
        h = r["hint"]
        print(f"\n[net] {h['net']}  is_port={h['is_port']}")
        print(f"  driver cell      : {h['driver_cell']} ({h['driver_type']})  [{h['driver_family']}]")
        if h.get("orig_driver_cell"):
            print(f"  bypassed (orig)  : {h['orig_net']} <- {h['orig_driver_cell']} "
                  f"[{h['orig_driver_family']}]")
        for u in h.get("upstream", []):
            print(f"    .{u['port']:<5s} {u['net']:<22s} <- {u['cell']:<24s} [{u['family']}]")

    if a.out:
        import pandas as pd
        a.out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[out] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
