"""f8_yosys.py -- F8 的 **yosys 原生原理图**版（单元框带引脚名 + 网名椭圆 ✓）。

做法：
  1. 对两侧视图各跑一次 `yosys show`：`read_verilog → hierarchy -auto-top → flatten →
     select c:*Trojan* (+k 跳锥) → show -format png`；
  2. 两栏 PNG 横排拼接，加标题与图注（CEC 状态 / 匹配对数 ✓）；
  3. 同时保留 `.dot` 供后续改样式 ✓。

为什么用它 ✓：yosys 的 `show` 是**网表原生**渲染（单元=方框+pins、网=椭圆），
比手绘更像真实电路图 ✓；缺点是布局不能跨栏连线 ✗（跨栏匹配箭头仍用 `f8_rewrite_case.py` ✓）。

用法：
  ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/f8_yosys.py --host s38417t100 --inst injalpha --ra ys_id --rb ys_abc --hops 1
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f8_rewrite_case as F8

WSL_ROOT = _eqguard_path('', wsl=True)
VDIR_WSL = f"{WSL_ROOT}/generate_trans/folds/hosts_bt31/trans"
TMP_WSL = "/mnt/c/Users/91344/AppData/Local/Temp"


def cell_cone(nodes: list, cons: dict, hops: int) -> list:
    """在 .v 侧算 k 跳邻域 ✓（与 yosys 的 %ci/%co 结果应一致 ✓，用于图注核对 ✓）。"""
    seen = set(nodes)
    for _ in range(hops):
        add = set()
        for c in seen:
            add |= {u for u in cons.get(c, set())}
        seen |= add
    return sorted(seen)


def render_side(view: str, hops: int, tag: str) -> Path | None:
    """> 返回生成的 PNG 路径 ✓（失败 None ✓）。"""
    ys = Path(TMP_WSL.replace("/mnt/c/", "C:/")) / f"ysf8_{tag}.ys"
    out_png = Path(TMP_WSL.replace("/mnt/c/", "C:/")) / f"ysf8_{tag}.png"
    hop = max(1, hops)
    script = "\n".join([
        f'read_verilog {VDIR_WSL}/{view}.v',
        "hierarchy -auto-top",
        "flatten",
        "select -set tro c:*Trojan*",
        f"select -set cone @tro %ci{hop} %co{hop}",
        "stat @cone",
        f"show -format png -prefix {TMP_WSL}/ysf8_{tag} @cone",
    ]) + "\n"
    ys.write_text(script, encoding="ascii")
    ys_wsl = f"{TMP_WSL}/ysf8_{tag}.ys"
    r = subprocess.run(["wsl", "-e", "bash", "-lc",
                        f'cd "{WSL_ROOT}" && yosys -q -s "{ys_wsl}"'],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300)
    if out_png.exists():
        return out_png
    print(f"[warn] {tag}: yosys 没产出 PNG（rc={r.returncode}）\n{r.stderr[-400:]}")
    return None


def compose(p_left: Path | None, p_right: Path | None, title_l: str, title_r: str,
            caption: str, out: Path) -> None:
    ims = [Image.open(p).convert("RGB") for p in (p_left, p_right) if p]
    if not ims:
        raise SystemExit("[ERROR] 两张都失败 ✗")
    h = max(i.height for i in ims)
    ims = [i.resize((int(i.width * h / i.height), h)) for i in ims]
    gap, top, bottom = 60, 70, 90
    W = sum(i.width for i in ims) + gap * (len(ims) + 1)
    canvas = Image.new("RGB", (W, h + top + bottom), "white")
    x = gap
    titles = [t for t in (title_l, title_r) if t]
    for i, im in enumerate(ims):
        canvas.paste(im, (x, top))
        if i < len(titles):
            ImageDraw.Draw(canvas).text((x, 28), titles[i], fill=(20, 20, 20))
        x += im.width + gap
    d = ImageDraw.Draw(canvas)
    d.text((gap, top + h + 30), caption, fill=(40, 40, 40))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print(f"[out] {out}（{W}x{h + top + bottom}）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="s38417t100")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--ra", default="ys_id")
    ap.add_argument("--rb", default="ys_abc")
    ap.add_argument("--hops", type=int, default=1)
    ap.add_argument("--out", type=Path, default=F8.FIGS / "F8_yosys.png")
    a = ap.parse_args()

    va = f"{a.host}__{a.inst}_d1_s42__{a.ra}"
    vb = f"{a.host}__{a.inst}_d1_s42__{a.rb}"
    print(f"[in] {va} vs {vb}（hops={a.hops}）")
    pa = render_side(va, a.hops, f"{a.host}_{a.inst}_{a.ra}")
    pb = render_side(vb, a.hops, f"{a.host}_{a.inst}_{a.rb}")

    # 匹配对数（区域内）
    import pandas as pd
    d = pd.read_csv(F8.T / "node_pairs_sat_node.csv", encoding="utf-8-sig").fillna("")
    ra, rb = a.ra.replace("ys_", ""), a.rb.replace("ys_", "")
    m = ((d["host"] == a.host) & (d["inst_a"] == a.inst) & (d["inst_b"] == a.inst)
         & (d["recipe_a"] == ra) & (d["recipe_b"] == rb) & (d["status"] == "proved"))
    n_pairs = int(len(d[m].drop_duplicates()))
    caption = (f"yosys show | cells selected by c:*Trojan* + {a.hops}-hop cone | "
               f"proved cross-implementation pairs for this spec: {n_pairs} "
               f"(see F8_rewrite_case.png for the matched-signal arrows)")
    compose(pa, pb, f"{va}  (pre-ABC)" if "id" in a.ra else f"{va}  (post-ABC)",
            f"{vb}  (post-ABC)" if "abc" in a.rb else f"{vb}", caption, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
