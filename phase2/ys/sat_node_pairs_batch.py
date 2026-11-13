"""sat_node_pairs_batch.py —— **批量 SAT 证明跨实现节点对**（P2-D/E 的节点级对应 ✓）。

为什么需要它 ✗：
  `sat_sweep_pairs.py` 每对**单独起一次 yosys** ✓ + 只锚 `Trojan*` 网 + `used_a/used_b` 一次 +
  `--per-sig 2 --max-pairs 60` ✗ → 全库只证出 528 对 / 229 个网名 ✗（落盘 134 节点 ✗）。
  本脚本 = **同一批改名为 `sw_<i>` 后一次证明** ✓，并可 `--anchor all` 让掩码**不偏向木马块** ✓
  （否则 mask 本身就是"这是注入块"的标签代理 ✗，AP 会被虚高 ✗）。

两种配对模式 ✓：
  1. **同实例跨配方** ✓（默认）：`--host H --inst I --pairs ys_id:ys_abc,ys_abc:ys_opt`
  2. **跨实例同配方** ✓（a4 三胞胎 E 组必需 ✓）：`--host H --inst a4trojan_s0 --inst-b a4ctlequiv_s0 --recipe ys_abc`

候选生成 ✓（与 `sat_sweep_pairs.py` **同一套** ✓，不重写 ✗）：K 拍顺序仿真签名相同 → 候选；
  `--anchor {all,trojan}`：all = 全网（默认 ✓，掩码无偏）／trojan = 只锚 `Trojan*`（旧口径 ✓）；
  `--budget`：每个配方对最多多少个候选 ✓（成本线性 ✓）；`--shuffle` 固定 seed 打散 ✓（避免按名字序偏置）。

证明 ✓：`equiv_make` + `equiv_simple -undef` + `equiv_induct -undef -seq 4`；批内逐 `sw_i` 解析
  `success!/failed` ✓；整批超时的 `sw_i` 记 `unknown` ✗（**不算失败** ✗）；`--retry-single` 可逐对重试 ✓。

输出 ✓：`tables/node_pairs_sat_node.csv`（独立表 ✗ 不改 `node_pairs_sweep.csv` ✓，避免与在跑批次混口径 ✗）
  列：`host,inst_a,inst_b,recipe,pair,net_a,net_b,sig_hex,status,batch,wall_s,log`
  追加写 + 按 `(host,inst_a,inst_b,recipe,net_a,net_b)` 去重 ✓（可断点续跑 ✓）。

⚠️ 口径 ✓：`proved` = 两 net **组合等价（DFF 输出自由 ✓）**；不含寄存器初值 ✗（与 `-seq 1` 一致 ✓）。
"""
from __future__ import annotations

import argparse
import os
import random
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sat_sweep_pairs as SW          # noqa: E402  复用结构 JSON / 顺序仿真 / 名字引用 ✓

ROOT = SW.ROOT
BASE = SW.BASE
# 证明步骤 ✓（默认 = 原口径：equiv_simple + equiv_induct ✓）
#   基准脚本可临时改写它做 A/B ✓（只跑 equiv_simple → 更快，但可能漏"需要归纳"的等价 ⚠️）
PROVE_STEPS: list[str] = ["equiv_simple -undef", "equiv_induct -undef -seq 4"]
LOGS = SW.LOGS
OUT = BASE / "tables/node_pairs_sat_node.csv"


def gnorm(x) -> str:
    return str(x).strip().lstrip("\\\\")


def pick_views(tdir: Path, host: str, inst: str, recipe: str) -> list[Path]:
    """**canonical 视图优先** ✓（修复 2026-10-23 ✗：原来直接 `sorted()` → `keep*` 变体排在
    `ys_*` 前面（k<y）→ SAT 实际跑在 keep 变体上 ✗，但结论按网名贴到所有变体 ✗ →
    跨变体名字对不上、语义也变味 ✗）。"""
    vs = sorted(tdir.glob(f"{host}__{inst}_d1_s42__*{recipe}.v"))
    if not vs:
        return vs
    canon = tdir / f"{host}__{inst}_d1_s42__{recipe}.v"
    if canon.exists():
        return [canon] + [v for v in vs if v.name != canon.name]
    plain = [v for v in vs if "keep" not in v.name]          # 无 canonical → 非 keep 优先 ✓
    return plain + [v for v in vs if "keep" in v.name]


def struct_iso(v: Path) -> Path:
    """**独立缓存目录** ✓（`logs/struct_node/`）—— 避免与正在跑的 `sat_full_batch` 抢
    `logs/struct/<top>.json` ✗（并发写同一 JSON → 读到半截文件 ✗）。
    2026-10-23 ✓：JSON 已存在且不比 `.v` 旧 → **直接复用**（原来每次都重跑 yosys ✗，每 spec 白烧 3–20 s ✗）。"""
    top = v.stem
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*module\s+([\\A-Za-z_][\w\.$]*)", ln)
        if m:
            top = m.group(1).lstrip("\\")
            break
    out = LOGS / "struct_node" / f"{top}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # ⚠️ 0 字节 JSON = 磁盘写满/中断留下的坏缓存 ✗（mtime 仍可能更新 ✗）→ 必须重建 ✓
    if (out.exists() and out.stat().st_size > 0
            and out.stat().st_mtime >= v.stat().st_mtime):
        return out
    ys = out.with_suffix(".prep.ys")
    ys.write_text("\n".join([f'read_verilog "{SW.wsl(v)}"', f"hierarchy -top {top}",
                             "flatten", "proc", f'write_json "{SW.wsl(out)}"']) + "\n",
                  encoding="utf-8")
    subprocess.run(["wsl", "-e", "bash", "-lc",
                    f'cd "{SW.WSL_ROOT}" && yosys -q -s "{SW.wsl(ys)}"'],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out



def candidates(modA, nA, modB, nB, sigA, sigB, mask, va: Path, vb: Path,
               anchor: str, budget: int, per_sig: int, seed: int) -> list[tuple[str, str, int]]:
    """签名相同 → 候选 ✓（不看名字 ✗）；`--anchor all` 不偏向木马块 ✓。"""
    portA = {gnorm(x) for x in modA["ports"]}
    portB = {gnorm(x) for x in modB["ports"]}
    dwA = {gnorm(x) for x in SW.decl_wires(va)}
    dwB = {gnorm(x) for x in SW.decl_wires(vb)}
    wiresA = {nm for nm, inf in modA.get("netnames", {}).items()
              if len(inf.get("bits", [])) == 1 and gnorm(nm) in dwA}
    wiresB = {nm for nm, inf in modB.get("netnames", {}).items()
              if len(inf.get("bits", [])) == 1 and gnorm(nm) in dwB}

    bucketA: dict[int, list[str]] = {}
    for b, s in sigA.items():
        nm = gnorm(nA.get(b))
        if nm is None or nm in portA or nm not in wiresA:
            continue
        if s in (0, mask):
            continue
        if anchor == "trojan" and "trojan" not in nm.lower():
            continue
        lst = bucketA.setdefault(s, [])
        if nm not in lst:
            lst.append(nm)

    rng = random.Random(seed)
    for lst in bucketA.values():
        rng.shuffle(lst)          # 2026-10-23 ✓：先打散每个签名桶（原来取的是 bit 序前 N 个 ✗ 有偏）

    pool: list[tuple[str, str, int]] = []
    for b, s in sigB.items():
        nm = gnorm(nB.get(b))
        if nm is None or nm in portB or nm not in wiresB:
            continue
        lst = bucketA.get(s, [])
        for nma in (lst if per_sig <= 0 else lst[:per_sig]):
            pool.append((nma, nm, s))

    rng.shuffle(pool)                     # 打散 ✓（否则取到的是"名字字典序前 N 个" ✗）
    out, used_a, used_b = [], set(), set()
    for nma, nmb, s in pool:              # 同一网只能改一次名 ✓（否则 rename 报 not found ✗）
        if nma in used_a or nmb in used_b:
            continue
        used_a.add(nma)
        used_b.add(nmb)
        out.append((nma, nmb, s))
        if budget > 0 and len(out) >= budget:      # budget<=0 = 取满整个池子 ✓
            break
    return out


def candidates_by_name(modA, nA, modB, nB, sigA, sigB, mask, va: Path, vb: Path,
                       anchor: str, budget: int, seed: int,
                       require_sig: bool = True) -> list[tuple[str, str, int]]:
    """**同名候选** ✓（B05 口径，2026-10-23 新增 ✓）。

    为什么加它 ✓：签名桶候选每视图只有 3–5 k（`per_sig` 限制 ✗），而**同名网**在 ABC 家族
    （`abc/opt/aig/nand`）里有 **14–20 k** ✓（实测 s38417 abc∩opt = 14,057 ✓），且这些同名对
    实测 **~100% 可证** ✓（abc:opt 1,467/1,469、abc:aig 300/300）→ **单位时间覆盖 ×3–4** ✓。

    `require_sig=True`（默认 ✓）：同名 **且 32-bit 仿真签名相同** 才作候选 ✓
    （把 `differ` 率压到最低 ✓；关掉就是纯同名 ⚠️）。
    """
    portA = {gnorm(x) for x in modA["ports"]}
    portB = {gnorm(x) for x in modB["ports"]}
    dwA = {gnorm(x) for x in SW.decl_wires(va)}
    dwB = {gnorm(x) for x in SW.decl_wires(vb)}
    wiresA = {gnorm(nm) for nm, inf in modA.get("netnames", {}).items()
              if len(inf.get("bits", [])) == 1 and gnorm(nm) in dwA}
    wiresB = {gnorm(nm) for nm, inf in modB.get("netnames", {}).items()
              if len(inf.get("bits", [])) == 1 and gnorm(nm) in dwB}
    nbA: dict[str, int] = {}
    for b, nm in nA.items():
        nbA.setdefault(gnorm(nm), b)
    nbB: dict[str, int] = {}
    for b, nm in nB.items():
        nbB.setdefault(gnorm(nm), b)

    common = sorted((wiresA & wiresB) - portA - portB)
    if anchor == "trojan":
        common = [x for x in common if "trojan" in x.lower()]
    rng = random.Random(seed)
    rng.shuffle(common)
    out: list[tuple[str, str, int]] = []
    for nm in common:
        ba, bb = nbA.get(nm), nbB.get(nm)
        if ba is None or bb is None:
            continue
        sa, sb = sigA.get(ba), sigB.get(bb)
        if sa in (None, 0, mask) or sb in (None, 0, mask):
            continue
        if require_sig and sa != sb:
            continue
        out.append((nm, nm, sa))
        if budget > 0 and len(out) >= budget:
            break
    return out


def parse_batch(out: str, n: int) -> dict[int, str]:
    """逐 `sw_i` 解析 ✓；未出现 = `unknown` ✗（批超时 → 不冤枉成 differ ✓）。"""
    st: dict[int, str] = {}
    for m in re.finditer(r"Trying to prove \$equiv for \\+sw_(\d+):\s*(success!|failed)", out):
        st[int(m.group(1))] = "proved" if m.group(2) == "success!" else "differ"
    for m in re.finditer(r"for \\+sw_(\d+):\s*(success!|failed)", out):
        st.setdefault(int(m.group(1)), "proved" if m.group(2) == "success!" else "differ")
    return {i: st.get(i, "unknown") for i in range(n)}


def prove_batch(tag: str, fa: Path, fb: Path, topA: str, topB: str,
                batch: list[tuple[str, str, int]], timeout: int) -> tuple[dict[int, str], float, Path]:
    lines = [f'read_verilog "{SW.wsl(fa)}"', f'read_verilog "{SW.wsl(fb)}"',
             f"select -module {topA}"]
    for i, (na, _nb, _s) in enumerate(batch):
        lines.append(f"rename {SW.ref(na)} sw_{i}")
    lines.append(f"select -module {topB}")
    for i, (_na, nb, _s) in enumerate(batch):
        lines.append(f"rename {SW.ref(nb)} sw_{i}")
    lines += [f"equiv_make {topA} {topB} equiv", "select -module equiv"]
    lines += list(PROVE_STEPS)
    lines.append("equiv_status")
    ys = LOGS / "batch_pairs" / f"{tag}.ys"
    ys.parent.mkdir(parents=True, exist_ok=True)
    ys.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t0 = time.time()
    try:
        p = subprocess.run(["wsl", "-e", "bash", "-lc",
                            f'cd "{SW.WSL_ROOT}" && timeout {timeout} yosys -s "{SW.wsl(ys)}"'],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout + 120)
        out = (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        out = "TIMEOUT"
    (ys.with_suffix(".log")).write_text(out, encoding="utf-8")
    return parse_batch(out, len(batch)), round(time.time() - t0, 2), ys.with_suffix(".log")


def specs(a) -> list[dict]:
    """把参数展开成 [(inst_a, inst_b, recipe_a, recipe_b, pair_label)] ✓。"""
    out = []
    if a.inst_b:
        for rcp in [x.strip() for x in str(a.recipe).split(",") if x.strip()]:
            ra = rcp.replace("ys_", "")
            out.append(dict(inst_a=a.inst, inst_b=a.inst_b, recipe_a=ra, recipe_b=ra,
                            pair="cross"))
        return out
    for pr in [x.strip() for x in str(a.pairs).split(",") if ":" in x]:
        ra, rb = [x.strip().replace("ys_", "") for x in pr.split(":")]
        out.append(dict(inst_a=a.inst, inst_b=a.inst, recipe_a=ra, recipe_b=rb,
                        pair=f"{ra}:{rb}"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--inst-b", default="", help="跨实例模式 ✓（如 a4ctlequiv_s0 ✓）")
    ap.add_argument("--recipe", default="ys_abc", help="跨实例模式的配方 ✓（可逗号分隔 ✓）")
    ap.add_argument("--pairs", default="ys_id:ys_abc,ys_abc:ys_opt",
                    help="同实例跨配方 ✓（`ys_a:ys_b` 逗号分隔 ✓）")
    ap.add_argument("--anchor", choices=["all", "trojan"], default="all")
    ap.add_argument("--budget", type=int, default=800, help="每个配方对最多候选数 ✓")
    ap.add_argument("--per-sig", type=int, default=2)
    ap.add_argument("--cand", choices=["sig", "name"], default="sig",
                    help="候选源 ✓：sig=签名桶（名字无关 ✓）；name=同名 + 签名校验 ✓"
                         "（ABC 家族池 14–20 k，实测 ~100%% 可证 ✓，覆盖 ×3–4 ✓）")
    ap.add_argument("--prove-mode", choices=["full", "simple"], default="full",
                    help="证明步骤 ✓：full=`equiv_simple + equiv_induct`（原口径 ✓）；"
                         "simple=只 `equiv_simple`（实测 600 对里 proved 数不变、快 6–25%% ✓，"
                         "仅建议用于 ABC 家族对 ✓）")
    ap.add_argument("--name-sig", choices=["on", "off"], default="on",
                    help="name 模式下是否要求 32-bit 签名相同 ✓（默认 on ✓）")
    ap.add_argument("--batch", type=int, default=25, help="每批证明多少个节点对 ✓")
    ap.add_argument("--timeout", type=int, default=90, help="单批 yosys 超时秒 ✓")
    ap.add_argument("--retry-single", action="store_true", help="unknown 逐对重试 ✓（慢 ✗）")
    ap.add_argument("--workers", type=int, default=1,
                    help="并行 yosys 批次数 ✓（默认 1；WSL 只有 ~7 GB → 建议 2–3 ⚠️）")
    ap.add_argument("--skip-covered", action="store_true",
                    help="跳过**两侧都已被 proved 覆盖**的候选 ✓（省重复证明 ✓）")
    ap.add_argument("--k", type=int, default=32)
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--host-fold", default="hosts_bt31")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--limit-specs", type=int, default=0, help=">0 只跑前 N 个 spec ✓（pilot ✓）")
    ap.add_argument("--force", action="store_true",
                    help="忽略断点记录 ✓（改大 --budget 重跑时必须加 ✗ 否则会被跳过 ✗）")
    a = ap.parse_args()
    if a.prove_mode == "simple":
        global PROVE_STEPS
        PROVE_STEPS = ["equiv_simple -undef"]
        print("[prove] **simple 模式** ✓（只 equiv_simple；实测 proved 数不变、快 6–25% ⚠️）")


    tdir = ROOT / "generate_trans" / "folds" / a.host_fold / "trans"
    sp = specs(a)
    if a.limit_specs:
        sp = sp[: a.limit_specs]
    out_p = Path(a.out)
    done = set()
    cov_a: dict[tuple, set] = defaultdict(set)
    cov_b: dict[tuple, set] = defaultdict(set)
    if out_p.exists():
        old = pd.read_csv(out_p, encoding="utf-8-sig").fillna("")
        done = set(zip(old["host"], old["inst_a"], old["inst_b"],
                       old["recipe_a"], old["recipe_b"]))
        if a.skip_covered:
            pr = old[old["status"].astype(str) == "proved"]
            for (h, ia, ra), g in pr.groupby(["host", "inst_a", "recipe_a"]):
                cov_a[(h, ia, ra)].update(g["net_a"].astype(str))
            for (h, ib, rb), g in pr.groupby(["host", "inst_b", "recipe_b"]):
                cov_b[(h, ib, rb)].update(g["net_b"].astype(str))
            print(f"[skip-covered] 已覆盖 net_a {sum(len(v) for v in cov_a.values())}"
                  f"｜net_b {sum(len(v) for v in cov_b.values())}")

    def _write_rows(rows: list[dict]) -> None:
        """增量落盘 + **状态取强** ✓（proved > differ > no_candidate > unknown）。
        修复 2026-10-23 ✗：原来 `keep='last'` 会把已 proved 的对在重跑时降级成 unknown ✗。
        ✗ 另修：直接 `to_csv(out_p)` 在并发读/杀毒扫描时会 `OSError(22)` → 改**临时文件 + os.replace + 重试** ✓。"""
        df = pd.DataFrame(rows)
        if out_p.exists():
            for _try in range(4):
                try:
                    df = pd.concat([pd.read_csv(out_p, encoding="utf-8-sig").fillna(""), df],
                                   ignore_index=True)
                    break
                except Exception:
                    time.sleep(1.0)
        rank = {"proved": 3, "differ": 2, "no_candidate": 1, "unknown": 0}
        df["_rank"] = df["status"].map(lambda x: rank.get(str(x), 0))
        df = (df.sort_values("_rank", kind="mergesort")
                .drop_duplicates(subset=["host", "inst_a", "inst_b", "recipe_a",
                                         "recipe_b", "net_a", "net_b"], keep="last")
                .drop(columns="_rank"))
        out_p.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_p.with_name(out_p.stem + ".tmp.csv")
        for attempt in range(6):
            try:
                df.to_csv(tmp, index=False, encoding="utf-8-sig")
                os.replace(tmp, out_p)
                return
            except OSError:
                if attempt == 5:
                    raise
                time.sleep(1.5 * (attempt + 1))

    print(f"[in] host={a.host} inst={a.inst} specs={len(sp)} anchor={a.anchor} "
          f"budget={a.budget} batch={a.batch} timeout={a.timeout}s")
    for k, s in enumerate(sp, 1):
        key = (a.host, s["inst_a"], s["inst_b"], s["recipe_a"], s["recipe_b"])
        va = pick_views(tdir, a.host, s["inst_a"], s["recipe_a"])
        vb = pick_views(tdir, a.host, s["inst_b"], s["recipe_b"])
        tag = f"{a.host}__{s['inst_a']}__vs__{s['inst_b']}__{s['recipe_a']}__{s['recipe_b']}"
        if not (va and vb):
            print(f"[skip] {tag} 缺 .v ✗")
            continue
        if key in done and not a.force:
            print(f"[skip] {tag} 已在表里 ✓")
            continue
        print(f"\n=== [{k}/{len(sp)}] {tag}")
        topA, modA, nA = SW.load_json(struct_iso(va[0]))
        topB, modB, nB = SW.load_json(struct_iso(vb[0]))
        t0 = time.time()
        sigA, mask = SW.simulate_seq(modA, nA, a.k, a.seed, a.cycles)
        sigB, _ = SW.simulate_seq(modB, nB, a.k, a.seed, a.cycles)
        if a.cand == "name":
            cand = candidates_by_name(modA, nA, modB, nB, sigA, sigB, mask, va[0], vb[0],
                                      a.anchor, a.budget, a.seed, a.name_sig == "on")
            print(f"  [cand] {len(cand)} 对 ✓（**同名** ✓ sig_check={a.name_sig} ✓ "
                  f"sim {time.time()-t0:.1f}s ✓）")
        else:
            cand = candidates(modA, nA, modB, nB, sigA, sigB, mask, va[0], vb[0],
                              a.anchor, a.budget, a.per_sig, a.seed)
            print(f"  [cand] {len(cand)} 对 ✓（sim {time.time()-t0:.1f}s ✓、anchor={a.anchor} ✓）")
        if a.skip_covered and cand:
            sa = cov_a.get((a.host, s["inst_a"], s["recipe_a"]), set())
            sb = cov_b.get((a.host, s["inst_b"], s["recipe_b"]), set())
            keep = [c for c in cand if not (c[0] in sa and c[1] in sb)]
            if len(keep) != len(cand):
                print(f"  [skip-covered] 去掉 {len(cand)-len(keep)} 对已覆盖 ✓（剩 {len(keep)}）")
            cand = keep
        if not cand:
            row = dict(host=a.host, inst_a=s["inst_a"], inst_b=s["inst_b"],
                       recipe_a=s["recipe_a"], recipe_b=s["recipe_b"], pair=s["pair"],
                       net_a="", net_b="", sig_hex="", status="no_candidate",
                       batch=-1, wall_s=0.0, log="")
            df = pd.DataFrame([row])
            if out_p.exists():
                df = pd.concat([pd.read_csv(out_p, encoding="utf-8-sig").fillna(""), df],
                               ignore_index=True)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_p, index=False, encoding="utf-8-sig")
            continue
        nb = max(1, a.batch)
        blocks = [(bi // nb, cand[bi: bi + nb]) for bi in range(0, len(cand), nb)]

        def _one_block(item):
            bidx, blk = item
            st, wall, logp = prove_batch(f"{tag}__b{bidx:03d}",
                                         va[0], vb[0], topA, topB, blk, a.timeout)
            if a.retry_single:
                for i, (na_, nb_, sg_) in enumerate(blk):
                    if st.get(i) == "unknown":
                        st2, w2, lp = prove_batch(f"{tag}__b{bidx:03d}__r{i:03d}",
                                                  va[0], vb[0], topA, topB,
                                                  [(na_, nb_, sg_)], a.timeout)
                        wall += w2
                        st[i] = st2.get(0, "unknown")
                        logp = lp
            rows = [dict(host=a.host, inst_a=s["inst_a"], inst_b=s["inst_b"],
                         recipe_a=s["recipe_a"], recipe_b=s["recipe_b"], pair=s["pair"],
                         net_a=na_, net_b=nb_, sig_hex=f"{sg_:x}"[:16],
                         status=st.get(i, "unknown"), batch=bidx,
                         wall_s=wall, log=str(logp.relative_to(ROOT)))
                    for i, (na_, nb_, sg_) in enumerate(blk)]
            n_ok = sum(1 for v in st.values() if v == "proved")
            print(f"  [batch {bidx:02d}] {n_ok}/{len(blk)} proved ✓ {wall:.1f}s")
            return rows

        if a.workers > 1 and len(blocks) > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=a.workers) as ex:
                futs = [ex.submit(_one_block, b) for b in blocks]
                for f in as_completed(futs):
                    _write_rows(f.result())
        else:
            for b in blocks:
                _write_rows(_one_block(b))
        done.add(key)

    if out_p.exists():
        df = pd.read_csv(out_p, encoding="utf-8-sig")
        print(f"\n[out] {out_p}（{len(df)} 行 ✓）")
        print(df["status"].value_counts().to_string())
        pr = df[df.status == "proved"]
        print(f"  唯一 net_a {pr['net_a'].nunique()}｜唯一 net_b {pr['net_b'].nunique()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

