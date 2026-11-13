"""Read-only val metrics for the three smoke arms (no training/test)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(_eqguard_path(''))
T15 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15"
FEAT = T15 / "features"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
import sys
sys.path.insert(0, str(ROOT))
from models.gin_net import GINNodeClassifier  # noqa: E402


def metrics(probs, labels, thr):
    p = probs[:, 1].cpu().numpy()
    y = labels.cpu().numpy()
    out = dict(n=int(len(y)), positives=int(y.sum()),
               AP=float(average_precision_score(y, p)) if 0 < y.sum() < len(y) else None,
               ROC_AUC=float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else None,
               threshold=float(thr))
    pred = p >= thr
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    out.update(TP=tp, FP=fp, FN=fn, TN=tn,
               precision=(tp / (tp + fp) if tp + fp else None),
               recall=(tp / (tp + fn) if tp + fn else None),
               FPR=(fp / (fp + tn) if fp + tn else None))
    return out


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config_smoke_r16.yaml").read_text(encoding="utf-8"))
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False)
    base = g.x.float().to(device)[:, :39]
    train_mask = g.train_mask.to(device)
    val_mask = g.val_mask.to(device)
    mu = base[train_mask].mean(0, keepdim=True)
    sd = base[train_mask].std(0, keepdim=True).clamp_min(1e-6)
    base_norm = torch.nan_to_num((base - mu) / sd, nan=0.0, posinf=0.0,
                                 neginf=0.0).clamp_(-10.0, 10.0)
    print("[EVAL] device", device, "normalized base sha",
          __import__("hashlib").sha256(__import__("numpy").ascontiguousarray(
              base_norm.detach().cpu().numpy()).tobytes()).hexdigest(), flush=True)
    rows = []
    for arm, extra_file in (("structure_mask_zero", "target18_zero.npy"),
                            ("structure_real", "target18_real.npy"),
                            ("structure_permuted", "target18_permuted.npy"),
                            ("structure_mask_zero_repeat", "target18_zero.npy")):
        extra = torch.from_numpy(np.load(FEAT / extra_file)).float().to(device)
        x = torch.cat([base_norm, extra], dim=1)
        y_all = g.y.to(device)
        edge_index = g.edge_index.to(device)
        d = str(ROOT / "results_smoke_r16/formal" /
                ("hosts_bt31_seed42mode2_allb1_fold_" +
                 {"structure_mask_zero": "zro0", "structure_real": "rel0",
                  "structure_permuted": "prm0",
                  "structure_mask_zero_repeat": "zro1"}[arm]))
        summ = json.loads((Path(d) / "smoke_val_summary.json").read_text(encoding="utf-8"))
        for kind, path in (("best", Path(d) / "best_model_ALL.pt"),
                           ("final", ROOT / "results_smoke_r16/formal" / arm / "final.pt")):
            ck = torch.load(path, map_location="cpu", weights_only=False)
            model = GINNodeClassifier(in_channels=58,
                                      hidden_channels=int(cfg["model"]["hidden_channels"]),
                                      out_channels=int(cfg["model"]["out_channels"]),
                                      num_layers=int(cfg["model"]["num_layers"])).to(device)
            model.load_state_dict(ck["state_dict"])
            model.eval()
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16,
                                                 enabled=device.type == "cuda"):
                logits = model(x, edge_index)
            thr = float(summ["final_threshold"] if kind == "final"
                        else ck.get("threshold", summ["final_threshold"]))
            m = metrics(logits[val_mask].float(), y_all[val_mask], thr)
            m.update(arm=arm, checkpoint=kind, checkpoint_sha=__import__("hashlib").sha256(
                path.read_bytes()).hexdigest())
            rows.append(m)
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "results_smoke_r16/val_metrics.csv", index=False,
               encoding="utf-8-sig")
    (ROOT / "results_smoke_r16/val_metrics.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out.to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())