"""Freeze round-16 bounded smoke commands (10 updates/arm, val-only)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

ROOT = Path(_eqguard_path(''))
T15 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15"
T16 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round16"
FEAT = T15 / "features"
OUT = ROOT / "results_smoke_r16" / "formal"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    T16.mkdir(parents=True, exist_ok=True)
    common = ("--work-dir generate_trans/folds/hosts_bt31 "
              "--fold-json generate_trans/folds/hosts_bt31/views.json "
              "--config config_smoke_r16.yaml --fold-mode fold --view-policy all "
              "--view-budget 1 --seed 42 --epochs 10 --steps-per-epoch 1 "
              "--val-every 5 --norm-fit train --extra-dense-prefix 0 --amp "
              "--smoke-val-only --smoke-fixed-rng --save-ckpt")
    arms = []
    for name, file, tag in (
            ("structure_mask_zero", "target18_zero.npy", "zro0"),
            ("structure_real", "target18_real.npy", "rel0"),
            ("structure_permuted", "target18_permuted.npy", "prm0")):
        cmd = (f"train_test2.3.py {common} --extra-feats satrel_node "
               f"--norm-extra bounded --extra-node-file {FEAT / file} "
               f"--smoke-final-ckpt {OUT / name / 'final.pt'} "
               f"--out-root {OUT} --tag {tag}")
        arms.append(dict(arm=name, tag=tag, extra_file=str(FEAT / file),
                         updates=10, command=cmd,
                         command_sha256=hashlib.sha256(cmd.encode()).hexdigest()))
    plan = dict(
        created="2026-10-26T00:50:00+08:00", status="frozen_not_executed",
        protocol="fixed fold train/val; val-only; no test evaluation",
        seed=42, updates_per_arm=10, arms=3, structure_arm="deferred",
        preflight=dict(updates=1, step_sec=53.2, peak_vram_mb=9878.7,
                       init_sha="f8dee9538ea1653cc34c09489803d77a10f96ed3cf6fedbeea29bbb3d474b88a",
                       extra_train_support=18, extra_val_support=4,
                       extra_dim=19, extra_norm_n=18),
        estimated=dict(updates_total=30, update_sec=53.2, gpu_min=26.6,
                       startup_and_val_margin_min=8, total_min=34.6,
                       within_45min=True),
        metrics=["val_AP_trans", "val_AP_orig", "fixed_fpr_threshold", "loss"],
        input_hashes=dict(real=sha(FEAT / "target18_real.npy"),
                          permuted=sha(FEAT / "target18_permuted.npy"),
                          zero=sha(FEAT / "target18_zero.npy"),
                          mask=sha(FEAT / "target18_mask.npy"),
                          config=sha(ROOT / "config_smoke_r16.yaml"),
                          train_script=sha(ROOT / "train_test2.3.py")),
        arms_detail=arms,
        no_auxiliary_losses=True, training_approved=False, test_labels_read=False)
    (T16 / "smoke_plan.json").write_text(json.dumps(plan, ensure_ascii=False,
                                                     indent=2), encoding="utf-8")
    (T16 / "commands.txt").write_text("\n\n".join(a["command"] for a in arms) + "\n",
                                      encoding="utf-8")
    print(json.dumps(dict(status=plan["status"], arms=len(arms),
                          updates=plan["updates_per_arm"],
                          estimated=plan["estimated"],
                          preflight=plan["preflight"]), ensure_ascii=False,
                     indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())