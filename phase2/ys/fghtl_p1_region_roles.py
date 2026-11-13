"""fghtl_p1_region_roles.py —— 补齐任务书 P1 的第 2/3 条 ✓（**区域拆分/合并** + **区域级角色**）。

一、区域对应（含**拆分/合并** ✓，任务书第 2 条）
  1. 用 `sat_sweep_pairs.simulate_seq` 的 **8 拍顺序仿真签名** ✓（输入按端口名共享 ✓、FF 初值 0 ✓）；
  2. 区域 = `Trojan*` 前缀 ✓（`TrojanAHJ/AP0/…` ✓）；
     **区域边界** = 该区域网的**扇入/扇出**到区域外的网 ✓；
     区域签名集合 = 边界网签名集合 ✓；
  3. 跨实现按 **Jaccard** 匹配 ✓（贪心 1:1 起步 → 统计被多方命中的情况 ✓）：
     `match_type ∈ {1:1, 1:N（A 区拆成多个 B 区）, N:1（多个 A 区并成一个 B 区）, unmatched}` ✓。

二、区域级角色（任务书第 3 条 ✓）
  · 节点对取 **并集** ✓：`node_pairs.csv`（name-anchored ✓）+ `node_pairs_sweep.csv`（sweeping ✓）；
  · 逐网角色 ✓（`Trojan*` 插入记录 + 锥 + SAT ✓）；聚合到区域 ✓：
    `region_role ∈ {trusted_trojan, mixed, all_benign, unknown}` ✓ + 四类计数 ✓。

输出 ✓：
  `tables/region_pairs.csv`（**覆盖**：加 `match_type` / `jaccard` / `partner_region` ✓）
  `tables/region_role_status.csv` ✓
  `tables/role_status_union.csv` ✓（并集逐网 ✓，带 `source ∈ {name, sweep}` ✓）

⚠️ 口径 ✓：`unmatched` / `unknown` **一律当"不可用"** ✗，不进 `L_eq` ✗。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

import sat_sweep_pairs as SW          # 复用顺序仿真 ✓ + 结构 JSON ✓（同目录 ✓）

ROOT = SW.ROOT
BASE = SW.BASE
LOGS = SW.LOGS
PREF = re.compile(r"^(?:\\\\)?(Trojan[A-Za-z0-9]+)")


def regions_of(names: dict[int, str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for b, n in names.items():
        m = PREF.match(str(n))
        if m:
            out.setdefault(m.group(1), []).append(b)
    return out


def boundary_sigs(mod: dict, names: dict, sig: dict[int, int],
                  region: str, bits: list[int]) -> list[int]:
    """区域边界网的**签名集合** ✓（扇入/扇出到区域外 ✓）。"""
    inside = set(bits)
    con, drv = {}, {}
    for cell in mod["cells"].values():
        for port, bs in cell.get("connections", {}).items():
            for b in bs:
                if not isinstance(b, int):
                    continue
                if port in ("Y", "Q", "QN"):
                    drv.setdefault(b, cell)
                else:
                    con.setdefault(b, []).append(cell)
    bnd: set[int] = set()
    for b in bits:
        for cell in con.get(b, []):
            for port, bs in cell["connections"].items():
                if port in ("Y", "Q", "QN"):
                    for ob in bs:
                        if isinstance(ob, int) and ob not in inside:
                            bnd.add(ob)
        cell = drv.get(b)
        if cell is not None:
            for port, bs in cell["connections"].items():
                if port in ("Y", "Q", "QN"):
                    continue
                for ib in bs:
                    if isinstance(ib, int) and ib not in inside:
                        bnd.add(ib)
    return [sig[b] for b in bnd if b in sig]


def jaccard(a: list[int], b: list[int]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def region_table(host: str, inst: str, pair: str, va: Path, vb: Path, k: int,
                 cycles: int, seed: int) -> tuple[list[dict], dict, dict]:
    topA, modA, nA = SW.load_json(SW.struct_json(va))
    topB, modB, nB = SW.load_json(SW.struct_json(vb))
    sigA, _ = SW.simulate_seq(modA, nA, k, seed, cycles)
    sigB, _ = SW.simulate_seq(modB, nB, k, seed, cycles)
    regA, regB = regions_of(nA), regions_of(nB)
    bndA = {r: boundary_sigs(modA, nA, sigA, r, bs) for r, bs in regA.items()}
    bndB = {r: boundary_sigs(modB, nB, sigB, r, bs) for r, bs in regB.items()}
    # ---- 贪心 1:1（按 jaccard 降序 ✓）
    scored = []
    for ra in regA:
        for rb in regB:
            j = jaccard(bndA[ra], bndB[rb])
            if j > 0:
                scored.append((j, ra, rb))
    scored.sort(reverse=True)
    used_a, used_b, match = set(), set(), {}
    for j, ra, rb in scored:
        if ra in used_a or rb in used_b:
            continue
        used_a.add(ra)
        used_b.add(rb)
        match[ra] = (rb, j)
    # ---- 拆分/合并判定 ✓（用**边界签名命中**而非 1:1 名额 ✓）
    rows = []
    for ra, j_a in sorted(((r, bndA[r]) for r in regA)):
        hit = [(rb, jaccard(j_a, bndB[rb])) for rb in regB]
        hit = [(rb, j) for rb, j in hit if j >= 0.10]
        hit.sort(key=lambda t: -t[1])
        # 该 A 区命中的 B 区数 ⇒ 1:N（拆分 ✓）；同时统计有多少 A 区命中同一 B 区 ⇒ N:1（合并 ✓）
        rb0, j0 = match.get(ra, (hit[0][0] if hit else "", hit[0][1] if hit else 0.0))
        back = [x for x in regA if any(jaccard(bndA[x], bndB[rb]) >= 0.10
                                       for rb, _ in hit)]
        if not hit:
            mt = "unmatched"
        else:
            best = hit[0][1]
            second = hit[1][1] if len(hit) > 1 else 0.0
            # 主命中必须"压倒性" ✓ 才算 1:1（否则视为拆到多个区 ✓）
            if best < 0.05:
                mt = "unmatched"
            elif len(hit) > 1 and second > 0.5 * best:
                mt = "1:N"
            elif len(back) > 1:
                mt = "N:1"
            else:
                mt = "1:1"
        rows.append(dict(host=host, inst=inst, pair=pair, region=ra,
                         partner_region=rb0, jaccard=round(j0, 4),
                         n_region_nets=len(regA[ra]), n_boundary_sigs=len(set(j_a)),
                         match_type=mt))
    return rows, (topA, modA, nA, sigA), (topB, modB, nB, sigB)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts", default="rs232t1000,s38584t100")
    ap.add_argument("--insts", default="injalpha,injepsilon")
    ap.add_argument("--pairs", default="ys_id:ys_abc,ys_id:ys_opt,ys_abc:ys_opt")
    ap.add_argument("--fold", default="hosts_bt31")
    ap.add_argument("--k", type=int, default=32)
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    tdir = BASE / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    np_name = tdir / "node_pairs.csv"
    np_sw = tdir / "node_pairs_sweep.csv"

    parts = []
    if np_name.exists():
        d = pd.read_csv(np_name, encoding="utf-8-sig").fillna("")
        d = d[d["net"].astype(str).str.len() > 0][["host", "inst", "pair", "net", "status"]]
        d["source"] = "name"
        parts.append(d)
    if np_sw.exists():
        s = pd.read_csv(np_sw, encoding="utf-8-sig").fillna("")
        s = s[(s["status"] == "proved") & (s["net_a"].astype(str).str.len() > 0)]
        left = s[["host", "inst", "pair", "net_a", "status"]].rename(columns={"net_a": "net"})
        right = s[["host", "inst", "pair", "net_b", "status"]].rename(columns={"net_b": "net"})
        u = pd.concat([left, right], ignore_index=True)
        u["source"] = "sweep"
        parts.append(u)
    if not parts:
        print("[warn] 没有节点对 ✗")
        return 1
    uni = pd.concat(parts, ignore_index=True).drop_duplicates(
        subset=["host", "inst", "pair", "net"], keep="last")
    uni["is_trojan"] = uni["net"].astype(str).str.contains("Trojan", case=False)
    proved = uni["status"] == "proved"
    uni["role"] = "unknown"
    uni.loc[proved & uni["is_trojan"], "role"] = "trusted_trojan"
    uni.loc[proved & ~uni["is_trojan"], "role"] = "trusted_benign"
    uni.loc[~proved & uni["is_trojan"], "role"] = "mixed"
    uni.to_csv(tdir / "role_status_union.csv", index=False, encoding="utf-8-sig")
    print(f"[out] role_status_union.csv（{len(uni)} 行 ✓）")
    print(uni["role"].value_counts().to_string())

    # ---- 证明对的**边表** ✓（name 同名 + sweep ✓，只取 proved ✓）→ 用于区域匹配 ✓
    edges = []
    if np_name.exists():
        d = pd.read_csv(np_name, encoding="utf-8-sig").fillna("")
        d = d[d["status"] == "proved"]
        edges.append(d[["host", "inst", "pair", "net", "status"]]
                     .rename(columns={"net": "net_a"}).assign(net_b=lambda x: x["net_a"]))
    if np_sw.exists():
        s = pd.read_csv(np_sw, encoding="utf-8-sig").fillna("")
        s = s[(s["status"] == "proved") & (s["net_a"].astype(str).str.len() > 0)]
        edges.append(s[["host", "inst", "pair", "net_a", "net_b", "status"]])
    pairs_uni = (pd.concat(edges, ignore_index=True)
                 if edges else pd.DataFrame(columns=["host", "inst", "pair", "net_a", "net_b"]))


    rows = []
    for host in [x for x in a.hosts.split(",") if x]:
        for inst in [x for x in a.insts.split(",") if x]:
            tdir_t = ROOT / "generate_trans" / "folds" / a.fold / "trans"
            for pr in [x for x in a.pairs.split(",") if ":" in x]:
                ra, rb = [t.strip() for t in pr.split(":")]
                va = sorted(tdir_t.glob(f"{host}__{inst}_d1_s42__*{ra}.v"))
                vb = sorted(tdir_t.glob(f"{host}__{inst}_d1_s42__*{rb}.v"))
                if not (va and vb):
                    continue
                if not ((pairs_uni.host == host) & (pairs_uni.inst == inst)).any():
                    print(f"  [skip] {host}/{inst} 无已证节点对 ✗（先跑 sweep ✓）")
                    continue
                try:
                    rr, _, _ = region_table(host, inst, pr, va[0], vb[0],
                                            a.k, a.cycles, a.seed)
                except Exception as e:      # noqa: BLE001
                    print(f"[warn] {host}/{inst}/{pr} 区域计算失败 ✗ {e}")
                    continue
                for r in rr:
                    sub = uni[(uni.host == host) & (uni.inst == inst) & (uni.pair == pr)
                              & (uni.net.astype(str).str.startswith(r["region"]))]
                    n_tj = int((sub["role"] == "trusted_trojan").sum())
                    n_tb = int((sub["role"] == "trusted_benign").sum())
                    n_mx = int((sub["role"] == "mixed").sum())
                    n_uk = int((sub["role"] == "unknown").sum())
                    r.update(n_trusted_trojan=n_tj, n_trusted_benign=n_tb,
                             n_mixed=n_mx, n_unknown=n_uk,
                             region_role=("trusted_trojan" if n_tj else
                                          "mixed" if (n_mx or n_uk) else
                                          "all_benign" if n_tb else "unknown"))
                    rows.append(r)
                print(f"  {host}/{inst}/{pr}: 区域 {len(rr)} ✓ "
                      f"{dict(pd.Series([x['match_type'] for x in rr]).value_counts())}")
    if not rows:
        print("[warn] 没有区域结果 ✗")
        return 1
    reg = pd.DataFrame(rows).sort_values(["host", "inst", "pair", "region"])
    # ---- match_type 用 **SAT 证明边** 重算 ✓（小区域的边界签名不判别 ✗）
    def _pref(s):
        m = PREF.match(str(s))
        return m.group(1) if m else ""

    if not pairs_uni.empty:
        e = pairs_uni.copy()
        e["ra"] = e["net_a"].map(_pref)
        e["rb"] = e["net_b"].map(_pref)
        e = e[(e["ra"] != "") & (e["rb"] != "")]
        agg = e.groupby(["host", "inst", "pair", "ra", "rb"]).size().rename("n").reset_index()
        for i, row in reg.iterrows():
            sub = agg[(agg.host == row.host) & (agg.inst == row.inst)
                      & (agg.pair == row.pair) & (agg.ra == row.region)]
            if sub.empty:
                reg.at[i, "match_type"] = "unmatched"
                reg.at[i, "n_pair_edges"] = 0
                continue
            reg.at[i, "n_pair_edges"] = int(sub["n"].sum())
            best = sub.sort_values("n", ascending=False).iloc[0]
            reg.at[i, "partner_region"] = best["rb"]
            back = agg[(agg.host == row.host) & (agg.inst == row.inst)
                       & (agg.pair == row.pair) & (agg.rb == best["rb"])]
            n_out, n_in = int(len(sub)), int(len(back))
            reg.at[i, "match_type"] = ("1:1" if (n_out == 1 and n_in == 1)
                                       else "1:N" if n_in == 1 else "N:1")
    reg.to_csv(tdir / "region_pairs.csv", index=False, encoding="utf-8-sig")
    reg[["host", "inst", "pair", "region", "partner_region", "jaccard", "match_type",
         "n_trusted_trojan", "n_trusted_benign", "n_mixed", "n_unknown",
         "region_role"]].to_csv(tdir / "region_role_status.csv", index=False,
                                encoding="utf-8-sig")
    print(f"\n[out] region_pairs.csv（{len(reg)} 行 ✓，含 match_type ✓）")
    print(reg["match_type"].value_counts().to_string())
    print(reg["region_role"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


