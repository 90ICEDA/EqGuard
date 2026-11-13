"""Build target-only 18-d SAT features with relation-level permutation."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
T14 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round14"
T15 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
FEAT = T15 / "features"
sys_path = None
import sys
sys.path.insert(0, str(ROOT / "_p0pilot/round9_20261025"))
from boundary_repr import COLS  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    FEAT.mkdir(parents=True, exist_ok=True)
    contract = json.loads((T15 / "signal_contract_manifest.json").read_text(
        encoding="utf-8"))
    meta = pd.read_csv(T14 / "relation_metadata_40.csv", encoding="utf-8-sig")
    meta["host"] = meta.source_view.str.split("__").str[0]
    meta = meta.set_index("relation_id")
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    N = int(g.y.size(0))
    cols = list(COLS) + ["covered"]
    assert len(cols) == 19
    real = np.lib.format.open_memmap(FEAT / "target18_real.npy", mode="w+",
                                     dtype=np.float32, shape=(N, 19))
    perm = np.lib.format.open_memmap(FEAT / "target18_permuted.npy", mode="w+",
                                     dtype=np.float32, shape=(N, 19))
    mask = np.zeros(N, dtype=bool)
    support_rows = []
    by_rel = {}
    for r in contract:
        rid = r["relation_id"]
        f = np.asarray(r["feature_18d"]["source"], dtype=np.float32)
        assert f.shape == (18,)
        nodes = sorted({r["target"][s]["node_index"] for s in ("source", "partner")
                        if r["target"][s]["node_index"] is not None})
        by_rel[rid] = dict(feature=f, nodes=nodes,
                           role=r["role"], host=meta.loc[rid, "host"],
                           kind=meta.loc[rid, "kind"])
        for n in nodes:
            mask[n] = True
        support_rows.append(dict(relation_id=rid, role=r["role"],
                                 host=meta.loc[rid, "host"],
                                 kind=meta.loc[rid, "kind"],
                                 target_nodes=";".join(map(str, nodes)),
                                 target_count=len(nodes)))
    for rid, x in by_rel.items():
        real[x["nodes"], :18] = x["feature"][None, :]
        real[x["nodes"], 18] = 1.0
    # Relation-level permutation within role+host+target-kind strata only.
    rng = np.random.default_rng(20261025)
    perm_map = {}
    invalid = []
    groups = {}
    for rid, x in by_rel.items():
        groups.setdefault((x["role"], x["host"], x["kind"]), []).append(rid)
    for key, ids in groups.items():
        if len(ids) < 2:
            invalid.append(dict(stratum=str(key), relations=len(ids),
                                reason="singleton_no_valid_permutation"))
            for rid in ids:
                perm_map[rid] = rid
            continue
        order = rng.permutation(len(ids))
        if np.array_equal(order, np.arange(len(ids))):
            order = np.roll(order, 1)
        for dst, src in zip(ids, [ids[i] for i in order]):
            perm_map[dst] = src
    for rid, src in perm_map.items():
        x, y = by_rel[rid], by_rel[src]
        perm[x["nodes"], :18] = y["feature"][None, :]
        perm[x["nodes"], 18] = 1.0
    real.flush(); perm.flush()
    np.save(FEAT / "target18_mask.npy", mask)
    pd.DataFrame(support_rows).to_csv(T15 / "target18_support.csv", index=False,
                                      encoding="utf-8-sig")
    pd.DataFrame([dict(relation_id=k, permuted_from=v,
                       changed=int(k != v)) for k, v in perm_map.items()]).to_csv(
        T15 / "target18_permutation.csv", index=False, encoding="utf-8-sig")
    changed_nodes = sorted(set(np.where(np.any(real != perm, axis=1))[0].tolist()))
    changed_cols = [cols[j] for j in range(19)
                    if np.any(np.asarray(real[:, j]) != np.asarray(perm[:, j]))]
    info = dict(
        n=N, columns=cols, extra_norm_n=18, covered_last=True,
        support_nodes=int(mask.sum()),
        support_train=int(g.train_mask[torch.tensor(np.where(mask)[0])].sum()),
        support_val=int(g.val_mask[torch.tensor(np.where(mask)[0])].sum()),
        support_role_counts=pd.Series([("train" if bool(g.train_mask[n]) else
                                        "val" if bool(g.val_mask[n]) else "other")
                                       for n in np.where(mask)[0]]).value_counts().to_dict(),
        real_sha256=sha(FEAT / "target18_real.npy"),
        permuted_sha256=sha(FEAT / "target18_permuted.npy"),
        mask_sha256=sha(FEAT / "target18_mask.npy"),
        changed_nodes=len(changed_nodes), changed_node_indices=changed_nodes,
        changed_columns=changed_cols,
        permutation_groups={str(k): len(v) for k, v in groups.items()},
        invalid_permutation_groups=invalid,
        same_support_and_mask=int(np.array_equal(real[:, 18], perm[:, 18])),
        note=("target-only attachment; cut coordinates are not nodes; permutation is "
              "relation-level and both sides use the same permuted record"))
    (T15 / "target18_manifest.json").write_text(json.dumps(info, ensure_ascii=False,
                                                           indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())