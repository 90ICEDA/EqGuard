"""make_p0_consistency.py —— 补两处**遗漏** ✓（2026-10-23 ✓）

1. **P0 第 6 条：跨实现"功能关系一致性"** ✗→✓
   对每个 (host, inst)：看 `ys_id / ys_abc / ys_opt` 三个实现里
   ① 被劫持 PO 是否**相同** ✓ ② `decided` / `influence` 是否**都为 1** ✓
   → `relation_consistency.csv`（`n_impl` / `n_same_target` / `consistent` / `targets` ✓）。

2. **P1 第 4 条的"率"** ✗→✓
   `signal_match_rate`（SAT proved / 参与比较的信号对 ✓）、
   `region_match_rate`（`match_type != unmatched` 占区域数 ✓）、
   `trojan_label_coverage`（`trusted_trojan` / 木马网总数 ✓）
   → `p1_rates.csv`。

3. **P0 第 7 条"超时率"** ✗→✓：`sat_summary.csv` 补 `timeout_rate` 列 ✓。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T = ROOT / "10.15" / "06_统一评测协议" / "N4_三向泛化" / "tables"


def main() -> int:
    # ---------- 1) 跨实现关系一致性 ✓
    fr = pd.read_csv(T / "functional_relations.csv", encoding="utf-8-sig")
    rows = []
    for (h, i), g in fr.groupby(["host", "inst"]):
        tgt = g["target"].dropna().astype(str)
        tg = [t for t in tgt if t and t != "nan"]
        same = len(set(tg)) <= 1
        decided = float(g["decided"].fillna(0).mean())
        infl = float(g["influence"].fillna(0).mean())
        rows.append(dict(host=h, inst=i, n_impl=len(g),
                         n_same_target=int(len(set(tg)) <= 1),
                         targets=";".join(sorted(set(tg))),
                         decided_rate=round(decided, 3),
                         influence_rate=round(infl, 3),
                         consistent=int(same and decided >= 0.99 and infl >= 0.99)))
    rc = pd.DataFrame(rows)
    rc.to_csv(T / "relation_consistency.csv", index=False, encoding="utf-8-sig")
    print("[out] relation_consistency.csv")
    print(rc.to_string(index=False))

    # ---------- 2) P1 三种"率" ✓
    np_name = pd.read_csv(T / "node_pairs.csv", encoding="utf-8-sig").fillna("")
    np_name = np_name[np_name["net"].astype(str).str.len() > 0]
    sw = pd.read_csv(T / "node_pairs_sweep.csv", encoding="utf-8-sig").fillna("")
    sw = sw[sw["net_a"].astype(str).str.len() > 0]
    rp = pd.read_csv(T / "region_pairs.csv", encoding="utf-8-sig")
    uni = pd.read_csv(T / "role_status_union.csv", encoding="utf-8-sig")
    rows = []
    for (h, i) in sorted(set(zip(np_name["host"], np_name["inst"]))):
        n1 = np_name[(np_name.host == h) & (np_name.inst == i)]
        s1 = sw[(sw.host == h) & (sw.inst == i)]
        r1 = rp[(rp.host == h) & (rp.inst == i)]
        u1 = uni[(uni.host == h) & (uni.inst == i)]
        tot = len(n1) + len(s1)
        prov = int((n1.status == "proved").sum()) + int((s1.status == "proved").sum())
        tro = u1[u1["net"].astype(str).str.contains("Trojan", case=False)]
        rows.append(dict(
            host=h, inst=i,
            n_pairs=tot, n_proved=prov,
            signal_match_rate=round(prov / max(tot, 1), 4),
            n_regions=len(r1),
            region_match_rate=round(float((r1.match_type != "unmatched").mean()), 4)
            if len(r1) else 0.0,
            n_trojan_nets=len(tro),
            n_trusted_trojan=int((tro.role == "trusted_trojan").sum())
            if "role" in tro else 0,
            trojan_label_coverage=round(
                float((tro.role == "trusted_trojan").mean()) if len(tro) else 0.0, 4)))
    pr = pd.DataFrame(rows)
    pr.to_csv(T / "p1_rates.csv", index=False, encoding="utf-8-sig")
    print("\n[out] p1_rates.csv")
    print(pr.to_string(index=False))

    # ---------- 3) 超时率 ✓
    ss = pd.read_csv(T / "sat_summary.csv", encoding="utf-8-sig")
    ss["timeout_rate"] = (1 - ss["n_proved"] / ss["n_impl"].clip(lower=1)).round(3)
    ss.to_csv(T / "sat_summary.csv", index=False, encoding="utf-8-sig")
    print("\n[out] sat_summary.csv（+timeout_rate ✓）")
    print(ss[["host", "inst", "n_impl", "n_proved", "coverage", "timeout_rate"]]
          .to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
