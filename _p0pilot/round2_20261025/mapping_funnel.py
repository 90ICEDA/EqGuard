"""Stage-by-stage mapping funnel for existing cone/dff_next relations.

No SAT queries. Losses are classified, never silently filled.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2"


def main() -> int:
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {v: r for r in ("train", "val", "test") for v in split[f"{r}_views"]}
    views = []
    for role in ("train", "val", "test"):
        views += split[f"{role}_views"]
    by_key = defaultdict(list)
    for v in views:
        p = v.split("__")
        by_key[(p[0], p[1], p[-1])].append(v)
    digest = {}

    def sha(path: Path):
        if str(path) not in digest:
            digest[str(path)] = (hashlib.sha256(path.read_bytes()).hexdigest()
                                 if path.exists() else None)
        return digest[str(path)]

    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, uniq_views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    del fids
    view_names = defaultdict(set)
    with (PT / "node_names_trans.txt").open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= vid.size:
                break
            view_names[int(vid[i])].add(line.strip().lstrip("\\"))
    print("node lists ready", len(view_names), flush=True)

    rel = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv",
                      encoding="utf-8-sig").fillna("")
    rel = rel[rel["kind"].isin(["cone", "dff_next"])].copy()
    rel["role"] = rel["design"].map(lambda d: role_of_view.get(Path(str(d)).stem, "unassigned"))
    rel["host"] = rel["design"].str.split("__").str[0]
    rel["recipe"] = rel["design"].str.split("__").str[-1].str.replace(".v", "", regex=False)

    cache = {}
    rows = []
    for _, r in rel.iterrows():
        design = str(r["design"])
        if design not in cache:
            logp = ROOT / str(r["log"])
            raw = logp.with_name(logp.name.replace(".sat.log", ".struct_raw.json"))
            cache[design] = None
            if raw.exists():
                try:
                    mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
                    mod = mods.get(str(r["top"])) or next(iter(mods.values()))
                    netbits = {nm: [b for b in info.get("bits", []) if isinstance(b, int)]
                               for nm, info in mod["netnames"].items()}
                    drivers = defaultdict(set)
                    for cn, c in mod["cells"].items():
                        dirs = c.get("port_directions", {})
                        for pin, bits in c["connections"].items():
                            if dirs.get(pin) == "output" or (not dirs and pin in ("Y", "Q", "QN")):
                                for b in bits:
                                    if isinstance(b, int):
                                        drivers[b].add(cn)
                    cache[design] = (netbits, drivers)
                except Exception as e:  # noqa: BLE001
                    cache[design] = ("error", str(e))
        got = cache[design]
        q = [r[f"sat_q{i}"] for i in range(1, 5)]
        stage = ("queries_all4_definite" if all(v in ("proved", "refuted") for v in q)
                 else "queries_incomplete")
        net = str(r["target"])
        bits, drv, reason = [], set(), ""
        if isinstance(got, tuple) and len(got) == 2:
            netbits, drivers = got
            bits = netbits.get(net, [])
            if not bits:
                cand = [k for k in netbits if k.lstrip("\\") == net.lstrip("\\")]
                if cand:
                    bits = netbits[cand[0]]
                    reason = "name_escape_or_alias"
            if not bits:
                reason = reason or "target_net_not_in_struct_raw"
            else:
                drv = set().union(*(drivers.get(b, set()) for b in bits))
                if not drv:
                    reason = "no_driver_for_bits"
        else:
            reason = "struct_raw_missing_or_invalid"
        parts = Path(design).stem.split("__")
        eligible = [v for v in by_key.get((parts[0], parts[1], parts[-1]), [])
                    if sha(WORK / "trans" / f"{v}.v") == sha(WORK / "trans" / design)
                    and sha(WORK / "trans" / design) is not None]
        names = set().union(*(view_names[int(i)] for i, v in enumerate(uniq_views)
                              if str(v) in eligible)) if eligible else set()
        attach = {c.lstrip("\\") for c in drv}
        if r["kind"] == "dff_next" and r["cell"]:
            attach.add(str(r["cell"]).lstrip("\\"))
        mapped = attach & names
        if stage == "queries_all4_definite" and not reason:
            if len(drv) > 1:
                reason = "multi_driver_ambiguous"
            elif not mapped:
                reason = "driver_cell_not_in_node_list"
            elif any(c not in names for c in attach):
                reason = "partial_attach_missing"
        rows.append(dict(design=design, role=r["role"], host=r["host"], recipe=r["recipe"],
                         kind=r["kind"], cell=r["cell"], target=net, stage=stage,
                         n_bits=len(bits), n_drivers=len(drv), n_attach=len(attach),
                         n_mapped_in_node_list=len(mapped), n_eligible_views=len(eligible),
                         reason=reason))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "mapping_funnel_rows.csv", index=False, encoding="utf-8-sig")
    print("\n[stage by role]\n", d.groupby(["role", "stage"]).size().to_string(), flush=True)
    print("\n[reason counts]\n", d["reason"].value_counts().to_string(), flush=True)
    print("\n[reason by host/recipe]\n",
          d.groupby(["role", "host", "recipe", "reason"]).size().to_string(), flush=True)
    print("\n[attach size]\n", d.groupby(["kind", "n_attach"]).size().to_string(), flush=True)
    print("\n[bit width]\n", d.groupby(["kind", "n_bits"]).size().to_string(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
