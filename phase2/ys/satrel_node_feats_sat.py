"""satrel_node_feats_sat.py —— **P2-C 的 SAT-only 节点级特征**（三层证据 ✓，每层单独 mask ✓）。

与 `satrel_node_feats.py` 的区别 ✓：
  · 旧版 6 维里混了"名字可解码标记""trusted_trojan 区域前缀"等**非 SAT** 信息 ✗，且只覆盖 134 节点 ✗；
  · 本版 **所有非零值都来自 SAT 表** ✓（`functional_relations.csv` / `node_pairs_sweep.csv` /
    `region_pairs.csv`），覆盖不到的节点全 0 + `mask=0` ✓（= **未知** ✗，不是"无关系" ✗）。

数据链路（已实测 ✓）：
  · `.pt` 第 i 个节点 = `node_names_trans.txt` 第 i 行 ✓（`dump_node_names.py` 与 `file_ids` 逐元素校验 ✓）；
  · 名字两型 ✓：`g__<原名>_<i>`（如 `g__TrojanAHJ.B_86`）与 `g_<原名>_<i>`（如 `g_U0_p1_122`）
    → 正则 `^g_{1,2}(.+)_\\d+$` 还原 `<原名>` ✓；另保留**精确名**直查 ✓（原样即命中时优先 ✓）。

输出（写到 `--pt-dir` ✓，与 `satrel_view_feats.npy` 同 row 顺序 ✓）：
    satrel_node_feats_sat.npy   (n_trans, 14) float32
    satrel_node_mask_sat.npy    (n_trans,  3) float32   0=S 关系层 / 1=P 节点对层 / 2=R 区域层
    satrel_node_meta_sat.json   逐层覆盖率 + 未命中计数 + 口径说明
    <tables>/satrel_node_sat_covered.csv   被覆盖节点明细（供 P4 出图 ✓；行数不大 ✓）

14 维（下标 / 语义 / 来源）：
    [0] is_target          节点 = 某条关系的 `target`                functional_relations
    [1] is_cut_data        节点在 `cut_nets` 里且非 MUX 选择端        functional_relations
    [2] is_cut_ctrl        节点 = MUX 关系的选择端 `S0`（控制信号 ✓） functional_relations
    [3] is_cell            节点 = 该关系的改写门 `cell`               functional_relations
    [4] decided            SAT 判定"割集足以决定目标" ✓               functional_relations（下发到 cut ✓）
    [5] influence          SAT 判定"控制信号在合法输入下能影响目标" ✓ functional_relations（下发到 cut ✓）
    [6] observable         SAT/BMC 判定"影响可传到 PO/DFF" ✓          functional_relations（下发到 target ✓）
    [7] reach_depth_norm   1/(1+reach_depth) ✓（无则 0 ✓）            functional_relations
    [8] log1p(n_proved)    该节点 SAT sweeping 已证等价对计数         node_pairs_sweep
    [9] log1p(n_differ)    该节点 SAT sweeping 已判不等价对计数       node_pairs_sweep
    [10] proved_ratio      proved/(proved+differ)                     node_pairs_sweep
    [11] region_jaccard    所属区域跨实现边界匹配 Jaccard（取最大 ✓） region_pairs
    [12] region_matched    所属区域 match_type ∈ {1:1,1:N,N:1} ✓     region_pairs
    [13] log1p(region_edges) 所属区域的 SAT 已证跨实现边数             region_pairs

⚠️ 口径（必须写进论文 ✗ 不能省）：
  1. **候选来源是注入记录** ✓（P0 的 ctrl/target/cut 由 `Trojan*` 挖出 ✓）→ C 组属 **privileged
     information** ✓；本脚本提供 `--drop-identity` 把 [0..3] 置零 ✓，用于**去身份消融** ⚠️；
  2. 覆盖不到的节点 = `unknown` ✗，**不得**当"无功能关系"写 ✗；
  3. `region_jaccard / region_edges` 是**区域级** SAT 证据下发到节点 ⚠️（节点在该区域内 ✓，但
     数值本身是区域级的 ✗），论文措辞写 "region-resolved" ✓，不写 "per-node proved" ✗；
  4. 同 (host, inst, recipe) 的多个 `keep*` 变体共享同一 SAT 结论 ⚠️（SAT 只在其中一个 .v 上跑过 ✓）。
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
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netmap as NM      # noqa: E402  SAT 网名 → 节点 id（直查 + assign + 驱动单元 ✓）

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
T = BASE / "tables"
DEC = re.compile(r"^g_{1,2}(.+)_\d+$")


def base_name(n: str) -> str:
    """`g__TrojanAHJ.B_86` → `TrojanAHJ.B`；`g_U0_p1_122` → `U0_p1`；否则原样 ✓。"""
    m = DEC.match(n or "")
    return m.group(1) if m else (n or "")


def views_for(views: list[str], host: str, inst: str, recipe: str) -> list[str]:
    """同一 (host, inst, recipe) 可能有多个 keep 变体 ✓ → **全部**都打标 ✓（同一 SAT 结论 ⚠️）。"""
    pre, suf = f"{host}__{inst}_", f"__{recipe}"
    return [v for v in views if v.startswith(pre) and v.endswith(suf)]


def load_names(pt_dir: Path, work: Path) -> tuple[list[str], list[str]]:
    txt = pt_dir / "node_names_trans.txt"
    if not txt.exists():
        raise SystemExit(f"[ERROR] 缺 {txt} ✗（先跑 phase2/ys/dump_node_names.py ✓）")
    names = txt.read_text(encoding="utf-8").split("\n")
    meta = json.loads((work / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fid = meta["file_ids"]
    if len(names) != len(fid):
        raise SystemExit(f"[ERROR] node_names {len(names)} != file_ids {len(fid)} ✗")
    return names, fid


def build_maps(names: list[str], fid: list[str], views: list[str]):
    """逐视图：精确名 → 节点下标 ✓、还原名 → 节点下标 ✓。"""
    exact: dict[str, dict[str, list[int]]] = {v: {} for v in views}
    basem: dict[str, dict[str, list[int]]] = {v: {} for v in views}
    for i, (n, v) in enumerate(zip(names, fid)):
        exact[v].setdefault(n, []).append(i)
        basem[v].setdefault(base_name(n), []).append(i)
    return exact, basem


def resolve(exact_v: dict[str, list[int]], base_v: dict[str, list[int]], nm: str) -> list[int]:
    """先精确 ✓ 再还原 ✓（网表名可能带反斜杠 / 位宽后缀 ✓）。"""
    key = str(nm).strip().lstrip("\\")
    ids = exact_v.get(key)
    if ids:
        return ids
    return base_v.get(key) or base_v.get(key.split("[")[0]) or []


def split_pair(pair: str) -> tuple[str, str]:
    a = [x.strip() for x in str(pair).split(":") if x.strip()]
    return (a[0], a[1]) if len(a) >= 2 else ("", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed")
    ap.add_argument("--work", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31")
    ap.add_argument("--tables", type=Path, default=T)
    ap.add_argument("--drop-identity", action="store_true",
                    help="把 [0..3]（is_target/is_cut_*/is_cell）置零 ✓ → **去身份消融** ⚠️")
    ap.add_argument("--views-dir", type=Path, default=None,
                    help="fold 的 trans/ 目录（默认 <work>/trans ✓，用于 网→驱动单元 映射 ✓）")
    ap.add_argument("--no-netmap", action="store_true",
                    help="回退到**旧口径**（只名字直查 ⚠️，命中率约 4–26%% ✗，仅供对照组 ✓）")
    ap.add_argument("--netmap-no-json", action="store_true",
                    help="不用 yosys JSON 判输出脚 ⚠️（只用 .v 正则 + 保守输出脚 ✓）")
    ap.add_argument("--netmap-max-alias", type=int, default=8,
                    help="assign 别名最多追几层 ✓（默认 8 ✓）")
    ap.add_argument("--extra-pairs", choices=["auto", "off"], default="auto",
                    help="额外并入 B05 的 `node_pairs.csv`（70,168 proved 行 ✓ 默认 auto ✓）")
    ap.add_argument("--incident", action="store_true",
                    help="⚠️ 证据贴到 driver + sinks（incident 口径 ⚠️，实测 ×2.5–4.5）")
    ap.add_argument("--tag-suffix", default="",
                    help="输出文件名后缀 ✓（如 `_driver` → `satrel_node_feats_sat_driver.npy` ✓，"
                         "用于同时保留 driver-only 严格口径 ✓；非空时不覆盖 covered.csv ✓）")
    ap.add_argument("--permute-within-view", action="store_true",
                    help="⚠️ 视图内置换对照 ✓：每个视图的 covered 数量/数值分布不变，只打乱贴到哪个节点 ✓"
                         "（用于证明不是'证据存在性'捷径 ✓）")
    ap.add_argument("--perm-seed", type=int, default=42)
    a = ap.parse_args()
    pt_dir, tabs = a.pt_dir, a.tables

    names, fid = load_names(pt_dir, a.work)
    n = len(fid)
    views = sorted(set(fid))
    exact, basem = build_maps(names, fid, views)
    # 网名 → 节点 id 映射器 ✓（2026-10-23：直查 + assign 别名 + 网→驱动单元 ✓）
    if a.no_netmap:
        class _LegacyMap:                       # 旧口径对照组 ⚠️（只有直查 ✗）
            def ids(self, view, net):
                return resolve(exact[view], basem[view], net)

            def summary(self):
                return {"mode": "legacy-direct-only", "hit_rate": None}

        mapper = _LegacyMap()
        print("[netmap] **旧口径**（只名字直查 ⚠️，仅供对照 ✓）")
    else:
        vdir = a.views_dir or (a.work / "trans")
        mapper = NM.NetMapper(exact, basem, vdir,
                              struct_dirs=NM.default_struct_dirs(BASE),
                              use_json=not a.netmap_no_json,
                              max_alias=a.netmap_max_alias,
                              include_sinks=bool(a.incident))
        print(f"[netmap] 已启用 ✓ views_dir={vdir}｜json={not a.netmap_no_json}"
              f"｜max_alias={a.netmap_max_alias}｜incident={bool(a.incident)}")
    y = None
    _yp = pt_dir / "y_trans.npy"
    if _yp.exists():
        y = np.load(_yp)
    else:
        import torch
        _d = torch.load(pt_dir / "trans_graph.pt", map_location="cpu",
                        weights_only=False, mmap=True)
        y = np.asarray(_d.y)
        del _d

    F = np.zeros((n, 14), np.float32)
    mk = np.zeros((n, 3), np.float32)
    prov: dict[str, int] = defaultdict(int)      # 未命中计数 ✓
    hit_s = np.zeros(n, bool)
    hit_p = np.zeros(n, bool)
    hit_r = np.zeros(n, bool)

    # ---------------- S 层：功能关系（P0） ----------------
    fr_p = tabs / "functional_relations.csv"
    if not fr_p.exists():
        raise SystemExit(f"[ERROR] 缺 {fr_p} ✗（先跑 sat_functional_relations.py ✓）")
    fr = pd.read_csv(fr_p, encoding="utf-8-sig").fillna("")
    n_fr_rows = n_fr_views = 0
    for _, r in fr.iterrows():
        vs = views_for(views, str(r["host"]), str(r["inst"]), str(r["recipe"]))
        if not vs:
            prov["S_no_view"] += 1
            continue
        n_fr_rows += 1
        st = str(r.get("status", ""))
        decided = float(r.get("decided", 0) or 0)
        infl = float(r.get("influence", 0) or 0)
        obs = float(r.get("observable", 0) or 0)
        dep = float(r.get("reach_depth", 0) or 0)
        dep_n = 0.0 if (st == "timeout" or dep <= 0) else 1.0 / (1.0 + dep)
        cuts = [x.strip() for x in str(r.get("cut_nets", "")).split(";") if x.strip()]
        ctrl = cuts[-1] if (str(r.get("kind", "")) == "mux" and cuts) else ""
        for v in vs:
            n_fr_views += 1
            t_ids = mapper.ids(v, str(r.get("target", "")))
            for i in t_ids:
                F[i, [0, 6]] = [1.0, obs]
                F[i, 7] = max(F[i, 7], dep_n)
                hit_s[i] = True
            for cu in cuts:
                for i in mapper.ids(v, cu):
                    F[i, 2 if cu == ctrl else 1] = 1.0
                    F[i, [4, 5]] = [decided, infl]
                    hit_s[i] = True
            for i in mapper.ids(v, str(r.get("cell", ""))):
                F[i, 3] = 1.0
                hit_s[i] = True
            if not t_ids:
                prov["S_target_miss"] += 1


    # ---------------- P 层：SAT 节点对（旧 sweep ✓ + 新批量 SAT ✓ 合并） ----------------
    proved: dict[int, int] = defaultdict(int)
    differ: dict[int, int] = defaultdict(set)      # 记录对端 → 计数去重 ✓
    partner: dict[int, set[str]] = defaultdict(set)
    n_sw = n_batch = 0

    def pair_rows():
        """统一成长表：`(host, inst, recipe, net, status, partner_key)` ✓。

        三个来源 ✓：
          · `node_pairs_sweep.csv`（视图级 sweeping ✓）
          · `node_pairs_sat_node.csv`（批量 SAT ✓）
          · **`node_pairs.csv`（B05，70,168 proved 行 ✓，2026-10-23 新增 ✓）**
            → B05 是**同名候选**：`net` 在 pair 两侧同名 ✓ → 可做**传递闭包**
              （同一 (host,inst,net) 的 proved 配方并集 → 该网在闭包里所有配方视图都算已证 ✓）
            → 与上面两张表**按 (host,inst,recipe,net) 去重** ✓（避免同一网重复计数 ✗）
        """
        seen: set[tuple] = set()
        p1 = tabs / "node_pairs_sweep.csv"
        if p1.exists():
            sw = pd.read_csv(p1, encoding="utf-8-sig").fillna("")
            for (host, inst, pair), g in sw.groupby(["host", "inst", "pair"]):
                ra, rb = split_pair(pair)
                if not (ra and rb):
                    continue
                for col, own, other in (("net_a", ra, rb), ("net_b", rb, ra)):
                    for nm, stt in zip(g[col].astype(str), g["status"].astype(str)):
                        seen.add((str(host), str(inst), own, nm))
                        yield str(host), str(inst), own, nm, stt, other
        p2 = tabs / "node_pairs_sat_node.csv"
        if p2.exists():
            sw2 = pd.read_csv(p2, encoding="utf-8-sig").fillna("")
            for _, r in sw2.iterrows():
                ia, ib = str(r["inst_a"]), str(r["inst_b"])
                # ⚠️ 批量表的 recipe 是 `id/abc/opt` ✗（无 `ys_` 前缀 ✗）；视图名要 `__ys_id` ✓
                ra, rb = str(r["recipe_a"]), str(r["recipe_b"])
                ra = ra if ra.startswith("ys_") else f"ys_{ra}"
                rb = rb if rb.startswith("ys_") else f"ys_{rb}"
                seen.add((str(r["host"]), ia, ra, str(r["net_a"])))
                seen.add((str(r["host"]), ib, rb, str(r["net_b"])))
                yield str(r["host"]), ia, ra, str(r["net_a"]), str(r["status"]), f"{ib}/{rb}"
                yield str(r["host"]), ib, rb, str(r["net_b"]), str(r["status"]), f"{ia}/{ra}"
        p0 = tabs / "node_pairs.csv"
        if a.extra_pairs != "off" and p0.exists():
            b05 = pd.read_csv(p0, encoding="utf-8-sig").fillna("")
            b05 = b05[b05["status"].astype(str) == "proved"]
            for (host, inst, net), g in b05.groupby(["host", "inst", "net"]):
                rset: set[str] = set()
                for pr in g["pair"].astype(str):
                    rset |= {x.strip() for x in pr.split(":") if x.strip()}
                if not rset:
                    continue
                others = ",".join(sorted(rset))
                for rcp in sorted(rset):                       # 传递闭包 ✓
                    if (str(host), str(inst), rcp, str(net)) in seen:
                        continue
                    yield str(host), str(inst), rcp, str(net), "proved", f"b05|{others}"

    if (tabs / "node_pairs_sweep.csv").exists():
        n_sw = len(pd.read_csv(tabs / "node_pairs_sweep.csv", encoding="utf-8-sig"))
    if (tabs / "node_pairs_sat_node.csv").exists():
        n_batch = len(pd.read_csv(tabs / "node_pairs_sat_node.csv", encoding="utf-8-sig"))
    n_b05 = 0
    if a.extra_pairs != "off" and (tabs / "node_pairs.csv").exists():
        _b05 = pd.read_csv(tabs / "node_pairs.csv", encoding="utf-8-sig")
        n_b05 = len(_b05)
        del _b05

    for host, inst, rcp, nm, stt, pkey in pair_rows():
        for v in views_for(views, host, inst, rcp):
            ids = mapper.ids(v, nm)
            if not ids:
                prov["P_net_miss"] += 1
                continue
            for i in ids:
                hit_p[i] = True
                if stt == "proved":
                    proved[i] += 1
                    partner[i].add(pkey)
                elif stt == "differ":
                    differ[i].add(pkey)
    for i in np.where(hit_p)[0]:
        p_, d_ = proved.get(int(i), 0), len(differ.get(int(i), set()))
        F[i, [8, 9, 10]] = [np.log1p(p_), np.log1p(d_), p_ / max(p_ + d_, 1)]


    # ---------------- R 层：区域边界 SAT 对应（下发到节点） ----------------
    rp_p = tabs / "region_pairs.csv"
    n_rp = 0
    if rp_p.exists():
        rp = pd.read_csv(rp_p, encoding="utf-8-sig").fillna("")
        n_rp = len(rp)
        # (host,inst,recipe) → region → [jaccard_max, matched_max, edges_max]
        reg_of: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))
        for (host, inst, pair), g in rp.groupby(["host", "inst", "pair"]):
            ra, rb = split_pair(pair)
            jac = pd.to_numeric(g["jaccard"], errors="coerce").fillna(0.0)
            edges = pd.to_numeric(g.get("n_pair_edges", 0), errors="coerce").fillna(0.0)
            matched = (g["match_type"].astype(str) != "unmatched").astype(float)
            for rcp in (ra, rb):
                for reg, j, e, m in zip(g["region"].astype(str), jac, edges, matched):
                    cur = reg_of[(str(host), str(inst), rcp)][reg]
                    cur[0] = max(cur[0], float(j))
                    cur[1] = max(cur[1], float(m))
                    cur[2] = max(cur[2], float(e))
        for (host, inst, rcp), regs in reg_of.items():
            order = sorted(regs, key=len, reverse=True)   # 最长前缀优先 ✓（TrojanAHJ 先于 TrojanA ✓）
            for v in views_for(views, host, inst, rcp):
                for nm, ids in basem[v].items():
                    if not nm.startswith("Trojan"):
                        continue
                    for reg in order:
                        if nm.startswith(reg):
                            j, m, e = regs[reg]
                            for i in ids:
                                F[i, 11] = max(F[i, 11], j)
                                F[i, 12] = max(F[i, 12], m)
                                F[i, 13] = max(F[i, 13], np.log1p(e))
                                hit_r[i] = True
                            break


    if a.drop_identity:
        F[:, 0:4] = 0.0
        hit_s = hit_s & (F[:, 4:8].sum(1) > 0)

    mk[:, 0] = hit_s
    mk[:, 1] = hit_p
    mk[:, 2] = hit_r

    # ⚠️ 视图内置换对照（2026-10-23 ✓）：**保持每个视图的 covered 数量与数值多重集不变**，
    #   只把"证据贴到哪个节点"随机打乱 → 排掉"存在性/来源"捷径 ✓（`--no-cov-flag` 排不掉 ✗）。
    if a.permute_within_view:
        rng = np.random.default_rng(int(a.perm_seed))
        by_view: dict[str, list[int]] = defaultdict(list)
        for i, v in enumerate(fid):
            by_view[v].append(i)
        n_perm = 0
        for v, idx in by_view.items():
            if len(idx) < 2:
                continue
            idx_arr = np.asarray(idx)
            p = rng.permutation(len(idx_arr))
            F[idx_arr] = F[idx_arr][p]
            mk[idx_arr] = mk[idx_arr][p]
            n_perm += 1
        print(f"[PERM] 视图内置换 ✓ {n_perm} 个视图（seed={a.perm_seed} ✓，"
              f"每视图 covered 数与数值分布不变 ✓）")
        covered = (mk.max(1) > 0).astype(np.float32)
    else:
        covered = (mk.max(1) > 0).astype(np.float32)

    # ⚠️ 显存约束（8 GB 卡，基线峰值已 ~7.9 GB ✗）：17 列会把训练推到 shared memory 分页 ✗
    #   → 训练默认只吃 **9 维核心子集** ✓（保留 SAT 语义 ✓，丢掉的 [0/1/3/9/11/12] 进 full 版 ✓）
    #   core: [2]控制端 [4]decided [5]influence [6]observable [7]深度 [8]已证数 [10]已证比 [13]区域边 + covered
    core_idx = [2, 4, 5, 6, 7, 8, 10, 13]
    Fc = np.concatenate([F[:, core_idx], covered[:, None]], 1).astype(np.float32)

    sfx = a.tag_suffix or ""
    np.save(pt_dir / f"satrel_node_feats_sat{sfx}.npy", Fc)                 # 训练用 ✓ 9 维
    np.save(pt_dir / f"satrel_node_feats_sat_full{sfx}.npy", F)             # 全量 14 维 ✓
    np.save(pt_dir / f"satrel_node_mask_sat{sfx}.npy", mk)

    # ---------------- 覆盖率报告 ----------------
    cov_any = mk.max(1) > 0
    trojan_name = np.array([("trojan" in (nm or "").lower()) for nm in names])
    denom = int(trojan_name.sum())
    meta = {
        "n_nodes": int(n),
        "n_views": len(views),
        "coverage_any": round(float(cov_any.mean()), 6),
        "coverage_any_nodes": int(cov_any.sum()),
        "coverage_by_layer": {k: int(mk[:, k].sum()) for k in range(3)},
        "coverage_target_denominator": {
            "trojan_named_nodes": denom,
            "S_covered_of_trojan_named": int((hit_s & trojan_name).sum()),
            "P_covered_of_trojan_named": int((hit_p & trojan_name).sum()),
            "R_covered_of_trojan_named": int((hit_r & trojan_name).sum()),
        },
        "rows_used": {"functional_relations": int(n_fr_rows),
                      "functional_relations_view_apply": int(n_fr_views),
                      "node_pairs_sweep": int(n_sw),
                      "node_pairs_sat_node": int(n_batch),
                      "node_pairs_B05": int(n_b05),
                      "region_pairs": int(n_rp)},
        "extra_pairs": str(a.extra_pairs),
        "incident": bool(a.incident),
        "permute_within_view": bool(a.permute_within_view),
        "perm_seed": int(a.perm_seed),
        "miss": dict(prov),
        "netmap": mapper.summary(),
        "drop_identity": bool(a.drop_identity),
        "train_feature_core": {"dims": 9, "full_idx": core_idx,
                               "last_dim": "covered flag（1=该节点有任一 SAT 证据 ✓）",
                               "note": "8 GB 显存限制 → 训练只用核心子集 ✓" if not a.drop_identity
                                       else "drop-identity 后 [0..3] 已置零 ✓"},
        "note": ("所有非零值均来自 SAT 表 ✓；mask=0 = 未知（不是无关系 ✗）；"
                 "候选由注入记录挖出 → 属 privileged information ⚠️；"
                 "同 (host,inst,recipe) 的多个 keep 变体共享同一 SAT 结论 ⚠️；"
                 "[11..13] 是区域级证据下发到节点 ⚠️（region-resolved ✓，非 per-node proved ✗）"),
    }
    if y is not None:
        yy = np.asarray(y)
        pos = yy == 1
        meta["pos_neg_coverage"] = {
            "pos": {k: round(float(mk[pos, k].mean()), 4) for k in range(3)},
            "neg": {k: round(float(mk[~pos, k].mean()), 6) for k in range(3)},
        }
        meta["pos_neg_coverage"]["pos"]["any"] = round(float(cov_any[pos].mean()), 4)
        meta["pos_neg_coverage"]["neg"]["any"] = round(float(cov_any[~pos].mean()), 6)
        meta["pos_nodes"] = int(pos.sum())
    (pt_dir / f"satrel_node_meta_sat{sfx}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # 明细 CSV（P4 出图用 ✓；只写被覆盖节点 ✓；`--tag-suffix` 非空时不覆盖主表 ✓）
    sel = np.where(cov_any)[0]
    if len(sel) and not sfx:
        pd.DataFrame({
            "node": sel,
            "view": [fid[i] for i in sel],
            "name": [names[i] for i in sel],
            "base": [base_name(names[i]) for i in sel],
            "label": [int(y[i]) if y is not None else -1 for i in sel],
            **{f"f{k}": F[sel, k] for k in range(14)},
            "m0": mk[sel, 0], "m1": mk[sel, 1], "m2": mk[sel, 2],
        }).to_csv(tabs / "satrel_node_sat_covered.csv", index=False, encoding="utf-8-sig")

    print(f"[node-satrel] {json.dumps(meta, ensure_ascii=False)}")
    print(f"[out] {pt_dir / f'satrel_node_feats_sat{sfx}.npy'} core={Fc.shape} ✓（训练用）"
          f"｜full={F.shape}（{pt_dir / f'satrel_node_feats_sat_full{sfx}.npy'}）")
    print(f"[out] {tabs / 'satrel_node_sat_covered.csv'}（{len(sel)} 行 ✓）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

