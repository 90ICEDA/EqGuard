"""Assemble round-16 val-only smoke results (no test evaluation)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T16 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round16"
RES = ROOT / "results_smoke_r16"
ARMS = [
    ("structure_mask_zero", "zro0"),
    ("structure_real", "rel0"),
    ("structure_permuted", "prm0"),
    ("structure_mask_zero_repeat", "zro1"),
]


def main() -> int:
    ev = pd.read_json(RES / "val_metrics.json")
    rows = []
    for arm, tag in ARMS:
        d = RES / "formal" / f"hosts_bt31_seed42mode2_allb1_fold_{tag}"
        s = json.loads((d / "smoke_val_summary.json").read_text(encoding="utf-8"))
        log = pd.read_csv(d / "train_log.csv", encoding="utf-8-sig")
        best = ev[(ev.arm == arm) & (ev.checkpoint == "best")].iloc[0]
        final = ev[(ev.arm == arm) & (ev.checkpoint == "final")].iloc[0]
        ck = RES / "formal" / arm / "final.pt"
        rows.append(dict(
            arm=arm, tag=tag, updates=int(s["updates"]),
            best_val_AP=float(s["best_val_AP"]),
            final_val_AP_t=float(s["final_val_AP_t"]),
            threshold=float(s["final_threshold"]),
            val_ROC_AUC_best=float(best.ROC_AUC),
            val_ROC_AUC_final=float(final.ROC_AUC),
            TP=int(best.TP), FP=int(best.FP), FN=int(best.FN), TN=int(best.TN),
            precision=best.precision, recall=float(best.recall), FPR=float(best.FPR),
            val_n=int(best.n), val_positives=int(best.positives),
            last_loss=float(log.loss.iloc[-1]),
            grad_norm_last=float(log.grad_norm.iloc[-1]),
            grad_finite_all=int(log.grad_finite.min()),
            wall_s=float(s["wall_s"]), peak_vram_mb=float(s["peak_vram_mb"]),
            init_sha=s["init_sha"], base_x_sha=s["base_x_sha"],
            extra_sha=s["extra_sha"], train_mask_sha=s["train_mask_sha"],
            val_mask_sha=s["val_mask_sha"], extra_mask_sha=s["extra_mask_sha"],
            extra_train_support=int(s["extra_train_support"]),
            extra_val_support=int(s["extra_val_support"]),
            final_ckpt_sha=hashlib.sha256(ck.read_bytes()).hexdigest(),
            test_evaluated=bool(s["test_evaluated"]),
            model_init_same=bool(s["init_sha"] == rows[0]["init_sha"]) if rows else True,
            base_same=bool(s["base_x_sha"] == rows[0]["base_x_sha"]) if rows else True,
            masks_same=bool((s["train_mask_sha"], s["val_mask_sha"], s["extra_mask_sha"])
                            == (rows[0]["train_mask_sha"], rows[0]["val_mask_sha"],
                                rows[0]["extra_mask_sha"])) if rows else True,
        ))
    df = pd.DataFrame(rows)
    zero = df[df.arm == "structure_mask_zero"].iloc[0]
    rep = df[df.arm == "structure_mask_zero_repeat"].iloc[0]
    real = df[df.arm == "structure_real"].iloc[0]
    perm = df[df.arm == "structure_permuted"].iloc[0]
    comparisons = {
        "real_minus_mask_zero_AP": float(real.best_val_AP - zero.best_val_AP),
        "permuted_minus_mask_zero_AP": float(perm.best_val_AP - zero.best_val_AP),
        "real_minus_permuted_AP": float(real.best_val_AP - perm.best_val_AP),
        "same_input_repeat_minus_zero_AP": float(rep.best_val_AP - zero.best_val_AP),
        "val_prevalence": float(zero.val_positives / zero.val_n),
    }
    df.to_csv(T16 / "r16_results.csv", index=False, encoding="utf-8-sig")
    out = dict(
        round=16, protocol="fixed fold train/val; val-only smoke; no test evaluation",
        status="completed_exploratory_smoke",
        updates_per_arm=10, arms_run=3, repeat_runs=1,
        structure_arm="deferred", seeds=[42], optimizer="Adam",
        train_views=259, val_views=65, test_views_loaded_but_not_evaluated=64,
        target_support=dict(train=18, val=4, unique=22),
        changed_nodes=6, changed_columns=12, val_changed_nodes=0,
        loss_config=dict(train_mode=2, lambda_const=0.0, lambda_det=0.0,
                         lambda_nor=0.0, lambda_pos=0.0, eq_loss=0.0,
                         pair_loss=0.0, region_loss=0.0),
        comparisons=comparisons, rows=rows,
        notes=[
            "All three 58-dim arms used the same init hash, masks, optimizer and 10-update budget.",
            "No structure(39) arm was run; structure comparison is deferred, not claimed.",
            "Same-input repeat quantifies GPU/bfloat16 numerical noise.",
            "AP is training-time val AP; ROC-AUC is a read-only re-evaluation from the saved "
            "checkpoint on the same fixed val split and matched normalized-base hash.",
            "At the calibrated threshold no val node was predicted positive; recall=0, FPR=0.",
            "Val has only 4 target-support nodes; this is not 89 functional samples.",
        ])
    (T16 / "r16_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    print(df.to_string(index=False), flush=True)
    print(json.dumps(comparisons, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())