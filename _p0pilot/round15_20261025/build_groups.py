"""Build target-only group matrices and freeze comparison inputs (no training)."""
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
import torch

ROOT = Path(_eqguard_path(''))
T15 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15"
FEAT = T15 / "features"
G = T15 / "groups"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    G.mkdir(parents=True, exist_ok=True)
    real = np.load(FEAT / "target18_real.npy", mmap_mode="r")
    perm = np.load(FEAT / "target18_permuted.npy", mmap_mode="r")
    mask = np.load(FEAT / "target18_mask.npy")
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    base = g.x.numpy()
    N = int(g.y.size(0))
    ids = np.where(mask)[0]
    zero = np.lib.format.open_memmap(FEAT / "target18_zero.npy", mode="w+",
                                     dtype=np.float32, shape=(N, 19))
    zero[ids, :18] = 0.0
    zero[ids, 18] = 1.0
    zero.flush()
    groups = {}
    for name, arr in (("structure", base[ids]),
                      ("structure_mask_zero", np.concatenate(
                          [base[ids], np.asarray(zero[ids])], axis=1)),
                      ("structure_real", np.concatenate(
                          [base[ids], np.asarray(real[ids])], axis=1)),
                      ("structure_permuted", np.concatenate(
                          [base[ids], np.asarray(perm[ids])], axis=1))):
        p = G / f"{name}.npy"
        np.save(p, np.asarray(arr, dtype=np.float32))
        groups[name] = dict(path=str(p.relative_to(ROOT)), shape=list(arr.shape),
                            sha256=sha(p))
    info = dict(
        support_nodes=int(mask.sum()), support_train=int(g.train_mask[
            torch.tensor(ids)].sum()), support_val=int(g.val_mask[
                torch.tensor(ids)].sum()),
        columns=19, extra_norm_n=18, last_column="covered",
        groups=groups,
        parameter_control=("structure+mask_zero, structure+real and structure+permuted "
                           "all have 39+19 inputs; structure is 39 inputs. The first-layer "
                           "parameter difference is 19*hidden, so the fair functional-content "
                           "comparison is real vs mask_zero/permuted at identical dimensions."),
        changed_nodes=int(np.any(np.asarray(real[ids]) != np.asarray(perm[ids]), axis=1).sum()),
        changed_columns=[j for j in range(19) if np.any(np.asarray(real[ids, j]) !=
                                                         np.asarray(perm[ids, j]))],
        mask_unchanged=bool(np.array_equal(np.asarray(real[ids, 18]),
                                          np.asarray(perm[ids, 18]))),
        zero_content=bool(np.asarray(zero[ids, :18]).max() == 0),
        hashes=dict(real=sha(FEAT / "target18_real.npy"),
                    permuted=sha(FEAT / "target18_permuted.npy"),
                    zero=sha(FEAT / "target18_zero.npy"),
                    mask=sha(FEAT / "target18_mask.npy"),
                    trans_graph=sha(PT / "trans_graph.pt")))
    (T15 / "group_manifest.json").write_text(json.dumps(info, ensure_ascii=False,
                                                         indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())