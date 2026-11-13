"""f9_gnn_internals.py -- F9: GNN internals (features / per-layer embeddings / scores / ablation)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
T = BASE / "tables"
FIGS = ROOT / "10.15/07_论文图表/figs"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"


def load_cfg() -> dict:
    import yaml
    with open(ROOT / "_devcfg/dual.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def zscore_clamp(x: torch.Tensor) -> torch.Tensor:
    mu = x.mean(0, keepdim=True)
    sd = x.std(0, keepdim=True).clamp_min(1e-6)
    return torch.nan_to_num((x - mu) / sd, nan=0.0, posinf=0.0, neginf=0.0).clamp_(-10.0, 10.0)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", default="s38417t100__injalpha_d1_s42__ys_abc")
    ap.add_argument("--ckpt", type=Path, default=None)
    ap.add_argument("--random-init", action="store_true")
    ap.add_argument("--normalized-input", type=Path, default=None,
                    help="Exact normalized .npy input exported from the checkpoint run; required for trained-model claims")
    ap.add_argument("--model-config", type=Path, default=None,
                    help="Exact YAML model configuration used by the checkpoint run")
    ap.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--max-nodes", type=int, default=120)
    ap.add_argument("--feature-file", default="satrel_node_feats_sat.npy",
                    help="node SAT feature file; use satrel_node_feats_sat_p0clean2.npy for v2")
    ap.add_argument("--csv-tag", default="",
                    help="suffix for F9_*.csv (e.g. _v2) so legacy CSVs are not overwritten")
    ap.add_argument("--out", type=Path, default=FIGS / "F9_gnn_internals.png")
    a = ap.parse_args()

    # Never silently replace a missing checkpoint with random weights or change
    # a trained model's preprocessing to global z-score of sparse SAT columns.
    if not a.random_init:
        if a.ckpt is None or not a.ckpt.is_file():
            ap.error("Provide an existing --ckpt, or explicitly use --random-init for smoke only")
        if a.normalized_input is None or not a.normalized_input.is_file():
            ap.error("Checkpoint analysis requires --normalized-input from that run; legacy global z-score is not valid")
        if a.model_config is None or not a.model_config.is_file():
            ap.error("Checkpoint analysis requires the run's --model-config")

    if a.model_config is not None:
        import yaml
        cfg = yaml.safe_load(a.model_config.read_text(encoding="utf-8"))
    else:
        cfg = load_cfg()
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    fid = json.load(open(WORK / "data/for_train/metadata_trans.json", encoding="utf-8"))["file_ids"]
    sf = PT / a.feature_file
    sat = torch.from_numpy(np.load(sf)).float() if sf.exists() else None
    x = torch.cat([d.x.float(), sat], 1) if sat is not None else d.x.float()
    if a.normalized_input is not None:
        exact = np.load(a.normalized_input, mmap_mode="r")
        if exact.shape != tuple(x.shape) or not np.isfinite(exact).all():
            raise SystemExit("Normalized input shape/finite check failed; verify feature schema and checkpoint run")
        x = torch.from_numpy(np.array(exact, dtype=np.float32, copy=True))
    else:
        x = zscore_clamp(x)  # explicit random-init smoke only
    edge_index, y = d.edge_index, d.y.numpy().astype(int)
    print(f"[in] nodes={x.size(0)} dims={x.size(1)} view={a.view}")

    sys.path.insert(0, str(ROOT))
    import importlib.util
    _spec = importlib.util.spec_from_file_location("t23", ROOT / "train_test2.3.py")
    T23 = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(T23)                     # 只执行模块级定义 ✓（main 有 guard ✓）

    # ⚠️ 先算出该视图的节点下标 ✓ → hook 里**只存这几十个节点** ✓（否则 3.2M×d 的拷贝会 OOM ✗）
    idx = np.where(np.asarray(fid) == a.view)[0]
    if len(idx) == 0:
        raise SystemExit(f"[ERROR] view not found {a.view}")
    idx = idx[: a.max_nodes]
    lab = y[idx]
    idx_t = torch.as_tensor(idx, dtype=torch.long, device=a.device)

    model = T23.build_model(cfg, int(x.size(1)), a.device)
    if a.ckpt and a.ckpt.exists() and not a.random_init:
        sd = torch.load(a.ckpt, map_location=a.device)
        model.load_state_dict(sd["state_dict"] if "state_dict" in sd else sd, strict=True)
        print(f"[ckpt] {a.ckpt}")
    else:
        print("[WARN] no checkpoint -> random init (script smoke only)")
    model.eval()

    x_dev, ei = x.to(a.device), edge_index.to(a.device)
    feats: dict[str, torch.Tensor] = {}

    def mk(name):
        def hook(_m, _inp, out):
            if torch.is_tensor(out) and out.dim() == 2 and out.size(0) == x.size(0):
                feats[name] = out.detach()[idx_t].float().cpu()      # 只存视图内节点 ✓
        return hook

    handles = [m.register_forward_hook(mk(n)) for n, m in model.named_modules()]
    with torch.no_grad():
        logits = model(x_dev, ei)
        p1 = F.softmax(logits.float(), dim=1)[:, 1].cpu().numpy()
    for h in handles:
        h.remove()
    print(f"[hook] captured {len(feats)} layers (view subset only)")

    cand = [(n, t) for n, t in feats.items() if t.size(1) >= 8]
    cand.sort(key=lambda kv: (kv[1].size(1), kv[0]))

    def pick_branch(key: str):
        c = [(n, t) for n, t in cand if key in n]
        c.sort(key=lambda kv: (kv[1].size(1), kv[0]))
        return c[-2:]

    picked = pick_branch("enc_s") + pick_branch("enc_f")
    if not picked:
        picked = cand[-3:]
    print("[layers]", [f"{n}({t.size(1)})" for n, t in picked])

    rows = []
    for n, t in picked:
        emb = t.numpy()
        emb = emb - emb.mean(0, keepdims=True)
        u, s, _vt = np.linalg.svd(emb, full_matrices=False)
        pc = u[:, :2] * s[:2]
        for j, i in enumerate(idx):
            rows.append(dict(view=a.view, node=int(i), layer=n, dim=int(t.size(1)),
                             pc1=float(pc[j, 0]), pc2=float(pc[j, 1]),
                             label=int(lab[j]), score=float(p1[i])))
    pd.DataFrame(rows).to_csv(T / f"F9_embeddings{a.csv_tag}.csv", index=False, encoding="utf-8-sig")
    np.savetxt(T / f"F9_features{a.csv_tag}.csv", x[idx].numpy(), delimiter=",",
               header=",".join(f"f{k}" for k in range(x.size(1))), comments="")

    abl = []
    if sat is not None:
        base_dim = x.size(1) - sat.size(1)
        x2 = x.clone()
        x2[:, base_dim:] = 0.0
        with torch.no_grad():
            p2 = F.softmax(model(x2.to(a.device), ei).float(), dim=1)[:, 1].cpu().numpy()
        for i in idx:
            abl.append(dict(view=a.view, node=int(i), label=int(y[i]),
                            score=float(p1[i]), score_no_sat=float(p2[i]),
                            delta=float(p1[i] - p2[i])))
        pd.DataFrame(abl).to_csv(T / f"F9_ablation{a.csv_tag}.csv", index=False, encoding="utf-8-sig")
        print(f"[out] {T / f'F9_ablation{a.csv_tag}.csv'} ({len(abl)} rows)")

    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    im = ax[0, 0].imshow(x[idx].numpy().T, aspect="auto", cmap="RdBu_r", vmin=-4, vmax=4)
    ax[0, 0].set_title(f"input features ({x.size(1)} dims)", fontsize=8)
    plt.colorbar(im, ax=ax[0, 0], fraction=0.03)
    for n, _t in picked:
        sub = [r for r in rows if r["layer"] == n]
        ax[0, 1].scatter([r["pc1"] for r in sub], [r["pc2"] for r in sub],
                         c=["#d62728" if r["label"] == 1 else "#1f77b4" for r in sub],
                         s=12, alpha=0.8, label=n)
    ax[0, 1].set_title("per-layer embedding (PCA2)", fontsize=8)
    ax[0, 1].legend(fontsize=6)
    ax[1, 0].hist([p1[idx][lab == 0], p1[idx][lab == 1]], bins=25, stacked=True,
                  color=["#1f77b4", "#d62728"], label=["normal", "trojan"])
    ax[1, 0].set_title("node risk score", fontsize=8)
    ax[1, 0].legend(fontsize=6)
    if abl:
        ax[1, 1].hist([r["delta"] for r in abl], bins=25, color="#555")
        ax[1, 1].axvline(0, color="k", lw=0.6)
        ax[1, 1].set_title("delta score after zeroing SAT dims", fontsize=8)
    else:
        ax[1, 1].axis("off")
    fig.suptitle(f"F9 . GNN internals . {a.view}", fontsize=9)
    FIGS.mkdir(parents=True, exist_ok=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=200, bbox_inches="tight")
    print(f"[out] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

