"""f8_dot.py -- F8 的**门→门直连**电路图（去掉 yosys 的网椭圆 ✓）。

为什么重写 ✗：`yosys show` 是"网为中心"（门 → **网椭圆** → 门），
  所以门与门之间看不到驱动线、箭头也都指向门 ✓（但这不直观 ✗）。
本脚本用同一份 `.v` + 自己的 net→driver 映射，直接产出：
  单元 = record 方框（左列输入脚 IN1/IN2/D…、右侧 <out> Q ✓）
  连线 = **驱动单元 → 负载单元**，边上标真实网名 ✓，箭头顺信号流向 ✓
  外部输入（图内无驱动门）= 方框内**直接写真实网名** ✓（不写形式 IN1/IN2 ✗）
  时钟脚默认只写网名（如 `CK`）且不接线 ✓；`--clock-mark` 才加 `▷` ⚠️（易被看成 `?` ✗）
  颜色 = 木马单元浅红 ✓ / 宿主浅蓝 ✓；`splines=polyline` 走线 ✓。

用法：
  ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/f8_dot.py \
      --host s38417t100 --inst injalpha --ra ys_id --rb ys_abc --hops 2
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f8_rewrite_case as F8

TMP = Path.home() / "AppData/Local/Temp"
FONT = "DejaVu Sans"        # ⚠️ WSL 里默认 Times 不含 `▷`(U+25B7) → 显示成 `?` ✗；DejaVu 有 ✓


def _short(s: str, k: int = 14) -> str:
    """网名过长时截断 ✓（record 太宽整张图会被压扁 ✗）。"""
    return s if len(s) <= k else s[: k - 2] + ".."


# ---------------------------------------------------------------------------
# ⚠️ yosys 写出的 `.v` 里有大量别名：`assign \TrojanAP0.Q = n__TrojanAP0_Q__g7 ;`
#    旧版只解析实例行 → 别名两侧的网对不上 → 木马输入/输出门全部"断线" ✗
#    （L 栏稳定出现 5 个孤立红门 ✗）。这里把 assign 两端并成同一个规范网 ✓。
# ---------------------------------------------------------------------------
ASSIGN_RE = re.compile(r"^\s*assign\s+\\?([^\s=]+)\s*=\s*\\?([^\s;]+)\s*;")
# 木马“输出到正常网表”的信号（例：TrojanA_t1）→ 区域主输出 TPO
# ⚠️ TrojanA_p0/p1/p2 是木马内部 payload（消费者输入仍是 Trojan* → 木马接木马），
#    不标 TPO；网表审计见 `_p0pilot/f8_tpo_audit.py`。
PAYLOAD_RE = re.compile(r"^Trojan\w*_t\d+$")


class _DSU:
    """并查集 ✓（assign 别名是双向等价的 ✓）。"""

    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def parse_assign_alias(path: Path) -> tuple[_DSU, set[str]]:
    """读顶层 output 端口 + assign 别名等价类 ✓。"""
    dsu, outs = _DSU(), set()
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s.startswith("output "):
            outs.add(s.split()[1].strip(";").lstrip("\\"))
        m = ASSIGN_RE.match(s)
        if m:
            dsu.union(m.group(1), m.group(2))
    return dsu, outs


def canonical_cells(cells: dict, dsu: _DSU) -> dict:
    """把所有引脚网名换到 assign 等价类的规范名 ✓（单元名/引脚名不变 ✓）。"""
    return {c: (typ, {p: dsu.find(n) for p, n in pins.items()})
            for c, (typ, pins) in cells.items()}


def output_roles(cells: dict, dsu: _DSU, tops: set[str]) -> tuple[set[str], set[str]]:
    """返回 (顶层 PO 的规范名, 木马 payload 输出的规范名) ✓。

    ⚠️ `TrojanA_p0` 这类 payload 名可能**只出现在 assign 行**、不在任何引脚上 ✗
    → 必须把 `dsu.p`（所有 assign 端）并进来 ✓，否则一个都匹配不到 ✗。
    """
    nets = {n for _t, pins in cells.values() for n in pins.values()} | set(dsu.p)
    top_c = {dsu.find(o) for o in tops}
    pay_c = {dsu.find(n) for n in nets if PAYLOAD_RE.match(n)}
    return top_c, pay_c



def region(cells, drv, cons, seeds, hops, cap):
    seen, q = set(seeds), deque((s, 0) for s in seeds)
    while q:
        c, d = q.popleft()
        if d >= hops or len(seen) >= cap:
            continue
        nb = set(cons.get(c, set()))
        for pin, net in cells[c][1].items():
            if pin.upper() in F8.OUT_PINS:
                nb |= set(drv.get(net, set()))
        for u in nb:
            if u not in seen and len(seen) < cap:
                seen.add(u)
                q.append((u, d + 1))
    return seen


def build_dot(cells, subset, drv, title: str, path: Path, rankdir: str = "TB",
              clock_wires: bool = False, ext_stubs: bool = False,
              clock_mark: bool = False, disp: dict | None = None,
              top_c=frozenset(), pay_c=frozenset()) -> int:
    """**自算层级 + rank=same**（TB 用）✓；时钟默认不接线 ✓。

    `cells` 是 **assign 别名合并后的规范网** ✓（用于连边 ✓）；
    `disp` 是原始 cells ✓（用于在方框/边上显示真实网名 ✓）。
    外部输入（图内**没有**驱动门的脚）→ 直接把真实网名写进方框 ✓。
    输出脚按 **Q / QN 分开建端口** ✓（旧版只留一个 `<out>` ✗ → Q/QN 边混在一起 ✗）；
      若该输出网（assign 闭包后）是顶层 PO 或木马 payload 输出 → 文本写 `OUT PO'` ✓。
    时钟脚默认只写真实网名（如 `CK`）✓；`clock_mark=True` 可加 `▷` 记号 ⚠️。
    """
    disp = disp or cells
    CLK_PINS = {"CK", "CLK"}
    ids = {c: f"n{i}" for i, c in enumerate(sorted(subset))}
    # ---- 1) 边 + 外部输入表 ----（第 5 项 = 驱动脚名，桩为 None ✓）
    edges: list[tuple[str, str, str, str, str | None]] = []
    stubs: dict[str, str] = {}                       # 规范网 -> id（仅 ext_stubs=True 用）
    stub_lab: dict[str, str] = {}                    # 桩 id -> 显示网名
    ext: dict[tuple[str, str], str] = {}             # (cell, pin) -> 外部网名（原始 ✓）
    for c in sorted(subset):
        typ, pins = cells[c]
        raw_pins = disp[c][1]
        for p, net in pins.items():
            if p.upper() in F8.OUT_PINS:
                continue
            raw = raw_pins.get(p, net)
            if (not clock_wires) and p.upper() in CLK_PINS:   # ⚠️ 时钟不接线 ✓
                ext[(c, p)] = raw
                continue
            hit = [u for u in drv.get(net, ()) if u in subset and u != c]
            if hit:
                u = hit[0]
                up = next((q for q, nn in cells[u][1].items()
                           if q.upper() in F8.OUT_PINS and nn == net), "out")
                edges.append((ids[u], ids[c], p, raw, up))
            else:
                ext[(c, p)] = raw
                if ext_stubs:
                    if net not in stubs:
                        stubs[net] = f"x{len(stubs)}"
                        stub_lab[stubs[net]] = raw
                    edges.append((stubs[net], ids[c], p, raw, None))

    # ---- 2) 最长路径分层（桩在第 0 层）----
    depth: dict[str, int] = {i: 0 for i in ids.values()}
    depth.update({i: 0 for i in stubs.values()})
    for _ in range(len(depth)):
        ch = False
        for u, c, *_ in edges:
            if depth[c] < depth[u] + 1:
                depth[c] = depth[u] + 1
                ch = True
        if not ch:
            break

    # ---- 3) 输出 DOT ----
    L = [f'digraph "{title}" {{', f'rankdir={rankdir};', 'splines=polyline;',
         'nodesep=0.22;', 'ranksep=0.55;', 'fontsize=9;', f'fontname="{FONT}";',
         f'node [shape=record, fontsize=9, penwidth=0.8, fontname="{FONT}"];',
         f'edge [fontsize=8, arrowsize=0.6, penwidth=0.8, fontname="{FONT}"];']
    for c in sorted(subset):
        typ, pins = cells[c]
        raw_pins = disp[c][1]
        ins = [p for p in pins if p.upper() not in F8.OUT_PINS]
        outs = [p for p in pins if p.upper() in F8.OUT_PINS]
        # 左列 = 输入脚：**图内没有驱动门的脚直接写真实网名** ✓（不写形式 IN1/IN2 ✗）
        # 时钟脚默认只写网名 ✓（`--clock-mark` 才加 `▷` ⚠️ 易被看成 `?` ✗）
        flds = []
        for p in ins:
            n = ext.get((c, p))
            if n is None:
                flds.append(f"<{p}> {p}")            # 图内相连 → 写脚名 ✓（网名在线上 ✓）
            elif p.upper() in CLK_PINS and clock_mark:
                flds.append(f"<{p}> ▷{_short(n)}")   # 时钟 → `▷` + 网名 ⚠️（可选）
            else:
                flds.append(f"<{p}> {_short(n)}")    # 外部输入 → 写真实网名 ✓
        left = "|".join(flds) or "<none> -"
        # 右列 = **每个输出脚一个端口** ✓；真实顶层输出标 `OUT PO`，木马输出到正常网表的信号标 `OUT TPO` ✓
        oflds = []
        for p in outs:
            cnet = pins[p]
            if cnet in top_c:
                oflds.append(f"<{p}> OUT PO")
            elif cnet in pay_c:
                oflds.append(f"<{p}> OUT TPO")
            else:
                oflds.append(f"<{p}> OUT {p}")
        right = "|".join(oflds) or "<out> -"
        fc = "lightpink" if "trojan" in c.lower() else "lightblue"
        lab = "{" + left + "}|" + f"{c}|{typ}" + "|{" + right + "}"
        L.append(f'{ids[c]} [label="{lab}", style=filled, fillcolor="{fc}"];')
    for sid, net in stub_lab.items():
        L.append(f'{sid} [shape=plaintext, fontsize=8, fontcolor="#444", label="{net}"];')
    # 同层强制横排 ✓（**仅 TB 用** ✓；LR 下 rank=same 会把图拉成竖条 ✗）
    if rankdir == "TB":
        by_depth: dict[int, list[str]] = {}
        for nid, d in depth.items():
            by_depth.setdefault(d, []).append(nid)
        for d in sorted(by_depth):
            L.append("{ rank=same; " + "; ".join(sorted(by_depth[d])) + "; }")
    # ---- 端口方向 ✓：LR=东→西 ✓ / TB=下→上 ✓
    out_side, in_side = ("s", "n") if rankdir == "TB" else ("e", "w")
    for u, c, p, net, op in edges:
        src = f"{u}:{op}:{out_side}" if op else u
        L.append(f'{src} -> {c}:{p}:{in_side} [label="{net}"];')
    L.append("}")
    path.write_text("\n".join(L), encoding="utf-8")   # ⚠️ ascii+replace 会把 `▷` 变成 `?` ✗
    return len(edges)


def render(dot_path: Path, png_path: Path) -> bool:
    """⚠️ 先删旧 PNG ✓ 并检查 dot 的返回码 ✓（否则会静默复用旧图 ✗）。"""
    if png_path.exists():
        png_path.unlink()
    wsl = f"/mnt/c/Users/{Path.home().name}/AppData/Local/Temp"
    r = subprocess.run(["wsl", "-e", "bash", "-lc",
                        f'dot -Tpng -Gdpi=170 "{wsl}/{dot_path.name}" -o "{wsl}/{png_path.name}"'],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    if r.returncode != 0:
        print(f"[dot-error] {r.stderr.strip()[:200]}")
        return False
    return png_path.exists()


def save_png(im: "Image.Image", path: Path) -> None:
    """⚠️ 直接 `im.save(out)` 覆盖已有 PNG 时会 `OSError(22)` ✗（与 CSV 写盘同一坑 ✗）
    → **临时文件 + os.replace + 重试** ✓。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.png")
    for attempt in range(6):
        try:
            im.save(tmp)
            os.replace(tmp, path)
            return
        except OSError:
            if attempt == 5:
                raise
            time.sleep(1.5 * (attempt + 1))


def compose(pl: Path, pr: Path, tl: str, tr: str, cap: str, out: Path) -> None:
    """⚠️ **不缩放** ✓（两栏同 dpi 同尺度 → 方便后期人工连匹配线 ✓）。"""
    ims = [Image.open(p).convert("RGB") for p in (pl, pr) if p and p.exists()]
    if not ims:
        raise SystemExit("[ERROR] 两侧都没渲染出来 ✗")
    gap, top, bottom = 60, 64, 74
    h = max(i.height for i in ims)
    W = sum(i.width for i in ims) + gap * (len(ims) + 1)
    cv = Image.new("RGB", (W, h + top + bottom), "white")
    d = ImageDraw.Draw(cv)
    x = gap
    for i, im in enumerate(ims):
        cv.paste(im, (x, top))
        d.text((x, 26), [tl, tr][i], fill=(20, 20, 20))
        x += im.width + gap
    d.text((gap, top + h + 24), cap, fill=(40, 40, 40))
    save_png(cv, out)
    print(f"[out] {out}（{W}x{h + top + bottom}）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="s38417t100")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--ra", default="ys_id")
    ap.add_argument("--rb", default="ys_abc")
    ap.add_argument("--hops", type=int, default=2)
    ap.add_argument("--cap", type=int, default=16)
    ap.add_argument("--rankdir", choices=["TB", "LR"], default="TB",
                    help="TB=从上到下 ✓（默认，弯折更少 ✓，文字仍是正的 ✓）；LR=从左到右")
    ap.add_argument("--clock-wires", action="store_true",
                    help="把时钟(CK/CLK)也接线 ⚠️（默认**不接** ✓，只在方框里写时钟网名如 `CK` ✓）")
    ap.add_argument("--ext-stubs", action="store_true",
                    help="外部输入画成左侧文本桩 ⚠️（默认**不画** ✓，直接把网名写进方框 ✓）")
    ap.add_argument("--clock-mark", action="store_true",
                    help="时钟脚加 `▷` 记号 ⚠️（默认不加 ✓；该字形在部分字体里会显示成 `?` ✗）")
    ap.add_argument("--out", type=Path, default=F8.FIGS / "F8_gate_graph.png")
    a = ap.parse_args()

    outs, tags = [], []
    for rcp, tag in ((a.ra, "L"), (a.rb, "R")):
        p = F8.VDIR / f"{a.host}__{a.inst}_d1_s42__{rcp}.v"
        cells = F8.parse_v(p)                      # 原始网名（用于显示 ✓）
        dsu, tops = parse_assign_alias(p)          # assign 别名 ✓
        ccells = canonical_cells(cells, dsu)       # 规范网（用于连边 ✓）
        top_c, pay_c = output_roles(cells, dsu, tops)   # PO / payload 判定 ✓
        drv, cons = F8.build_graph(ccells)
        seeds = {c for c in cells if "trojan" in c.lower()}
        nodes = region(ccells, drv, cons, seeds, a.hops, a.cap)
        dot_p, png_p = TMP / f"f8g_{tag}.dot", TMP / f"f8g_{tag}.png"
        ne = build_dot(ccells, nodes, drv, f"{a.host}__{a.inst}__{rcp}", dot_p,
                       a.rankdir, a.clock_wires, a.ext_stubs, a.clock_mark,
                       disp=cells, top_c=top_c, pay_c=pay_c)
        ok = render(dot_p, png_p)
        print(f"[{tag}] {rcp}: cells={len(nodes)} edges={ne} render={'ok' if ok else 'FAIL'}")
        outs.append(png_p if ok else None)
        tags.append(f"{a.host} . {a.inst} . {rcp} ({len(nodes)} cells / {ne} wires)")

    cap = (f"gate-to-gate wires (real net names on edges) | assign aliases merged "
           f"| external inputs labelled with real net names | "
           f"OUT PO = top-level primary output | OUT TPO = trojan output entering normal logic "
           f"(internal p* not marked) | "
           f"CK/CLK pins drawn unwired (net name shown in cell, no clock wires) | "
           f"trojan cells pink | hops={a.hops} | nodes capped at {a.cap}")
    # 单栏大图另存 ✓（便于后期人工加匹配连线 ✓）
    for p, sfx in ((outs[0], "_L"), (outs[1], "_R")):
        if p and p.exists():
            dst = a.out.with_name(a.out.stem + sfx + a.out.suffix)
            save_png(Image.open(p), dst)
            print(f"[out] {dst}")
    compose(outs[0], outs[1], tags[0], tags[1], cap, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
