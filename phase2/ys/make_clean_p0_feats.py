"""make_clean_p0_feats.py -- build leak-free node features from label-agnostic P0.

New writer only: it does not modify the legacy satrel_node_feats_sat*.npy files.

Inputs
  --p0-csv   merged label-agnostic P0 CSV
  P1 table   <tables>/node_pairs_sat_node.csv (all-anchor SAT pairs)

Outputs (tag suffix defaults to _p0clean)
  satrel_node_feats_sat_p0clean.npy       (n_trans, 9) float32
  satrel_node_feats_sat_full_p0clean.npy  (n_trans,14) float32
  satrel_node_mask_sat_p0clean.npy        (n_trans, 3) float32
  satrel_node_meta_sat_p0clean.json

Clean 9-dim core (no region_edges, no name-derived covered leakage):
  [0] is_target
  [1] is_cut_data
  [2] is_cell
  [3] decided
  [4] influence
  [5] observable
  [6] log1p(P1 proved count), within-view max-normalised
  [7] P1 proved_ratio = proved/(proved+differ)
  [8] covered flag = (S or P evidence exists)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
    """rs232t1000__inst__keepcur__ys_id -> rs232t1000."""
    s = str(top or "").strip()
    if s.endswith(".v"):
        s = s[:-2]
    return s.split("__", 1)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p0-csv", type=Path, default=DEFAULT_P0)
    ap.add_argument("--pt-dir", type=Path, default=DEFAULT_PT)
    ap.add_argument("--work", type=Path, default=DEFAULT_WORK)
    ap.add_argument("--tables", type=Path, default=NF.T)
    ap.add_argument("--tag-suffix", default="_p0clean")
    ap.add_argument("--status", choices=["proved", "proved_partial", "any"],
                    default="proved",
                    help="P0 status filter; default proved only (clean)")
    ap.add_argument("--no-p1", action="store_true",
                    help="skip all-anchor P1 proved counts")
    ap.add_argument("--p1-max-rows", type=int, default=0,
                    help="debug limit for P1 rows (0 = all)")
    ap.add_argument("--no-netmap", action="store_true",
                    help="legacy direct-name mapping (debug only)")
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

    F = np.zeros((n, 14), np.float32)
    mk = np.zeros((n, 3), np.float32)
    hit_s = np.zeros(n, bool)
    hit_p = np.zeros(n, bool)
    prov: dict[str, int] = defaultdict(int)

    # ---------------- S layer: label-agnostic P0 ----------------
    if not a.p0_csv.exists():
        raise SystemExit(f"[ERROR] missing P0 CSV: {a.p0_csv}")
    p0 = pd.read_csv(a.p0_csv, encoding="utf-8-sig").fillna("")
    if len(p0) == 0:
        raise SystemExit("[ERROR] P0 CSV has zero rows")
    n_s_rows = n_s_views = 0
    for _, r in p0.iterrows():
        st = str(r.get("status", "")).strip()
        if a.status == "proved" and st != "proved":
            continue
        if a.status == "proved_partial" and st not in ("proved", "partial"):
            continue
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
        decided = float(r.get("decided", 0) or 0)
        infl = float(r.get("influence", 0) or 0)
        # The agnostic P0 CSV has no `observable` column; derive it from the
        # reach columns when the column is absent/blank.  (2026-10-24 fix)
        obs_raw = r.get("observable", "")
        try:
            obs = float(obs_raw) if str(obs_raw).strip().lower() not in ("", "nan", "none") else 0.0
        except (TypeError, ValueError):
            obs = 0.0
        if obs == 0.0:
            try:
                n_po = float(r.get("n_po_reached", 0) or 0)
                n_dff = float(r.get("n_dff_reached", 0) or 0)
                obs = 1.0 if (n_po > 0 or n_dff > 0) else 0.0
            except (TypeError, ValueError):
                obs = 0.0
        cuts = [x.strip() for x in str(r.get("cut_nets", "")).split(";") if x.strip()]
        qnet = str(r.get("q_net", "")).strip()
        target = str(r.get("target", "")).strip()
        cell = str(r.get("cell", "")).strip()
        for v in vs:
            n_s_views += 1
            t_ids = mapper.ids(v, target) if target else []
            for i in t_ids:
                F[i, 0] = 1.0
                F[i, 6] = obs
                hit_s[i] = True
            for cu in cuts:
                for i in mapper.ids(v, cu):
                    F[i, 1] = 1.0
                    F[i, 4] = decided
                    F[i, 5] = infl
                    hit_s[i] = True
            if qnet:
                for i in mapper.ids(v, qnet):
                    F[i, 2] = 1.0
                    hit_s[i] = True
            if cell:
                for i in mapper.ids(v, cell):
                    F[i, 3] = 1.0
                    hit_s[i] = True
            if not t_ids:
                prov["S_target_miss"] += 1

    # ---------------- P1 layer: all-anchor proved pairs ----------------
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
            proved: dict[int, int] = defaultdict(int)
            differ: dict[int, set[str]] = defaultdict(set)
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
                key = f"{ia}/{ra}|{ib}/{rb}"
                for inst, rcp, net in ((ia, ra, na), (ib, rb, nb)):
                    if not (inst and rcp and net):
                        continue
                    for v in NF.views_for(views, host, inst, rcp):
                        for i in mapper.ids(v, net):
                            hit_p[i] = True
                            if stt == "proved":
                                proved[i] += 1
                            else:
                                differ[i].add(key)
            for i in np.where(hit_p)[0]:
                p_ = int(proved.get(int(i), 0))
                d_ = len(differ.get(int(i), set()))
                F[i, 8] = np.log1p(p_)
                F[i, 9] = np.log1p(d_)
                F[i, 10] = p_ / max(p_ + d_, 1)

            # Within-view max-normalisation of log1p(proved count).
            fa = np.asarray(fid, dtype=object)
            for v in views:
                idx = np.where(fa == v)[0]
                if len(idx) == 0:
                    continue
                mx = float(F[idx, 8].max())
                if mx > 0:
                    F[idx, 8] /= mx

    mk[:, 0] = hit_s
    mk[:, 1] = hit_p
    mk[:, 2] = 0.0          # no region layer in clean features
    covered = (mk.max(1) > 0).astype(np.float32)

    # target, cut, cell, decided, influence, observable, P1 count, P1 ratio
    core_idx = [0, 1, 3, 4, 5, 6, 8, 10]
    Fc = np.concatenate([F[:, core_idx], covered[:, None]], 1).astype(np.float32)

    sfx = a.tag_suffix or ""
    np.save(pt_dir / f"satrel_node_feats_sat{sfx}.npy", Fc)
    np.save(pt_dir / f"satrel_node_feats_sat_full{sfx}.npy", F)
    np.save(pt_dir / f"satrel_node_mask_sat{sfx}.npy", mk)

    trojan_name = np.array([("trojan" in (nm or "").lower()) for nm in names])
    meta = {
        "source_p0": str(a.p0_csv),
        "p0_status_filter": a.status,
        "n_nodes": int(n),
        "n_views": len(views),
        "p0_rows_used": int(n_s_rows),
        "p0_row_view_applications": int(n_s_views),
        "p1_rows_read": int(n_p_rows),
        "p1_enabled": not a.no_p1,
        "region_layer": 0,
        "coverage_any": round(float(covered.mean()), 6),
        "coverage_any_nodes": int(covered.sum()),
        "coverage_by_layer": {"0_S": int(mk[:, 0].sum()),
                              "1_P": int(mk[:, 1].sum()),
                              "2_R": int(mk[:, 2].sum())},
        "observable_nonzero": int((Fc[:, 5] > 0).sum()),
        "trojan_named_nodes": int(trojan_name.sum()),
        "S_covered_of_trojan_named": int((hit_s & trojan_name).sum()),
        "P_covered_of_trojan_named": int((hit_p & trojan_name).sum()),
        "miss": dict(prov),
        "netmap": mapper.summary(),
        "core_idx_full": core_idx,
        "core_note": ("9 dims: target, cut, cell, decided, influence, observable, "
                      "P1 log1p(proved)/view-max, P1 proved_ratio, covered; "
                      "NO region_edges / NO name-derived covered regions"),
    }
    (pt_dir / f"satrel_node_meta_sat{sfx}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[out] {pt_dir / f'satrel_node_feats_sat{sfx}.npy'} shape={Fc.shape}")
    print(f"[out] {pt_dir / f'satrel_node_feats_sat_full{sfx}.npy'} shape={F.shape}")
    print(f"[out] {pt_dir / f'satrel_node_mask_sat{sfx}.npy'} shape={mk.shape}")
    print(f"[meta] {json.dumps(meta, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


