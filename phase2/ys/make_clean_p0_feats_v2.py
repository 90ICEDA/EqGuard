"""make_clean_p0_feats_v2.py -- fixed, per-node P0 features (no status=proved filter).

Key fixes vs v1
  * includes proved + partial rows (INV/XOR are not silently dropped);
  * recomputes a type-agnostic `decided` and `influence_general`;
  * observable is continuous reach (n_po / n_dff), not a binary missing value;
  * no 0.5 imputation; `covered` is only the last mask-like flag;
  * per-node aggregation (roles, relation counts, fractions), not one broadcast 1;
  * removes exact duplicates (`decided == influence == is_cut`).

Full 19-dim order:
  0 is_target, 1 is_cut, 2 is_cell, 3 is_target_only,
  4 n_target_log, 5 n_cut_log, 6 n_cell_log, 7 n_rel_log,
  8 frac_decided, 9 frac_influence, 10 frac_proved,
  11 reach_po_log, 12 reach_dff_log, 13 obs_tested,
  14 p1_proved_log, 15 p1_differ_log, 16 p1_ratio,
  17 frac_unknown, 18 covered

Core 12-dim order (training):
  [2] is_cell, [1] is_cut, [3] is_target_only, [7] n_rel_log,
  [8] frac_decided, [9] frac_influence, [10] frac_proved,
  [11] reach_po_log, [12] reach_dff_log,
  [14] p1_proved_log, [16] p1_ratio, [18] covered
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netmap as NM  # noqa: E402
import satrel_node_feats_sat as NF  # noqa: E402

ROOT = NF.ROOT
DEFAULT_PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
DEFAULT_WORK = ROOT / "generate_trans/folds/hosts_bt31"
DEFAULT_P0 = ROOT / "_p0pilot/functional_relations_agnostic.csv"


def clean_host(top: str) -> str:
    s = str(top or "").strip()
    if s.endswith(".v"):
        s = s[:-2]
    return s.split("__", 1)[0]


def _q(r: pd.Series, k: str) -> str:
    return str(r.get(k, "") or "").strip().lower()


def _influence_general(r: pd.Series, kind: str) -> int:
    """Mux keeps selector test; gates use output(all1) != output(all0)."""
    if kind == "mux":
        try:
            return int(float(r.get("influence", 0) or 0))
        except (TypeError, ValueError):
            return 0
    q1, q2, q3, q4 = (_q(r, "sat_q1"), _q(r, "sat_q2"),
                      _q(r, "sat_q3"), _q(r, "sat_q4"))
    # Forced output is 1 at all-1 and 0 at all-0, or vice versa.
    return int((q1 == "proved" and q4 == "proved") or
               (q2 == "proved" and q3 == "proved"))


def _decided(r: pd.Series, kind: str) -> int:
    if kind == "mux":
        try:
            return int(float(r.get("decided", 0) or 0))
        except (TypeError, ValueError):
            return 0
    q1, q2, q3, q4 = (_q(r, "sat_q1"), _q(r, "sat_q2"),
                      _q(r, "sat_q3"), _q(r, "sat_q4"))
    return int(((q1 == "proved") ^ (q2 == "proved")) and
               ((q3 == "proved") ^ (q4 == "proved")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p0-csv", type=Path, default=DEFAULT_P0)
    ap.add_argument("--pt-dir", type=Path, default=DEFAULT_PT)
    ap.add_argument("--work", type=Path, default=DEFAULT_WORK)
    ap.add_argument("--tables", type=Path, default=NF.T)
    ap.add_argument("--tag-suffix", default="_p0clean2")
    ap.add_argument("--no-p1", action="store_true")
    ap.add_argument("--p1-max-rows", type=int, default=0)
    ap.add_argument("--no-netmap", action="store_true")
    a = ap.parse_args()

    pt_dir, tabs = a.pt_dir, a.tables
    names, fid = NF.load_names(pt_dir, a.work)
    n = len(fid)
    views = sorted(set(fid))
    exact, basem = NF.build_maps(names, fid, views)
    if a.no_netmap:
        class _LegacyMap:
            def ids(self, view, net):
                return NF.resolve(exact[view], basem[view], net)
            def summary(self):
                return {"mode": "legacy-direct-only", "hit_rate": None}
        mapper = _LegacyMap()
    else:
        mapper = NM.NetMapper(
            exact, basem, a.work / "trans",
            struct_dirs=NM.default_struct_dirs(NF.BASE),
            use_json=True, max_alias=8, include_sinks=False,
        )
    print(f"[netmap] views={len(views)} nodes={n} mode={mapper.summary().get('mode')}")

    # per-node aggregates
    n_target = np.zeros(n, np.int32)
    n_cut = np.zeros(n, np.int32)
    n_cell = np.zeros(n, np.int32)
    n_rel = np.zeros(n, np.int32)
    n_proved = np.zeros(n, np.int32)
    n_decided = np.zeros(n, np.int32)
    n_influence = np.zeros(n, np.int32)
    n_unknown = np.zeros(n, np.int32)
    reach_po = np.zeros(n, np.int32)
    reach_dff = np.zeros(n, np.int32)
    obs_tested = np.zeros(n, np.int32)
    hit_s = np.zeros(n, bool)
    hit_p = np.zeros(n, bool)
    p1_proved = np.zeros(n, np.int32)
    p1_differ = np.zeros(n, np.int32)
    prov: dict[str, int] = defaultdict(int)
    status_counts: Counter = Counter()

    # ---------------- S layer: all P0 rows (proved + partial) ----------------
    if not a.p0_csv.exists():
        raise SystemExit(f"[ERROR] missing P0 CSV: {a.p0_csv}")
    p0 = pd.read_csv(a.p0_csv, encoding="utf-8-sig").fillna("")
    if len(p0) == 0:
        raise SystemExit("[ERROR] P0 CSV has zero rows")
    n_s_rows = n_s_apps = 0
    for _, r in p0.iterrows():
        top = str(r.get("top", "")).strip()
        host = clean_host(top)
        inst = str(r.get("inst", "")).strip()
        recipe = str(r.get("recipe", "")).strip()
        if not (host and inst and recipe):
            prov["S_bad_key"] += 1
            continue
        vs = NF.views_for(views, host, inst, recipe)
        if not vs:
            prov["S_no_view"] += 1
            continue
        n_s_rows += 1
        kind = str(r.get("kind", "")).strip()
        status = str(r.get("status", "")).strip()
        status_counts[status] += 1
        proved = int(status == "proved")
        decided = _decided(r, kind)
        influence = _influence_general(r, kind)
        qstat = [_q(r, f"sat_q{i}") for i in (1, 2, 3, 4)]
        unknown = int(any(x == "unknown" for x in qstat))
        target = str(r.get("target", "")).strip()
        cell = str(r.get("cell", "")).strip()
        cuts = [x.strip() for x in str(r.get("cut_nets", "")).split(";") if x.strip()]
        try:
            npo = int(float(r.get("n_po_reached", 0) or 0))
            ndff = int(float(r.get("n_dff_reached", 0) or 0))
        except (TypeError, ValueError):
            npo = ndff = 0
        for v in vs:
            n_s_apps += 1
            t_ids = mapper.ids(v, target) if target else []
            cut_ids = set()
            for cu in cuts:
                cut_ids.update(mapper.ids(v, cu))
            cell_ids = set(mapper.ids(v, cell)) if cell else set()
            nodes = set(t_ids) | cut_ids | cell_ids
            if not nodes:
                prov["S_no_node"] += 1
                continue
            for i in nodes:
                n_rel[i] += 1
                n_proved[i] += proved
                n_decided[i] += decided
                n_influence[i] += influence
                n_unknown[i] += unknown
                hit_s[i] = True
            for i in t_ids:
                n_target[i] += 1
                obs_tested[i] = 1
                reach_po[i] += npo
                reach_dff[i] += ndff
            for i in cut_ids:
                n_cut[i] += 1
            for i in cell_ids:
                n_cell[i] += 1
            if not t_ids:
                prov["S_target_miss"] += 1

    # ---------------- P1 layer: all-anchor proved/differ pairs ----------------
    n_p_rows = 0
    if not a.no_p1:
        p1p = tabs / "node_pairs_sat_node.csv"
        if not p1p.exists():
            prov["P_missing"] += 1
        else:
            p1 = pd.read_csv(p1p, encoding="utf-8-sig").fillna("")
            if a.p1_max_rows and len(p1) > a.p1_max_rows:
                p1 = p1.iloc[:a.p1_max_rows]
            n_p_rows = len(p1)
            for _, r in p1.iterrows():
                host = str(r.get("host", "")).strip()
                ia = str(r.get("inst_a", "")).strip()
                ib = str(r.get("inst_b", "")).strip()
                ra = str(r.get("recipe_a", "")).strip()
                rb = str(r.get("recipe_b", "")).strip()
                ra = ra if ra.startswith("ys_") else f"ys_{ra}"
                rb = rb if rb.startswith("ys_") else f"ys_{rb}"
                stt = str(r.get("status", "")).strip()
                if stt not in ("proved", "differ"):
                    continue
                na = str(r.get("net_a", "")).strip()
                nb = str(r.get("net_b", "")).strip()
                for inst, rcp, net in ((ia, ra, na), (ib, rb, nb)):
                    if not (inst and rcp and net):
                        continue
                    for v in NF.views_for(views, host, inst, rcp):
                        for i in mapper.ids(v, net):
                            hit_p[i] = True
                            if stt == "proved":
                                p1_proved[i] += 1
                            else:
                                p1_differ[i] += 1

    # ---------------- feature assembly ----------------
    is_target = (n_target > 0).astype(np.float32)
    is_cut = (n_cut > 0).astype(np.float32)
    is_cell = (n_cell > 0).astype(np.float32)
    is_target_only = ((n_target > 0) & (n_cell == 0)).astype(np.float32)
    denom = np.maximum(n_rel.astype(np.float32), 1.0)
    frac_decided = (n_decided.astype(np.float32) / denom)
    frac_influence = (n_influence.astype(np.float32) / denom)
    frac_proved = (n_proved.astype(np.float32) / denom)
    frac_unknown = (n_unknown.astype(np.float32) / denom)
    p1_denom = np.maximum((p1_proved + p1_differ).astype(np.float32), 1.0)
    p1_ratio = (p1_proved.astype(np.float32) / p1_denom)
    covered = ((n_rel > 0) | hit_p).astype(np.float32)

    view_idx: dict[str, list[int]] = defaultdict(list)
    for i, v in enumerate(fid):
        view_idx[v].append(i)

    def log_norm(a: np.ndarray) -> np.ndarray:
        out = np.log1p(a.astype(np.float32))
        for idxs in view_idx.values():
            idx = np.asarray(idxs, dtype=np.int64)
            mx = float(out[idx].max()) if len(idx) else 0.0
            if mx > 0:
                out[idx] /= mx
        return out

    n_target_log = log_norm(n_target)
    n_cut_log = log_norm(n_cut)
    n_cell_log = log_norm(n_cell)
    n_rel_log = log_norm(n_rel)
    reach_po_log = log_norm(reach_po)
    reach_dff_log = log_norm(reach_dff)
    p1_proved_log = log_norm(p1_proved)
    p1_differ_log = log_norm(p1_differ)

    F = np.column_stack([
        is_target, is_cut, is_cell, is_target_only,
        n_target_log, n_cut_log, n_cell_log, n_rel_log,
        frac_decided, frac_influence, frac_proved,
        reach_po_log, reach_dff_log, obs_tested.astype(np.float32),
        p1_proved_log, p1_differ_log, p1_ratio,
        frac_unknown, covered,
    ]).astype(np.float32)
    full_names = [
        "is_target", "is_cut", "is_cell", "is_target_only",
        "n_target_log", "n_cut_log", "n_cell_log", "n_rel_log",
        "frac_decided", "frac_influence", "frac_proved",
        "reach_po_log", "reach_dff_log", "obs_tested",
        "p1_proved_log", "p1_differ_log", "p1_ratio",
        "frac_unknown", "covered",
    ]
    core_idx = [2, 1, 3, 7, 8, 9, 10, 11, 12, 14, 16, 18]
    core_names = [full_names[i] for i in core_idx]
    Fc = F[:, core_idx].copy()

    mk = np.stack([hit_s.astype(np.float32),
                   hit_p.astype(np.float32),
                   np.zeros(n, np.float32)], axis=1)

    sfx = a.tag_suffix or ""
    np.save(pt_dir / f"satrel_node_feats_sat{sfx}.npy", Fc)
    np.save(pt_dir / f"satrel_node_feats_sat_full{sfx}.npy", F)
    np.save(pt_dir / f"satrel_node_mask_sat{sfx}.npy", mk)

    trojan_name = np.array([("trojan" in (nm or "").lower()) for nm in names])
    meta = {
        "source_p0": str(a.p0_csv),
        "p0_status_filter": "none (all proved+partial rows)",
        "n_nodes": int(n),
        "n_views": len(views),
        "p0_rows_used": int(n_s_rows),
        "p0_row_view_applications": int(n_s_apps),
        "p0_status_counts": dict(status_counts),
        "p1_rows_read": int(n_p_rows),
        "p1_enabled": not a.no_p1,
        "region_layer": 0,
        "coverage_any": round(float(covered.mean()), 6),
        "coverage_any_nodes": int(covered.sum()),
        "coverage_by_layer": {"0_S": int(hit_s.sum()),
                              "1_P": int(hit_p.sum()),
                              "2_R": 0},
        "observable_nonzero": int(((obs_tested > 0) &
                                   ((reach_po + reach_dff) > 0)).sum()),
        "trojan_named_nodes": int(trojan_name.sum()),
        "S_covered_of_trojan_named": int((hit_s & trojan_name).sum()),
        "P_covered_of_trojan_named": int((hit_p & trojan_name).sum()),
        "core_dim": len(core_idx),
        "core_names": core_names,
        "full_dim": len(full_names),
        "full_names": full_names,
        "miss": dict(prov),
        "netmap": mapper.summary(),
        "note": ("all P0 rows included (no proved-only filter); "
                 "influence_general for gate/cone/dff = forced all-1 output != "
                 "forced all-0 output; mux keeps selector influence; "
                 "XOR/XNOR still need toggle-one queries for influence, so "
                 "frac_decided is the primary functional bit; "
                 "no 0.5 imputation; covered is the last mask-like flag"),
    }
    (pt_dir / f"satrel_node_meta_sat{sfx}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[out] {pt_dir / f'satrel_node_feats_sat{sfx}.npy'} shape={Fc.shape} core={core_names}")
    print(f"[out] {pt_dir / f'satrel_node_feats_sat_full{sfx}.npy'} shape={F.shape}")
    print(f"[out] {pt_dir / f'satrel_node_mask_sat{sfx}.npy'} shape={mk.shape}")
    print(f"[meta] {json.dumps(meta, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



