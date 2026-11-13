"""Round-15 corrected signal-coordinate contract (no SAT/training)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
T10 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round10"
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"
T14 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round14"
T15 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
sys.path.insert(0, str(ROOT / "_p0pilot/round12_20261025"))
from audit_blockers import NetIndex, load_raw  # noqa: E402


def main() -> int:
    T15.mkdir(parents=True, exist_ok=True)
    pairs = json.loads((T11 / "validated_pairs_cumulative.json").read_text(
        encoding="utf-8"))
    old = json.loads((T14 / "pair_sample_manifest.json").read_text(
        encoding="utf-8"))
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    N = int(g.y.size(0))
    names = (PT / "node_names_trans.txt").read_text(
        encoding="utf-8", errors="replace").splitlines()
    fids = np.asarray(json.loads((ROOT / "generate_trans/folds/hosts_bt31/data/for_train/"
                                  "metadata_trans.json").read_text(
                                      encoding="utf-8"))["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    view_of_node = {i: str(views[int(vid[i])]) for i in range(len(vid))}

    recs, coords, targets = [], [], []
    for item, prev in zip(pairs, old):
        rid = item["relation_id"]
        rel_coords, target_info = [], None
        raw_cache = {}
        for slot in range(5):
            side_coords = {}
            for side, view, nets in (("source", item["source_view"], item["source_nets"]),
                                     ("partner", item["partner_view"], item["partner_nets"])):
                net = nets[slot]
                if view not in raw_cache:
                    m, info, path = load_raw(view)
                    raw_cache[view] = (NetIndex(m), info, path)
                ix, info, path = raw_cache[view]
                bits = ix.bits(net)
                bit = bits[0] if len(bits) == 1 else None
                drv = ix.drv.get(bit, []) if bit is not None else []
                if drv:
                    cell, typ, out_pin = drv[0]
                else:
                    cell = typ = out_pin = None
                pi, pi_valid = None, False
                if bit is not None:
                    for pn, p in ix.m.get("ports", {}).items():
                        pbits = [b for b in p.get("bits", []) if isinstance(b, int)]
                        if p.get("direction") == "input" and bit in pbits:
                            pi = f"{pn}[{pbits.index(bit)}]"
                            pi_valid = True
                            break
                node_idx = prev["cut_coordinates"][slot][side]["node_index"]
                valid = bool(node_idx is not None and 0 <= int(node_idx) < N)
                node_idx = int(node_idx) if valid else None
                if node_idx is not None:
                    assert view_of_node.get(node_idx) == view, (view, node_idx)
                aliases = sorted(n for n, v in ix.nets.items()
                                 if v.get("bits") == [bit]) if bit is not None else []
                same_cell_outputs = []
                if cell:
                    for b2 in ix.outnet.get(cell, []):
                        ns = sorted(n for n, v in ix.nets.items() if v.get("bits") == [b2])
                        same_cell_outputs.append(dict(
                            bit=b2, nets=ns[:4],
                            pin=next((p for c, t, p in ix.drv.get(b2, [])
                                      if c == cell), "")))
                dff = bool(typ and ("DFF" in typ.upper() or "LATCH" in typ.upper()))
                qpin = out_pin if dff else None
                polarity = (1 if qpin == "Q" else -1 if qpin == "QN" else 0) if dff else 0
                c = dict(
                    relation_id=rid, slot=slot, is_target=int(slot == 4), side=side,
                    view=view, raw_snapshot=str(path.relative_to(ROOT)),
                    source_sha=info["source_sha"], raw_sha=info["raw_sha"],
                    net=net, bit=bit, driver_cell=cell, driver_type=typ,
                    output_pin=out_pin, physical_Q=cell if dff else None,
                    q_pin=qpin, polarity=polarity, node_index=node_idx,
                    node_name=names[node_idx].strip().lstrip("\\") if node_idx is not None else None,
                    split=("train" if node_idx is not None and bool(g.train_mask[node_idx])
                           else "val" if node_idx is not None and bool(g.val_mask[node_idx])
                           else "other" if node_idx is not None else None),
                    pi_anchor=pi, pi_valid=pi_valid,
                    valid_index=int(node_idx is not None),
                    aliases=aliases[:12], same_bit_alias_count=max(0, len(aliases) - 1),
                    same_cell_outputs=same_cell_outputs[:8])
                side_coords[side] = c
                coords.append(c)
            rel_coords.append(dict(slot=slot, **{s: side_coords[s]
                                                 for s in ("source", "partner")}))
            if slot == 4:
                target_info = side_coords

        recs.append(dict(
            sample_id=rid, relation_id=rid, role=item["role"],
            source_view=item["source_view"], partner_view=item["partner_view"],
            source_sha=item["source_sha"], partner_sha=item["partner_sha"],
            context_id=item["context_id"], cut_coordinates=rel_coords[:4],
            target=dict(slot=4, **target_info), evidence_refs=prev["evidence_refs"],
            feature_18d=prev["feature_18d"]))
        tnodes = [x["node_index"] for x in target_info.values()
                  if isinstance(x, dict) and x.get("node_index") is not None]
        targets.append(dict(relation_id=rid, role=item["role"],
                            target_nodes=sorted(set(tnodes)),
                            source_target=target_info["source"]["node_index"],
                            partner_target=target_info["partner"]["node_index"]))
    by_node = defaultdict(set)
    for c in coords:
        if c["node_index"] is not None:
            by_node[c["node_index"]].add(c["relation_id"])
    for c in coords:
        c["shared_node_relations"] = (sorted(by_node.get(c["node_index"], []))
                                      if c["node_index"] is not None else [])
    for r in recs:
        for c in r["cut_coordinates"]:
            for s in ("source", "partner"):
                n = c[s]["node_index"]
                c[s]["shared_node_relations"] = sorted(by_node.get(n, [])) if n is not None else []
        for s in ("source", "partner"):
            n = r["target"][s]["node_index"]
            r["target"][s]["shared_node_relations"] = sorted(by_node.get(n, [])) if n is not None else []
    (T15 / "signal_contract_manifest.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(coords).to_csv(T15 / "signal_coordinates.csv", index=False,
                                encoding="utf-8-sig")
    pd.DataFrame(targets).to_csv(T15 / "target_support.csv", index=False,
                                 encoding="utf-8-sig")
    valid = [c for c in coords if c["valid_index"]]
    pi = [c for c in coords if c["node_index"] is None and c["pi_anchor"]]
    unbound = [c for c in coords if c["pi_anchor"] and not c["pi_valid"]]
    qn = [c for c in coords if c["q_pin"] == "QN"]
    q = [c for c in coords if c["q_pin"] == "Q"]
    shared = [c for c in valid if len(c["shared_node_relations"]) > 1]
    same_bit = [c for c in coords if c["same_bit_alias_count"] > 0]
    same_cell = [c for c in coords if len(c["same_cell_outputs"]) > 1]
    tmap = defaultdict(list)
    for t in targets:
        for n in t["target_nodes"]:
            tmap[n].append(t["relation_id"])
    conflict = {str(n): v for n, v in tmap.items() if len(v) > 1}
    role_counts = pd.Series([c["split"] for c in valid]).value_counts().to_dict()
    uniq_nodes = sorted({c["node_index"] for c in valid})
    uniq_roles = {"train": 0, "val": 0, "test": 0, "other": 0}
    for n in uniq_nodes:
        if bool(g.train_mask[n]):
            uniq_roles["train"] += 1
        elif bool(g.val_mask[n]):
            uniq_roles["val"] += 1
        elif bool(g.test_mask[n]):
            uniq_roles["test"] += 1
        else:
            uniq_roles["other"] += 1
    groups = defaultdict(list)
    for c in valid:
        groups[(c["relation_id"], c["side"], c["node_index"])].append(c)
    multi = {str(k): [dict(bit=x["bit"], pin=x["q_pin"], cell=x["physical_Q"])
                      for x in v] for k, v in groups.items() if len(v) > 1}
    qn_groups = {k: v for k, v in multi.items()
                 if len({x["bit"] for x in v}) > 1
                 and all(x["pin"] in ("Q", "QN") for x in v)}
    summary = dict(
        relations=len(recs), coordinates=len(coords), cut_slots=4, target_slot=4,
        valid_coordinates=len(valid),
        valid_unique_node_indices=len(uniq_nodes),
        valid_unique_role_counts=uniq_roles,
        valid_coordinate_role_counts=role_counts,
        target_support_unique=len(tmap),
        target_support_train=sum(bool(g.train_mask[int(k)]) for k in tmap),
        target_support_val=sum(bool(g.val_mask[int(k)]) for k in tmap),
        target_conflicts=conflict,
        target_aggregation_rule=("max per column if conflict; otherwise one relation per "
                                 "target; conflicts are reported, never silently overwritten"),
        pi_anchor_records=len(pi), pi_unbound=len(unbound),
        pi_examples=[c["pi_anchor"] for c in pi[:10]],
        q_pin_records=len(q), qn_pin_records=len(qn),
        qn_duplicate_groups=qn_groups,
        same_bit_alias_coords=len(same_bit), same_cell_multi_output_coords=len(same_cell),
        shared_node_coords=len(shared),
        shared_node_relations={str(k): sorted(v) for k, v in by_node.items() if len(v) > 1},
        raw_sha_ok=int(all(c["raw_sha"] for c in coords)),
        view_hash_ok=int(all(c["source_sha"] for c in coords)))
    (T15 / "signal_contract_validation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())