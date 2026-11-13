"""fghtl_stability_832.py -- 832 个正-正 SAT 对齐对的跨实现稳定性。

输入：
  C v2 seed42 ckpt + satrel_node_feats_sat_p0clean2.npy（12 维）
  legacy C v1 clean ckpt + satrel_node_feats_sat.npy（9 维，对照）
  satrel_node_pairs_labelclean.npz（kind0 且 y[a]=y[b]=1 → 832 对）
输出：
  tables/FGHTL_stability_832_pairs.csv
  tables/FGHTL_stability_832_summary.csv
指标：
  within-pair score std/mean、两两 recipe Spearman、top-5% Trojan overlap、翻转率。
说明：
  只覆盖 SAT 可对齐的 832 个正节点，不能外推到全部 Trojan 节点。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
DEFAULT_V2 = ROOT / "results/hosts_bt31_seed42mode4_allb1_fold_fghtl_CncleanV2R42/best_model_ALL.pt"
DEFAULT_V1 = ROOT / "results/hosts_bt31_seed42mode4_allb1_fold_fghtl_Cnclean42/best_model_ALL.pt"
DEFAULT_F2 = "satrel_node_feats_sat_p0clean2.npy"
DEFAULT_F1 = "satrel_node_feats_sat.npy"


def load_t23():
    spec = importlib.util.spec_from_file_location("t23", ROOT / "train_test2.3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_cfg() -> dict:
    import yaml
    with open(ROOT / "_devcfg/dual.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_model(T23, cfg, ckpt: Path, dim: int, device: str):
    model = T23.build_model(cfg, dim, device)
    sd = torch.load(ckpt, map_location=device, weights_only=False)
    sd = sd.get("state_dict", sd) if isinstance(sd, dict) else sd
    missing, unexpected = model.load_state_dict(sd, strict=False)
    model.eval()
    print(f"[ckpt] {ckpt.name} dim={dim} missing={len(missing)} unexpected={len(unexpected)}")
    return model


def full_scores(model, x: torch.Tensor, ei: torch.Tensor, device: str) -> np.ndarray:
    with torch.no_grad():
        logits = model(x.to(device), ei.to(device))
        return F.softmax(logits.float(), dim=1)[:, 1].cpu().numpy()


def parse_view(v: str) -> tuple[str, str, str]:
    """host__inst_d1_s42__recipe -> (host, inst, recipe)."""
    p = str(v).split("__")
    if len(p) < 3:
        return str(v), "", ""
    return p[0], p[1].replace("_d1_s42", ""), p[2]


def summarize(p: np.ndarray, a: np.ndarray, b: np.ndarray, fid: np.ndarray,
              y: np.ndarray, method: str, thr: float = 0.5):
    sa, sb = p[a], p[b]
    va, vb = fid[a].astype(str), fid[b].astype(str)
    keep = va != vb
    views = sorted(set(va[keep]) | set(vb[keep]))
    q95 = {}
    for v in views:
        idx = np.where(fid == v)[0]
        pos = idx[y[idx] == 1]
        q95[v] = float(np.quantile(p[pos], 0.95)) if len(pos) else np.inf
    rows = []
    for i in np.where(keep)[0]:
        va_i, vb_i = va[i], vb[i]
        ta = sa[i] >= q95.get(va_i, np.inf)
        tb = sb[i] >= q95.get(vb_i, np.inf)
        host, inst, ra = parse_view(va_i)
        _, _, rb = parse_view(vb_i)
        rows.append(dict(method=method, pair=int(i), host=host, inst=inst,
                         recipe_a=ra, recipe_b=rb, node_a=int(a[i]), node_b=int(b[i]),
                         score_a=float(sa[i]), score_b=float(sb[i]),
                         pair_mean=float((sa[i] + sb[i]) / 2),
                         pair_std=float(np.std([sa[i], sb[i]])),
                         abs_diff=float(abs(sa[i] - sb[i])),
                         top5_a=bool(ta), top5_b=bool(tb), flip_top5=bool(ta != tb),
                         flip_thr=bool((sa[i] >= thr) != (sb[i] >= thr))))
    d = pd.DataFrame(rows)
    grp = []
    for (h, inst, ra, rb), g in d.groupby(["host", "inst", "recipe_a", "recipe_b"]):
        rho = np.nan
        if len(g) >= 3 and g["score_a"].nunique() > 1 and g["score_b"].nunique() > 1:
            rho = float(pd.Series(g["score_a"]).corr(pd.Series(g["score_b"]), method="spearman"))
        grp.append(dict(method=method, host=h, inst=inst, recipe_a=ra, recipe_b=rb,
                        n=len(g), spearman=rho,
                        top5_overlap=float((g["top5_a"] & g["top5_b"]).mean()),
                        flip_top5=float(g["flip_top5"].mean()),
                        flip_thr=float(g["flip_thr"].mean())))
    gd = pd.DataFrame(grp)
    summary = dict(
        method=method, n_pairs=int(len(d)), n_recipe_pairs=int(len(gd)),
        mean_score=float(np.mean(np.r_[sa[keep], sb[keep]])),
        mean_pair_std=float(d["pair_std"].mean()),
        median_pair_std=float(d["pair_std"].median()),
        mean_absdiff=float(d["abs_diff"].mean()),
        mean_spearman=float(gd["spearman"].mean()),
        median_spearman=float(gd["spearman"].median()),
        top5_overlap=float(gd["top5_overlap"].mean()),
        flip_top5=float(d["flip_top5"].mean()),
        flip_thr=float(d["flip_thr"].mean()),
    )
    return d, summary


def run_method(T23, cfg, name: str, ckpt: Path, feat: str, device: str,
               a, b, fid, y, ei):
    if not ckpt.exists():
        print(f"[skip] {name}: ckpt missing {ckpt}")
        return None, None
    base = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    sat = np.load(PT / feat)
    x = torch.cat([base.x.float(), torch.from_numpy(sat).float()], 1)
    model = load_model(T23, cfg, ckpt, int(x.size(1)), device)
    p = full_scores(model, x, ei, device)
    np.save(PT / f"FGHTL_scores_{name}.npy", p.astype(np.float32))
    print(f"[score] {name}: n={len(p)} range=[{p.min():.4f},{p.max():.4f}]")
    return summarize(p, a, b, fid, y, name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt-v2", type=Path, default=DEFAULT_V2)
    ap.add_argument("--ckpt-v1", type=Path, default=DEFAULT_V1)
    ap.add_argument("--feat-v2", default=DEFAULT_F2)
    ap.add_argument("--feat-v1", default=DEFAULT_F1)
    ap.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--thr", type=float, default=0.5)
    a = ap.parse_args()

    cfg, T23 = load_cfg(), load_t23()
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(int)
    ei = d.edge_index
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"])
    z = np.load(PT / "satrel_node_pairs_labelclean.npz")
    a_pos, b_pos, kind = z["a"], z["b"], z["kind"]
    m = (kind == 0) & (y[a_pos] == 1) & (y[b_pos] == 1)
    a_pos, b_pos = a_pos[m], b_pos[m]
    print(f"[pairs] kind0 pos-pos = {len(a_pos)}")

    all_pairs, summaries = [], []
    for name, ckpt, feat in (("C_v2", a.ckpt_v2, a.feat_v2),
                             ("C_v1_clean", a.ckpt_v1, a.feat_v1)):
        d_pairs, s = run_method(T23, cfg, name, ckpt, feat, a.device,
                                a_pos, b_pos, fid, y, ei)
        if s is not None:
            all_pairs.append(d_pairs)
            summaries.append(s)

    if not summaries:
        raise SystemExit("[ERROR] 没有可运行的方法（ckpt 全缺失）")
    T.mkdir(parents=True, exist_ok=True)
    pd.concat(all_pairs).to_csv(T / "FGHTL_stability_832_pairs.csv",
                                index=False, encoding="utf-8-sig")
    sm = pd.DataFrame(summaries)
    sm.to_csv(T / "FGHTL_stability_832_summary.csv", index=False, encoding="utf-8-sig")
    print("\n" + sm.to_string(index=False))
    print(f"\n[out] {T / 'FGHTL_stability_832_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


