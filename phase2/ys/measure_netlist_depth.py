"""measure_netlist_depth.py —— 给 F0 补 **逻辑深度** 与 **名字存活率**（yosys 结构侧 ✓）。

不做的 ✗：不推断功能 ✓（yosys 不懂功能 ✓）；只给两个**结构事实** ✓：
  ① `ltp` 最长拓扑路径长度 = **逻辑深度** ✓（组合层数 ✓）
  ② **名字存活率** ✓：相对同 host、同配方的 `clean` 网表 ✓，
     端口名保留率 ✓ + 实例名保留率 ✓（= 1 − 被重命名/合并的比例 ✓）

输出 ✓：`<out>/netlist_depth.csv`（逐网表 ✓）+ 控制台汇总 ✓。

用法 ✓：
  python phase2/ys/measure_netlist_depth.py --recipes ys_id,ys_opt,ys_abc \\
         --insts clean,injalpha,ctlmatcha --out 10.15/07_论文图表/tables
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
YOSYS = ROOT / "ginvenv" / "Scripts" / "yowasp-yosys.exe"
NET = ROOT / "generate_trans" / "yosys_netlists"

RE_INST = re.compile(r"^\s*([A-Za-z_][\w$]*)\s+([A-Za-z_\\][\w$\\]*)\s*\(", re.M)
RE_MOD = re.compile(r"module\s+([A-Za-z_][\w$]*)\s*\(([^;]*?)\)\s*;(.*?)endmodule", re.S)
RE_CELLS = re.compile(r"^\s+(\d+)\s+cells\s*$", re.M)      # ⚠️ stat 的格式是 "  325 cells" ✗


def ports_of(txt: str) -> set[str]:
    """顶层模块的端口名集合 ✓（`input [7:0] a, b;` 逐名拆 ✓）。"""
    m = RE_MOD.search(txt)
    if not m:
        return set()
    body = m.group(3)
    out: set[str] = set()
    for decl in re.finditer(r"\b(input|output|inout)\b([^;]*);", body):
        seg = re.sub(r"\[[^\]]*\]", " ", decl.group(2))
        for tok in seg.split(","):
            tok = tok.strip().split()[-1] if tok.strip() else ""
            if re.fullmatch(r"[A-Za-z_][\w$]*", tok):
                out.add(tok)
    return out


def insts_of(txt: str) -> set[str]:
    """实例名集合 ✓（跳过 module/端口声明行 ✓）。"""
    outs = set()
    for m in RE_INST.finditer(txt):
        kw, name = m.group(1), m.group(2)
        if kw in ("module", "input", "output", "inout", "wire", "reg", "assign",
                  "always", "endmodule", "parameter", "localparam", "begin", "end"):
            continue
        outs.add(name)
    return outs


def run_ltp(net: Path) -> tuple[int, int]:
    """返回 (节点数, 逻辑深度) ✓；失败返回 (-1, -1) ✗。"""
    p = f"read_verilog -sv {net.as_posix()}; hierarchy -auto-top; ltp; stat"
    # ⚠️ 不能加 `-q` ✗：`ltp` / `stat` 的结论都打在日志里 ✓，`-q` 会把它们一起吞掉 ✗
    r = subprocess.run([str(YOSYS), "-p", p], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    txt = r.stdout + r.stderr
    depth = -1
    m = re.search(r"Longest topological path in \S+ \(length=(\d+)\)", txt)
    if m:
        depth = int(m.group(1))
    nodes = -1
    mm = RE_CELLS.search(txt)
    if mm:
        nodes = int(mm.group(1))
    return nodes, depth


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net-root", type=Path, default=NET)
    ap.add_argument("--recipes", default="ys_id,ys_opt,ys_abc")
    ap.add_argument("--insts", default="clean,injalpha,ctlmatcha")
    ap.add_argument("--out", type=Path, default=ROOT / "10.15/07_论文图表/tables")
    a = ap.parse_args()

    rec = {r.strip() for r in a.recipes.split(",") if r.strip()}
    ins = {i.strip() for i in a.insts.split(",") if i.strip()}
    rows = []
    hosts = sorted(p for p in a.net_root.iterdir() if p.is_dir() and p.name != "logs")
    for hd in hosts:
        # 基线 ✓ = 同 host 的 `clean__ys_id`（= 原始名字 ✓，ys_id 是恒等配方 ✓）
        bf = hd / f"{hd.name}_clean__ys_id.v"
        if not bf.exists():
            print(f"[skip] {hd.name} 没有 clean__ys_id ✗")
            continue
        bt = bf.read_text(encoding="utf-8", errors="replace")
        bp, bi = ports_of(bt), insts_of(bt)

        def emit(f: Path, inst: str, rec_i: str) -> None:
            n, d = run_ltp(f)
            t = f.read_text(encoding="utf-8", errors="replace")
            pp, ii = ports_of(t), insts_of(t)
            rows.append(dict(host=hd.name, inst=inst, recipe=rec_i, nodes=n, depth=d,
                             port_keep=round(len(bp & pp) / max(1, len(bp)), 4),
                             inst_keep=round(len(bi & ii) / max(1, len(bi)), 4)))
            print(f"[ok] {hd.name}/{inst}/{rec_i} nodes={n} depth={d} "
                  f"port={rows[-1]['port_keep']} inst={rows[-1]['inst_keep']}", flush=True)

        for rec_i in sorted(rec):
            f = hd / f"{hd.name}_clean__{rec_i}.v"
            if f.exists():
                emit(f, "clean", rec_i)
        for f in sorted(hd.glob("*.v")):
            m = re.match(r"^(?P<host>[^_]+)__(?P<inst>.+?)_d1_s\d+__(?P<rec>ys_\w+)\.v$", f.name)
            if not m:
                continue
            inst, rec_i = m.group("inst"), m.group("rec")
            if inst not in ins or rec_i not in rec:
                continue
            emit(f, inst, rec_i)
    df = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out / "netlist_depth.csv", index=False, encoding="utf-8-sig")
    if not df.empty:
        print("\n按配方汇总 ✓（depth 中位 / inst_keep 中位 ✓）")
        print(df.groupby("recipe")[["depth", "inst_keep", "port_keep"]]
              .median().round(3).to_string())
    print(f"\n[out] {a.out / 'netlist_depth.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
