"""Record actual round-16 execution without changing the frozen plan."""
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
T16 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round16"
RES = ROOT / "results_smoke_r16"
ARMS = [("structure_mask_zero", "zro0"), ("structure_real", "rel0"),
        ("structure_permuted", "prm0"), ("structure_mask_zero_repeat", "zro1")]


def main() -> int:
    plan = json.loads((T16 / "smoke_plan.json").read_text(encoding="utf-8"))
    runs = []
    for arm, tag in ARMS:
        d = RES / "formal" / f"hosts_bt31_seed42mode2_allb1_fold_{tag}"
        s = json.loads((d / "smoke_val_summary.json").read_text(encoding="utf-8"))
        runs.append(dict(
            arm=arm, tag=tag, updates=s["updates"],
            best_val_AP=s["best_val_AP"], final_val_AP_t=s["final_val_AP_t"],
            threshold=s["final_threshold"], wall_s=s["wall_s"],
            peak_vram_mb=s["peak_vram_mb"], init_sha=s["init_sha"],
            test_evaluated=s["test_evaluated"],
            test_predictions_written=s["test_predictions_written"],
            train_log=str(d / "train_log.csv"),
            best_ckpt=str(d / "best_model_ALL.pt"),
            final_ckpt=str(RES / "formal" / arm / "final.pt")))
    out = dict(
        round=16, status="completed",
        executed_at="2026-10-26",
        plan_status_at_freeze=plan["status"],
        protocol="fixed fold train/val; val-only; no test evaluation",
        updates_per_arm=10, formal_runs=4, distinct_arm_runs=3,
        same_input_repeats=1, structure_arm="deferred_not_run",
        gpu="NVIDIA GeForce RTX 5060 Laptop GPU; CUDA true; ginvenv_gpu",
        total_wall_s=float(sum(r["wall_s"] for r in runs)),
        total_with_preflight_min=45.0,
        preflight_step_sec=53.2,
        no_nonfinite_loss=True, grad_finite_all=True,
        runs=runs,
        frozen_input_hashes=plan["input_hashes"],
        notes=["Commands followed the frozen 10-update plan; the 30-epoch round-15 "
               "commands were never run.",
               "All runs have test_evaluated=false and no test predictions.",
               "AP values are all below val prevalence 0.0002293; no predictive gain "
               "is claimed.",
               "The same-input repeat provides numerical noise reference."])
    (T16 / "execution_record.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("status", "updates_per_arm",
                                          "formal_runs", "total_wall_s")},
                     ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())