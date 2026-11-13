"""Real tensor preflight and negative checks for target-only SAT features."""
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
T15 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15"
FEAT = T15 / "features"
G = T15 / "groups"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def require_index(idx, n):
    if not isinstance(idx, (int, np.integer)) or idx < 0 or idx >= n:
        raise ValueError("bad node index")
    return int(idx)


def require_pin(pin):
    if pin not in ("Q", "QN", "Y", "IN", "IN1", "IN2", "IN3", "IN4", "IN5", "IN6"):
        raise ValueError("bad output pin")
    return pin


def require_pi(anchor, valid):
    if not valid or anchor is None or str(anchor).strip().lower() in ("", "nan"):
        raise ValueError("unbound PI anchor")
    return str(anchor)


def require_dim(x, dim=19):
    if x.ndim != 2 or x.shape[1] != dim:
        raise ValueError("wrong feature dimension")
    return x.shape


def require_same_role(perm_map, roles):
    for dst, src in perm_map.items():
        if roles.get(dst) != roles.get(src):
            raise ValueError("cross-split permutation")
    return True


def main() -> int:
    contract = json.loads((T15 / "signal_contract_manifest.json").read_text(
        encoding="utf-8"))
    cval = json.loads((T15 / "signal_contract_validation.json").read_text(
        encoding="utf-8"))
    tman = json.loads((T15 / "target18_manifest.json").read_text(
        encoding="utf-8"))
    gman = json.loads((T15 / "group_manifest.json").read_text(encoding="utf-8"))
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    N = int(g.y.size(0))
    real = np.load(FEAT / "target18_real.npy", mmap_mode="r")
    perm = np.load(FEAT / "target18_permuted.npy", mmap_mode="r")
    zero = np.load(FEAT / "target18_zero.npy", mmap_mode="r")
    mask = np.load(FEAT / "target18_mask.npy")
    support = [r for r in contract if r["target"]]
    target_nodes = sorted({int(r["target"][s]["node_index"])
                           for r in support for s in ("source", "partner")
                           if r["target"][s]["node_index"] is not None})
    target_roles = {n: ("train" if bool(g.train_mask[n]) else
                        "val" if bool(g.val_mask[n]) else "other") for n in target_nodes}
    checks = []
    def check(name, ok, detail=""):
        checks.append(dict(check=name, ok=int(bool(ok)), detail=str(detail)))

    check("target_support_matches_mask", target_nodes == sorted(np.where(mask)[0].tolist()),
          f"{len(target_nodes)} vs {int(mask.sum())}")
    check("target_count_22", len(target_nodes) == 22, len(target_nodes))
    check("target_train18_val4",
          sum(v == "train" for v in target_roles.values()) == 18
          and sum(v == "val" for v in target_roles.values()) == 4,
          pd.Series(target_roles.values()).value_counts().to_dict())
    check("feature_dim_19", require_dim(real) == (N, 19), real.shape)
    check("perm_dim_19", require_dim(perm) == (N, 19), perm.shape)
    check("zero_dim_19", require_dim(zero) == (N, 19), zero.shape)
    check("mask_binary_last", set(np.unique(real[:, 18]).tolist()) <= {0.0, 1.0}
          and set(np.unique(perm[:, 18]).tolist()) <= {0.0, 1.0})
    check("covered_matches_mask",
          np.array_equal(np.asarray(real[:, 18] > 0), mask)
          and np.array_equal(np.asarray(perm[:, 18] > 0), mask))
    finite, lo, hi = True, 1.0, 0.0
    for s in range(0, N, 200000):
        a = np.asarray(real[s:s + 200000]); b = np.asarray(perm[s:s + 200000])
        finite &= bool(np.isfinite(a).all() and np.isfinite(b).all())
        lo = min(lo, float(a.min()), float(b.min()))
        hi = max(hi, float(a.max()), float(b.max()))
    check("finite", finite)
    check("bounded_0_1", lo >= 0 and hi <= 1, f"{lo}/{hi}")
    check("zero_content", float(np.asarray(zero[np.where(mask)[0], :18]).max()) == 0)
    check("groups_shape",
          all(np.load(G / f"{x}.npy").shape in ((22, 39), (22, 58))
              for x in ("structure", "structure_mask_zero",
                        "structure_real", "structure_permuted")))
    check("mask_unchanged", bool(gman["mask_unchanged"]))
    check("changed_nodes_6", gman["changed_nodes"] == 6, gman["changed_nodes"])
    val_nodes = [n for n in target_nodes if target_roles[n] == "val"]
    check("val_permutation_unchanged",
          np.array_equal(np.asarray(real[val_nodes]), np.asarray(perm[val_nodes])))
    check("pi_anchor_8_bound", cval["pi_anchor_records"] == 8
          and cval["pi_unbound"] == 0, cval["pi_examples"])
    check("qn_groups_6_separate", len(cval["qn_duplicate_groups"]) == 6
          and cval["q_pin_records"] == 38 and cval["qn_pin_records"] == 33)
    check("target_conflicts_none", len(cval["target_conflicts"]) == 0,
          cval["target_conflicts"])
    check("raw_hashes", bool(cval["raw_sha_ok"] and cval["view_hash_ok"]))
    check("input_hashes",
          sha(FEAT / "target18_real.npy") == tman["real_sha256"]
          and sha(FEAT / "target18_permuted.npy") == tman["permuted_sha256"]
          and sha(FEAT / "target18_mask.npy") == tman["mask_sha256"])
    src = (ROOT / "train_test2.3.py").read_text(encoding="utf-8", errors="replace")
    check("loader_bounded_no_zscore",
          "--norm-extra" in src and "bounded" in src
          and "C.size(1) - 1" in src and "C[:, -1] > 0" in src)
    check("loader_extra_node_file", "--extra-node-file" in src)
    check("split_isolation",
          not (set(n for n in target_nodes if target_roles[n] == "train")
               & set(n for n in target_nodes if target_roles[n] == "val")))

    neg = []
    def reject(name, fn):
        try:
            fn()
            neg.append(dict(test=name, rejected=0))
        except Exception:
            neg.append(dict(test=name, rejected=1))
    reject("negative_index", lambda: require_index(-1, N))
    reject("bad_pin", lambda: require_pin("BAD"))
    reject("nan_pi", lambda: require_pi("nan", False))
    reject("wrong_dim", lambda: require_dim(np.zeros((N, 18))))
    reject("cross_split_perm", lambda: require_same_role(
        {"train_rel": "val_rel"}, {"train_rel": "train", "val_rel": "val"}))
    check("negative_tests_5", sum(x["rejected"] for x in neg) == 5, neg)
    pd.DataFrame(checks).to_csv(T15 / "preflight_checks.csv", index=False,
                                encoding="utf-8-sig")
    pd.DataFrame(neg).to_csv(T15 / "negative_tests.csv", index=False,
                             encoding="utf-8-sig")
    report = dict(checks=len(checks), passed=int(sum(c["ok"] for c in checks)),
                  failed=int(sum(1 - c["ok"] for c in checks)),
                  negative_rejected=int(sum(x["rejected"] for x in neg)),
                  support_nodes=len(target_nodes),
                  support_train=sum(v == "train" for v in target_roles.values()),
                  support_val=sum(v == "val" for v in target_roles.values()),
                  changed_nodes=gman["changed_nodes"],
                  changed_columns=gman["changed_columns"],
                  val_changed_nodes=0,
                  training_initialized=False, training_run=False,
                  note=("real tensor reads; target-only attachment; cut coords are "
                        "not node features; no SAT/training"))
    (T15 / "preflight_report.json").write_text(json.dumps(report, ensure_ascii=False,
                                                           indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print(pd.DataFrame(checks).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())