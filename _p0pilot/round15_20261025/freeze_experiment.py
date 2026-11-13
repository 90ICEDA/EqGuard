"""Freeze the four-arm exploratory comparison plan without training."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T15 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15"
FEAT = T15 / "features"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((T15 / "target18_manifest.json").read_text(
        encoding="utf-8"))
    gm = json.loads((T15 / "group_manifest.json").read_text(encoding="utf-8"))
    base = dict(
        seed=42, fold_mode="lro", lro_splits="ys_aig",
        epochs=30, steps_per_epoch=1, val_every=5,
        norm_fit="train", norm_extra="bounded", dense_prefix=0,
        extra_feats="satrel_node", label_mask="none",
        amp=True, training_allowed=False, device="ginvenv_gpu",
        note=("one held-out recipe split; no test labels read; no L_eq/L_pair; "
              "same support/mask for all extra arms"))
    arms = []
    common = ("train_test2.3.py --work-dir generate_trans/folds/hosts_bt31 "
              "--fold-json generate_trans/folds/hosts_bt31/views.json "
              "--fold-mode lro --lro-splits ys_aig --seed 42 --epochs 30 "
              "--steps-per-epoch 1 --val-every 5 --norm-fit train "
              "--extra-dense-prefix 0 --amp")
    for name, file, extra in (
            ("structure", None, "--extra-feats none"),
            ("structure_mask_zero", "target18_zero.npy",
             "--extra-feats satrel_node --norm-extra bounded --extra-node-file "
             + str(FEAT / "target18_zero.npy")),
            ("structure_real", "target18_real.npy",
             "--extra-feats satrel_node --norm-extra bounded --extra-node-file "
             + str(FEAT / "target18_real.npy")),
            ("structure_permuted", "target18_permuted.npy",
             "--extra-feats satrel_node --norm-extra bounded --extra-node-file "
             + str(FEAT / "target18_permuted.npy"))):
        cmd = f"{common} {extra} --tag {name}"
        arms.append(dict(arm=name, extra_file=file, input_dim=(39 if not file else 58),
                         command=cmd,
                         command_sha256=hashlib.sha256(cmd.encode()).hexdigest()))
    plan = dict(
        created=datetime.now().astimezone().isoformat(timespec="seconds"),
        status="frozen_not_executed", training_approved=False,
        training_runs=0, test_labels_read=False, sat_queries=0,
        seed=42, budget=dict(arms=4, splits=1, epochs=30, steps_per_epoch=1,
                             max_runs=4),
        metrics=["ROC-AUC", "AP", "fixed_fpr_threshold", "val_loss"],
        split_policy=("LRO held-out recipe ys_aig; val only for fixed evaluation/threshold; "
                      "no test labels; train/val permutation separate"),
        fairness=("structure+mask_zero, structure+real, structure+permuted share 39+19 "
                  "inputs and identical masks; structure has 39 inputs; the parameter "
                  "difference is in the first layer (19*hidden), so the functional-content "
                  "comparison is real vs mask_zero/permuted at equal dimensions"),
        no_auxiliary_loss=True,
        target_only=True, support_nodes=manifest["support_nodes"],
        support_train=manifest["support_train"], support_val=manifest["support_val"],
        columns=manifest["columns"], extra_norm_n=18, covered_last=True,
        invalid_permutation_groups=manifest["invalid_permutation_groups"],
        input_hashes=dict(real=sha(FEAT / "target18_real.npy"),
                          permuted=sha(FEAT / "target18_permuted.npy"),
                          zero=sha(FEAT / "target18_zero.npy"),
                          mask=sha(FEAT / "target18_mask.npy"),
                          trans_graph=sha(ROOT / "generate_trans/folds/hosts_bt31/"
                                          "data/processed/trans_graph.pt"),
                          train_script=sha(ROOT / "train_test2.3.py"),
                          config=sha(ROOT / "config.yaml")),
        arms=arms, note="frozen only; do not launch in round15")
    (T15 / "experiment_plan.json").write_text(json.dumps(plan, ensure_ascii=False,
                                                          indent=2), encoding="utf-8")
    pd.DataFrame(arms).to_csv(T15 / "arm_manifest.csv", index=False,
                              encoding="utf-8-sig")
    (T15 / "commands.txt").write_text("\n\n".join(a["command"] for a in arms) + "\n",
                                      encoding="utf-8")
    print(json.dumps(dict(status=plan["status"], arms=len(arms),
                          seed=plan["seed"], budget=plan["budget"],
                          support=plan["support_nodes"],
                          hashes=plan["input_hashes"]), ensure_ascii=False,
                     indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())