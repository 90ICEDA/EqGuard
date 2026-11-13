"""build_p0clean4.py -- leakage-controlled SAT features from SAT-v3 evidence.

Variants (all share the 7 functional core columns of p0clean3):
  safe    : core(7) + case counts(4) + proved/partial frac(2) + covered(1) = 14
  struct  : safe + is_S + is_P (before covered)                           = 16
  control : struct with is_S shuffled **within each view**                = 16

v3 separates `structural` (simple gate/mux decides itself), `proved_sat`
(cone/DFF with SAT proved decided AND influence) and `partial_sat`, so
`proved_sat` is a real functional relation. `is_S` is label-adjacent
(AP ~5x base) -> `safe` is primary, `struct`/`control` are the ablation.
Last column is the `covered` mask (training reads C[:, -1]).
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase2" / "ys"))
import netmap as NM          # noqa: E402  assign/alias/driver resolution
import satrel_node_feats_sat as NF  # noqa: E402 name maps

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
V3 = T / "functional_relations_v3.csv"
SRC3 = PT / "satrel_node_feats_sat_p0clean3.npy"
DEC = re.compile(r"^g_{1,2}(.+)_\d+$")
CLASSES = ["gate_simple", "mux_cell", "cone_po", "dff_next"]
STATUS = ["structural", "proved_sat", "partial_sat"]
SEED = 20261024


def base_name(n: str) -> str:
    m = DEC.match(n or "")
    return m.group(1) if m else (n or "")


def view_blocks(meta_path: Path):
    """file_ids -> (unique views, view_id per node)."""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fid = meta["file_ids"]
    vid, views = pd.factorize(np.asarray(fid, dtype=object), sort=False)
    vid = vid.astype(np.int16)
    del fid, meta
    return views.tolist(), vid


def case_table():
    """(design, net) -> per-class / per-status counts."""
    d = pd.read_csv(V3, encoding="utf-8-sig",
                    usecols=["design", "target", "cut_nets", "cell",
                             "case_class", "status_v3"]).fillna("")
    tab: dict[tuple, list] = {}
    for design, target, cuts, cell, cl, st in zip(
            d.design, d.target, d.cut_nets, d.cell, d.case_class, d.status_v3):
        nets = set()
        if target:
            nets.add(str(target))
        for c in str(cuts).split(";"):
            c = c.strip()
            if c:
                nets.add(c)
        if cell:
            nets.add(str(cell))
        if not nets:
            continue
        dv = str(design)
        if dv.endswith(".v"):
            dv = dv[:-2]
        for net in nets:
            k = (dv, net)
            row = tab.get(k)
            if row is None:
                row = [0] * (len(CLASSES) + len(STATUS))
                tab[k] = row
            if cl in CLASSES:
                row[CLASSES.index(cl)] += 1
            if st in STATUS:
                row[len(CLASSES) + STATUS.index(st)] += 1
    print(f"[v3] keys={len(tab)} rows={len(d)}")
    return tab


def grouped_indices(vid: np.ndarray, n_views: int) -> list[np.ndarray]:
    """Stable groups preserve legacy within-view order and every RNG draw."""
    order = np.argsort(vid, kind="stable")
    counts = np.bincount(vid, minlength=n_views)
    return list(np.split(order, np.cumsum(counts)[:-1]))


def log_norm(a: np.ndarray, vid: np.ndarray, n_views: int, groups=None) -> np.ndarray:
    out = np.log1p(a.astype(np.float32))
    for idx in groups if groups is not None else grouped_indices(vid, n_views):
        if idx.size == 0:
            continue
        mx = float(out[idx].max())
        if mx > 0:
            out[idx] /= mx
    return out
def aggregate_netmap(n: int, nk: int) -> tuple[np.ndarray, int]:
    """Same aggregation, but resolve nets through NetMapper (assign/alias/driver)."""
    d = pd.read_csv(V3, encoding="utf-8-sig",
                    usecols=["design", "target", "cut_nets", "cell",
                             "case_class", "status_v3"]).fillna("")
    names, fid = NF.load_names(PT, WORK)
    views = sorted(set(fid))
    exact, basem = NF.build_maps(names, fid, views)
    del names, fid
    mapper = NM.NetMapper(exact, basem, WORK / "trans",
                          struct_dirs=NM.default_struct_dirs(NF.BASE),
                          use_json=True, max_alias=8, include_sinks=False)
    print(f"[netmap] {mapper.summary()}")
    acc = np.zeros((n, nk), np.int32)
    hit: set[int] = set()
    for design, target, cuts, cell, cl, st in zip(
            d.design, d.target, d.cut_nets, d.cell, d.case_class, d.status_v3):
        dv = str(design)
        if dv.endswith(".v"):
            dv = dv[:-2]
        nets = set()
        if target:
            nets.add(str(target))
        for c in str(cuts).split(";"):
            c = c.strip()
            if c:
                nets.add(c)
        if cell:
            nets.add(str(cell))
        ci = CLASSES.index(cl) if cl in CLASSES else -1
        si = STATUS.index(st) if st in STATUS else -1
        ids: set[int] = set()
        for net in nets:
            ids.update(mapper.ids(dv, net))
        for i in ids:
            if ci >= 0:
                acc[i, ci] += 1
            if si >= 0:
                acc[i, len(CLASSES) + si] += 1
            hit.add(i)
    return acc, len(hit)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--netmap", action="store_true", help="resolve nets via NetMapper")
    ap.add_argument("--suffix", default="", help="output suffix, e.g. nm")
    ap.add_argument("--only", default="", help="fast core-only export: comma-separated core_only/core_p0rel/core_reach/core_p1/covered_only; requires --suffix")
    a = ap.parse_args()

    if a.only:
        # These variants depend only on the inherited core. Avoid parsing netlists,
        # loading node names, constructing 19 arrays, and advancing any RNG.
        columns = {"core_only": list(range(7)) + [9], "core_p0rel": [0,1,2,3,9],
                   "core_reach": [4,5,9], "core_p1": [6,9], "covered_only": [9]}
        chosen = a.only.split(",")
        if not a.suffix or any(k not in columns for k in chosen) or a.netmap:
            ap.error("--only requires --suffix, supports inherited-core variants only, and cannot use --netmap")
        source = np.load(SRC3, mmap_mode="r")
        for variant in chosen:
            dest = PT / f"satrel_node_feats_sat_p0clean4_{a.suffix}_{variant}.npy"
            if dest.exists():
                raise FileExistsError(f"refusing to replace {dest}")
            result = np.lib.format.open_memmap(dest, mode="w+", dtype=np.float32,
                                               shape=(len(source),len(columns[variant])))
            for start in range(0,len(source),262144):
                result[start:start+262144] = source[start:start+262144, columns[variant]]
            result.flush()
            print(f"[fast-export] {dest} {result.shape}")
        return 0

    core = np.load(SRC3)                      # (n, 10)
    n = core.shape[0]
    core7 = core[:, :7].astype(np.float32)
    is_s = core[:, 7].astype(np.float32)
    is_p = core[:, 8].astype(np.float32)
    cov = core[:, 9].astype(np.float32)
    print(f"[core] {core.shape} S={int(is_s.sum())} P={int(is_p.sum())} cover={cov.mean():.4f}")
    del core

    views, vid = view_blocks(WORK / "data/for_train/metadata_trans.json")
    all_idx = grouped_indices(vid, len(views))
    print(f"[views] {len(views)} nodes={n}")

    nk = len(CLASSES) + len(STATUS)
    if a.netmap:
        acc, hit = aggregate_netmap(n, nk)
    else:
        tab = case_table()
        acc = np.zeros((n, nk), np.int32)
        hit = 0
        view_arr = np.asarray(views, dtype=object)
        with (PT / "node_names_trans.txt").open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                nm = line.rstrip("\n")
                if not nm:
                    continue
                v = view_arr[vid[i]]
                row = tab.get((v, nm))
                if row is None:
                    row = tab.get((v, base_name(nm)))
                if row is not None:
                    acc[i] = row
                    hit += 1
        del tab
    print(f"[map] matched nodes={hit} ({hit / max(n, 1):.6f})")

    cls_cnt = acc[:, :len(CLASSES)]
    st_cnt = acc[:, len(CLASSES):]
    denom = np.maximum(cls_cnt.sum(1).astype(np.float32), 1.0)
    feats = [log_norm(cls_cnt[:, k], vid, len(views), all_idx)[:, None] for k in range(len(CLASSES))]
    feats.append((st_cnt[:, 1] / denom)[:, None])      # frac_proved_sat
    feats.append((st_cnt[:, 2] / denom)[:, None])      # frac_partial_sat
    v4 = np.concatenate(feats, axis=1).astype(np.float32)

    safe = np.concatenate([core7, v4, cov[:, None]], axis=1).astype(np.float32)
    struct = np.concatenate([core7, v4, is_s[:, None], is_p[:, None], cov[:, None]], axis=1)
    struct = struct.astype(np.float32)

    rng = np.random.default_rng(SEED)
    is_s_shuf = is_s.copy()
    for j in range(len(views)):
        idx = all_idx[j]
        if idx.size:
            is_s_shuf[idx] = is_s[rng.permutation(idx)]
    control = np.concatenate([core7, v4, is_s_shuf[:, None], is_p[:, None], cov[:, None]],
                             axis=1).astype(np.float32)

    # shuffle6: permute the 6 v3-evidence columns within each view (position-prior control)
    v4_shuf = v4.copy()
    for j in range(len(views)):
        idx = all_idx[j]
        if idx.size:
            perm = rng.permutation(idx)
            v4_shuf[idx] = v4[perm]
    shuffle6 = np.concatenate([core7, v4_shuf, cov[:, None]], axis=1).astype(np.float32)

    # split the 6 v3 columns: counts (n_*_log) vs verdicts (frac_proved/partial_sat)
    counts_only = np.concatenate([core7, v4[:, :4], cov[:, None]], axis=1).astype(np.float32)
    verdict_only = np.concatenate([core7, v4[:, 4:], cov[:, None]], axis=1).astype(np.float32)
    core_only = np.concatenate([core7, cov[:, None]], axis=1).astype(np.float32)

    # verdict_perm: keep counts + evidence support, permute verdict values among case nodes
    vp = safe.copy()
    has_case = cls_cnt.sum(1) > 0
    for j in range(len(views)):
        idx = all_idx[j]
        if idx.size == 0:
            continue
        sel = idx[has_case[idx]]
        if sel.size > 1:
            vp[sel[:, None], np.array([11, 12])] = v4[rng.permutation(sel)][:, 4:6]
    verdict_perm = vp.astype(np.float32)

    # verdict_valueperm: keep each verdict column's non-zero mask EXACTLY, permute only
    # the values among the non-zero nodes of that column (support-preserving semantics test)
    vvp = safe.copy()
    for col in (11, 12):
        base = np.asarray(v4[:, col - 7])
        out = base.copy()
        for j in range(len(views)):
            idx = all_idx[j]
            if idx.size == 0:
                continue
            nz = idx[base[idx] != 0]
            if nz.size > 1:
                out[nz] = base[rng.permutation(nz)]
        vvp[:, col] = out
    verdict_valueperm = vvp.astype(np.float32)

    # verdict_randsupport: keep core7 + counts; move each verdict column's support to a
    # RANDOM node set of the same size within the view (same value multiset).
    # If AP stays ~safe -> only "how many nodes are flagged"; if it drops -> node identity matters.
    vrs = safe.copy()
    for col in (11, 12):
        base = np.asarray(v4[:, col - 7])
        out = np.zeros(n, np.float32)
        for j in range(len(views)):
            idx = all_idx[j]
            nz = idx[base[idx] != 0]
            if nz.size == 0 or idx.size <= nz.size:
                out[idx] = base[idx]
                continue
            vals = base[nz]
            pick = rng.choice(idx, size=nz.size, replace=False)
            out[pick] = vals[rng.permutation(nz.size)]
        vrs[:, col] = out
    verdict_randsupport = vrs.astype(np.float32)

    # ---- feature-localisation variants (all share core7 offsets / covered mask) ----
    # core7 order: 0 n_rel_log, 1 frac_decided, 2 frac_influence, 3 frac_proved,
    #              4 reach_po_log, 5 reach_dff_log, 6 p1_ratio
    sub = lambda idx: np.concatenate([core7[:, idx], cov[:, None]], axis=1).astype(np.float32)
    core_p0rel = sub([0, 1, 2, 3])      # P0 relation/verdict fractions
    core_reach = sub([4, 5])            # reachability (observability)
    core_p1 = sub([6])                  # P1 equivalence ratio
    covered_only = cov[:, None].astype(np.float32)
    verdict_proved = np.concatenate([core7, v4[:, 4:5], cov[:, None]], axis=1).astype(np.float32)
    verdict_partial = np.concatenate([core7, v4[:, 5:6], cov[:, None]], axis=1).astype(np.float32)

    # safe without the n_mux column (test whether one shortcut column carries the gain)
    keep_cols = [0, 2, 3, 4, 5]             # v4 minus n_mux (v4 index 1)
    safe_nomux = np.concatenate([core7, v4[:, keep_cols], cov[:, None]], axis=1).astype(np.float32)
    # n_mux only (39 + 1 + covered) -- single-feature model
    mux_only = np.concatenate([v4[:, 1:2], cov[:, None]], axis=1).astype(np.float32)

    # core7 + 2 RANDOM binary columns with the same per-view non-zero counts as the
    # real verdict columns (no counts block). If this also ~0.063, the verdict "gain"
    # is an optimisation artefact, not information.
    rand2 = np.zeros((n, 2), np.float32)
    for col, src in ((0, 11), (1, 12)):
        base = np.asarray(safe[:, src])
        for j in range(len(views)):
            idx = all_idx[j]
            k = int((base[idx] != 0).sum())
            if idx.size and k:
                pick = rng.choice(idx, size=k, replace=False)
                rand2[pick, col] = 1.0
    core_rand2 = np.concatenate([core7, rand2, cov[:, None]], axis=1).astype(np.float32)

    names = ["n_rel_log", "frac_decided", "frac_influence", "frac_proved",
             "reach_po_log", "reach_dff_log", "p1_ratio",
             "n_gate_log", "n_mux_log", "n_cone_log", "n_dff_log",
             "frac_proved_sat", "frac_partial_sat", "covered"]
    outs = {"safe": safe, "struct": struct, "control": control, "shuffle6": shuffle6,
            "counts_only": counts_only, "verdict_only": verdict_only,
            "core_only": core_only, "verdict_perm": verdict_perm,
            "verdict_valueperm": verdict_valueperm,
            "verdict_randsupport": verdict_randsupport,
            "core_p0rel": core_p0rel, "core_reach": core_reach, "core_p1": core_p1,
            "covered_only": covered_only,
            "verdict_proved": verdict_proved, "verdict_partial": verdict_partial,
            "safe_nomux": safe_nomux, "mux_only": mux_only,
            "core_rand2": core_rand2}
    meta = {
        "source": str(V3), "core_source": str(SRC3), "n_nodes": int(n),
        "n_views": len(views), "mapped_nodes": int(hit),
        "covered": round(float(cov.mean()), 6),
        "n_s": int(is_s.sum()), "n_p": int(is_p.sum()),
        "variants": {k: int(v.shape[1]) for k, v in outs.items()},
        "names": {"safe": names,
                  "struct": names[:-1] + ["is_S", "is_P", "covered"],
                  "control": names[:-1] + ["is_S_shuffled_within_view", "is_P", "covered"],
                  "shuffle6": names[:-1] + ["v3_evidence_shuffled_within_view", "covered"],
                  "counts_only": names[:7] + names[7:11] + ["covered"],
                  "verdict_only": names[:7] + names[11:13] + ["covered"],
                  "core_only": names[:7] + ["covered"],
                  "verdict_perm": names,
                  "verdict_valueperm": names,
                  "verdict_randsupport": names,
                  "core_p0rel": names[:4] + ["covered"],
                  "core_reach": names[4:6] + ["covered"],
                  "core_p1": [names[6], "covered"],
                  "covered_only": ["covered"],
                  "verdict_proved": names[:7] + [names[11], "covered"],
                  "verdict_partial": names[:7] + [names[12], "covered"],
                  "safe_nomux": names[:8] + names[9:13] + ["covered"],
                  "mux_only": [names[8], "covered"],
                  "core_rand2": names[:7] + ["rand_flag_a", "rand_flag_b", "covered"]},
        "case_counts": {c: int(cls_cnt[:, i].sum()) for i, c in enumerate(CLASSES)},
        "status_counts": {s: int(st_cnt[:, i].sum()) for i, s in enumerate(STATUS)},
        "seed_shuffle": SEED,
        "note": ("proved_sat = cone/DFF with SAT proved decided AND influence; "
                 "structural (simple gate/mux) only counted in n_*_log, never as proved. "
                 "is_S is label-adjacent -> safe is primary, struct/control are ablation."),
    }
    sfx = f"_{a.suffix}" if a.suffix else ""
    for k, v in outs.items():
        p = PT / f"satrel_node_feats_sat_p0clean4{sfx}_{k}.npy"
        np.save(p, v)
        print(f"[out] {p} {v.shape}")
    meta_path = PT / f"satrel_node_feats_sat_p0clean4{sfx}_meta.json"
    (meta_path).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[out] {meta_path}")
    print(json.dumps({k: meta[k] for k in ("mapped_nodes", "variants", "case_counts", "status_counts")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

