"""Map round-6 cut leaves to graph nodes (one scan of node names)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
R3 = ROOT / "_p0pilot/round3_20261025"
R6 = ROOT / "_p0pilot/round6_20261025"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"
sys.path.insert(0, str(R3))
from r3_nets import build_index  # noqa: E402


def main() -> int:
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    allowed = {r: set(split[f"{r}_views"]) for r in ("train", "val")}
    role_of_view = {v: r for r in allowed for v in allowed[r]}
    plan = json.loads((TAB6 / "r6_candidate_plan.json").read_text(encoding="utf-8"))
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    del fids
    by_key = defaultdict(list)
    for i, v in enumerate(views):
        p = str(v).split("__")
        by_key[(p[0], p[1], p[-1])].append(i)
    digest = {}

    def sha(p: Path):
        if str(p) not in digest:
            digest[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return digest[str(p)]

    rel = pd.read_csv(TAB6 / "r6_nonlocal_relations.csv", encoding="utf-8-sig")
    attach = {}
    idx_cache = {}
    for _, r in rel.iterrows():
        design = str(r.design)
        if design not in idx_cache:
            mods = json.loads((R6 / "struct_raw" / f"{Path(design).stem}.json")
                              .read_text(encoding="utf-8"))["modules"]
            idx_cache[design] = build_index(next(iter(mods.values())))
        idx = idx_cache[design]
        names = {str(r.driver).lstrip("\\")}
        if r.kind == "dff_next":
            bits = idx["netbits"].get(str(r.target), ())
            for cn, con in idx["dff_cells"].items():
                if bits and any(b in con.get("D", []) for b in bits):
                    names.add(cn.lstrip("\\"))
        attach[r.relation_id] = names
    desired = set().union(*attach.values())
    hits = defaultdict(list)
    with (PT / "node_names_trans.txt").open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= vid.size:
                break
            nm = line.strip().lstrip("\\")
            if nm in desired:
                hits[nm].append((i, int(vid[i])))
    rows, mrows = [], []
    for _, r in rel.iterrows():
        design = str(r.design)
        parts = Path(design).stem.split("__")
        elig = [i for i in by_key.get((parts[0], parts[1], parts[-1]), [])
                if sha(WORK / "trans" / f"{views[i]}.v") == sha(WORK / "trans" / design)]
        for vi in elig:
            mapped = []
            for nm in sorted(attach[r.relation_id]):
                ids = [i for i, vv in hits.get(nm, []) if vv == vi]
                if ids:
                    mapped.append(nm)
                    for ni in ids:
                        rows.append(dict(relation_id=r.relation_id, design=design,
                                         view=str(views[vi]),
                                         role=role_of_view[str(views[vi])],
                                         name=nm, node_index=int(ni),
                                         target_id=r.target_id))
            mrows.append(dict(relation_id=r.relation_id, design=design,
                              view=str(views[vi]),
                              role=role_of_view[str(views[vi])],
                              attach=len(attach[r.relation_id]), mapped=len(mapped),
                              missing=len(attach[r.relation_id]) - len(mapped),
                              missing_names=";".join(sorted(
                                  attach[r.relation_id] - set(mapped)))))
    nd = pd.DataFrame(rows)
    if len(nd):
        nd = nd.drop_duplicates(["relation_id", "view", "node_index"])
    else:
        nd = pd.DataFrame(columns=["relation_id", "design", "view", "role",
                                   "name", "node_index", "target_id"])
    nd.to_csv(TAB6 / "r6_nodes.csv", index=False, encoding="utf-8-sig")
    md = pd.DataFrame(mrows)
    md.to_csv(TAB6 / "r6_mapping_by_view.csv", index=False, encoding="utf-8-sig")
    info = dict(relations=len(plan["frozen"]), node_rows=len(nd),
                unique_nodes=int(nd.node_index.nunique()),
                views=int(md.view.nunique()), mapping_rows=len(md),
                all_mapped=int((md.missing == 0).sum()),
                missing_names=int(md.missing.sum()))
    (TAB6 / "r6_mapping_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    print(md[md.missing > 0].to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())