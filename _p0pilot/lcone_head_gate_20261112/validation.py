"""Prepare validation endpoint inputs from the frozen graph and checkpoint."""
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_prep_20261112"))
from preflight import Model, S, depths, endpoints


def main():
    output = OUT / "aux_driver_v2"
    output.mkdir(exist_ok=True)
    _, arrays, names, views = S.load_snapshot("val")
    selected = {r["view_name"] for r in S.read(P / "lcone_endpoint_frozen_20261112/SELECTION.json")["included"]
                if r["split"] == "val"}
    evidence = {(r["view"], r["cone_id"]): r["status"]
                for r in S.read(P / "lcone_endpoint_frozen_20261112/EVIDENCE.json")["endpoints"]
                if r["split"] == "val"}
    source_file = P / "seed42_supervised_prep_20261109/CONE_CACHE_V2.csv"
    records = defaultdict(list)
    with source_file.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["split"] == "val" and r["view"] in selected and r["kind"] in ("D", "PO") and r["phys_rows"]:
                records[r["view"]].append(r)
    assert {(v, r["cone_id"]) for v, rr in records.items() for r in rr} == evidence.keys()
    virtual_by_view = defaultdict(dict)
    vmap = S.F / "data/derived_v2/bitwise_alias_20261029_v2/virtual_node_map.jsonl"
    with vmap.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["view"] in selected:
                virtual_by_view[r["view"]][r["name"]] = r["global_node"]
    idx, meta, members, ptr = [], [], [], [0]
    for v, rr in sorted(records.items()):
        net = endpoints(S.F / "trans" / f"{v}.v")[0]
        mapping = S.view_rows(views, names, v)
        reverse = {i: n for n, i in mapping.items()}
        for r in sorted(rr, key=lambda x: x["cone_id"]):
            status = evidence[v, r["cone_id"]]
            mem = np.fromstring(r["phys_rows"], dtype=np.int64, sep="|")
            assert np.all(arrays["physical"][mem])
            driver = mapping.get(r["driver"])
            item = dict(view=v, cone_id=r["cone_id"], kind=r["kind"], status=status)
            auxiliary = driver is None and r["driver"] in virtual_by_view[v]
            if auxiliary:
                ordered = sorted(virtual_by_view[v], key=virtual_by_view[v].get)
                assert ordered == net["virtual_names"]
                assert virtual_by_view[v][r["driver"]] in {int(x) for x in r["aux_globals"].split("|") if x}
                driver = views[v]["physical_stop"] + ordered.index(r["driver"])
                assert driver < views[v]["stop"] and not arrays["physical"][driver]
            if driver is None or (not auxiliary and driver not in mem):
                item["feature_available"] = False
                item["reason"] = "driver_without_physical_row"
                meta.append(item)
                continue
            dist = depths(net, r["driver"])
            distance = np.asarray([dist[reverse[g]] for g in mem], dtype=np.int32)
            assert (distance == 0).sum() == (0 if auxiliary else 1)
            members.extend(map(int, mem))
            ptr.append(len(members))
            item.update(feature_available=True, feature_row=len(idx), auxiliary_driver=auxiliary)
            idx.append((mem, distance, driver, r["kind"]))
            meta.append(item)
    in_root = P / "control_boundary_v3_20261104"
    raw = np.load(in_root / "inputs/trans_val/x39.npy")
    edge = np.load(in_root / "inputs/trans_val/edge_index.npy")
    with np.load(in_root / "normalization.npz") as z:
        raw[:, 25:] = np.clip((raw[:, 25:] - z["mean"][25:]) / z["std"][25:], -10, 10)
    assert raw.dtype == np.float32
    x = torch.as_tensor(raw, device="cuda")
    e = torch.as_tensor(edge, device="cuda", dtype=torch.long)
    model = Model().cuda().eval().requires_grad_(False)
    reports = []
    run = P / "seed42_nc_ablation_20261109"
    with np.load(run / "N_scores.npz") as old:
        assert np.array_equal(old["y_val"], arrays["y"])
        assert np.array_equal(old["trust_val"], arrays["trusted"])
        for point in ("best", "last"):
            ckpt = run / f"N_{point}.pt"
            model.load_state_dict(torch.load(ckpt, weights_only=True, map_location="cuda"), strict=True)
            state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            captured = []
            hook = model.classifier.register_forward_pre_hook(lambda _, args: captured.append(args[0].detach()))
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                logits = model(x, e).float()
            hook.remove()
            assert len(captured) == 1
            h = captured.pop().float().cpu().numpy()
            margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
            assert np.isfinite(h).all() and np.isfinite(margin).all()
            previous = old[f"val_{point}"]
            margin_error = float(np.max(np.abs(margin - previous)))
            margin_diff_rows = int(np.count_nonzero(margin != previous))
            # Use the frozen historical margins for A and the common B/C scalars.
            # The new forward supplies only the contextual embeddings.
            assert margin_error <= 0.125 and np.mean(np.abs(margin - previous)) <= 0.005
            margin = previous
            b = np.zeros((len(idx), 268), np.float32)
            c = np.zeros_like(b)
            for i, (mem, dd, drv, kind) in enumerate(idx):
                m = margin[mem]
                stats = [m.max(), np.quantile(m, .9), np.median(m), m.mean(), m.std(),
                         margin[drv], math.log1p(len(mem)), float(kind == "PO")]
                bands = (dd == 0, dd == 1, (dd >= 2) & (dd <= 3), dd >= 4)
                assert np.all(sum(bands) == 1)
                pooled = [h[drv], *[h[mem[mask]].mean(0) if mask.any() else np.zeros(64) for mask in bands[1:]]]
                b[i, :8] = stats
                c[i] = np.concatenate([stats, *pooled, [1.0, *[float(k.any()) for k in bands[1:]]]])
            assert np.isfinite(c).all() and np.array_equal(b[:, :8], c[:, :8])
            assert all(torch.equal(state[k], v) for k, v in model.state_dict().items())
            asset = output / f"VAL_BC_SEED42_N_{point.upper()}.npz"
            with asset.open("xb") as f:
                np.savez_compressed(f, B=b, C=c, members=np.array(members, np.int64), ptr=np.array(ptr, np.int64),
                                    keys=np.array([f"{r['view']}|{r['cone_id']}" for r in meta if r["feature_available"]]))
            reports.append(dict(point=point, checkpoint_sha256=S.sha(ckpt), margin_max_error=margin_error,
                                margin_changed_rows=margin_diff_rows, margin_used="stored_historical",
                                asset_sha256=S.sha(asset)))
            print(point, len(idx), margin_error, flush=True)
    with (output / "VAL_INVENTORY.json").open("x", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    with (output / "VAL_PREFLIGHT.json").open("x", encoding="utf-8") as f:
        json.dump(dict(views=len(records), rankable=len(idx), nonempty=len(meta),
                       status=dict(Counter(("scored_" if r["feature_available"] else "unscored_") + r["status"] for r in meta)),
                       auxiliary_drivers=sum(r.get("auxiliary_driver", False) for r in meta),
                       checkpoints=reports, updates=0), f, indent=2)


if __name__ == "__main__":
    main()
