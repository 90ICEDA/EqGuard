# -*- coding: utf-8 -*-
"""
train_security.py —— M1 / M2 的训练（M0 直接用 train_test2.3.py）

复用主流水线：
  * 数据/掩码/视图预算/阈值校准/指标：全部从 train_test2.3 导入（数值与 M0 一致）；
  * 任务损失与一致性损失：T22.siamese_loss（与 M0 完全相同）；
额外项（phase2.methods）：
  * M1:  sec 表示 + 对抗头（GRL），λ_adv 从 0 线性升到 --lambda-adv，
          让 sec 尽量不能预测 operator / depth（**不**对抗 circuit ID）；
  * M2:  M1 + λ_inv·(同 stem 同 depth、不同 operator 的 sec 视图表示拉近)
              + λ_sec·(matched benign/Trojan 的 sec 视图表示拉开，margin hinge)。

用法（M1，d2 fold）：
  python phase2/train_security.py --method M1 --work-dir generate_trans/folds/single_to_composed_d2 \
      --fold-json generate_trans/matrix/folds/single_to_composed_d2/views.json \
      --fold-mode fold --epochs 100 --seed 42 --view-policy pred_hard --view-budget 4 --amp
用法（M2，双干预 pilot）：
  python phase2/train_security.py --method M2 --work-dir generate_trans/folds/dual_pilot \
      --fold-json generate_trans/folds/dual_pilot/views.json --fold-mode fold \
      --epochs 60 --seed 42 --view-policy all --view-budget 8 --amp
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
import yaml

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent
sys.path.insert(0, str(ROOT))

from phase2 import p2common as C  # noqa: E402
from phase2.methods import (SecGIN, adversarial_loss, invariance_loss,  # noqa: E402
                            make_object_tensors, object_consistency_loss,
                            security_margin_loss)

OPS = ["decomp", "balance", "refactor", "resub"]
OP_IDX = {o: i for i, o in enumerate(OPS)}


def _load_t23():
    spec = importlib.util.spec_from_file_location("train_test2_3", str(ROOT / "train_test2.3.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T23 = _load_t23()
T22 = T23.T22


def parse_args():
    ap = argparse.ArgumentParser(description="M1/M2：security representation + 双干预约束")
    ap.add_argument("--method", choices=["M1", "M2", "M3"], required=True)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--fold-json", type=Path, required=True)
    ap.add_argument("--fold-mode", choices=["fold", "loco", "lio"], default="fold")
    ap.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    ap.add_argument("--circuits", type=str, default="",
                    help="只评估这些电路前缀（透传给 summarize 记录用）")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--view-policy", choices=["all", "random", "pred_hard", "inspection_hard"],
                    default="pred_hard")
    ap.add_argument("--view-budget", type=int, default=4)
    ap.add_argument("--hard-buffer", type=int, default=3)
    ap.add_argument("--val-every", type=int, default=5)
    ap.add_argument("--sec-dim", type=int, default=32)
    ap.add_argument("--lambda-adv", type=float, default=1.0)
    ap.add_argument("--lambda-inv", type=float, default=1.0)
    ap.add_argument("--lambda-sec", type=float, default=1.0)
    ap.add_argument("--margin", type=float, default=1.0)
    ap.add_argument("--lambda-obj", type=float, default=1.0,
                    help="M3：object-aware consistency 权重（会同时把原 gate-to-gate 一致性项置 0）")
    ap.add_argument("--obj-mode", choices=["mse_logit", "mae_prob"], default="mse_logit")
    ap.add_argument("--strict-pairs", action="store_true",
                    help="M2/M3：若 security 配对一次都没配上（安全对比项全程为 0），直接报错退出。"
                         "建议正式跑一律开，避免静默退化成 M1")
    ap.add_argument("--out-root", type=Path, default=ROOT / "results")
    ap.add_argument("--tag", type=str, default="")
    ap.add_argument("--amp", action="store_true")
    return ap.parse_args()


def view_op_depth_labels(views):
    """返回 (op_labels, op_mask, dep_labels, dep_mask)：未知标签用 mask 排除。"""
    op = np.full(len(views), -1, dtype=np.int64)
    dep = np.full(len(views), -1, dtype=np.int64)
    for i, v in enumerate(views):
        info = C.parse_view(v)
        if info.first_op in OP_IDX:
            op[i] = OP_IDX[info.first_op]
        if info.depth >= 1:
            dep[i] = min(info.depth, 3) - 1
    return op, op >= 0, dep, dep >= 0


def synthesis_pairs(views):
    """同 stem 同 depth、不同 operator 的视图对（用于 M2 的实现不变性）。"""
    buckets = defaultdict(list)
    for v in views:
        info = C.parse_view(v)
        if info.first_op in OP_IDX:
            buckets[(info.stem, info.depth)].append(v)
    pairs = []
    for _k, vs in buckets.items():
        pairs += list(itertools.combinations(sorted(vs), 2))
    return pairs


def security_pairs(views):
    """<stem>__ident_d0_s0 ↔ <stem>__benign_d0_s0 的配对（用于 M2 的安全对比）。"""
    byv = set(views)
    pairs = []
    for v in views:
        info = C.parse_view(v)
        if info.operators == "ident":
            b = f"{info.stem}__benign_d0_s0"
            if b in byv:
                pairs.append((v, b))
    return pairs


# ---- γ（受控跨宿主）fold 的配对：读 fold 目录里的 views_meta.csv ----
_MATCHED_CTL = {  # inj* ↔ ctl*（与 inject_trojan.CONTROL_SPECS 的 match 字段一致）
    "injalpha": "ctlmatcha", "injbeta": "ctlmatchb", "injgamma": "ctlmatchc",
    "injdelta": "ctlmatchd", "injepsilon": "ctlmatche", "injzeta": "ctlmatchf",
}


def load_views_meta(work_dir: Path):
    """γ fold 的 views_meta.csv（含 view/src_view/op）；没有或列不全则返回 None。"""
    p = Path(work_dir) / "views_meta.csv"
    if not p.exists():
        return None
    try:
        d = pd.read_csv(p)
    except Exception:
        return None
    return d if {"view", "src_view", "op"} <= set(d.columns) else None


def gamma_view_pairs(meta, views):
    """γ 的两类配对（按 **语义** 定义，不依赖视图名里的 operator 字段）：

    * inv：同一个 `src_view` 的视图之间（orig ↔ 各改写、改写之间）
           —— 等价重写（CEC 140/140 PASS），正是 M2 想拉近的对象；
    * sec：木马视图 ↔ **结构一一匹配**的合法对照视图（同 op 档）
           —— 负对照，"结构上无可区分"是预期，用来压住伪影。
    """
    have = set(views)
    sub = meta[meta["view"].isin(have)]
    inv: list = []
    for _src, g in sub.groupby("src_view"):
        vs = sorted(set(g["view"]))
        if len(vs) > 1:
            inv += list(itertools.combinations(vs, 2))
    idx = defaultdict(set)
    for _i, r in sub.iterrows():
        host = str(r["src_view"]).split("__")[0]
        inst = str(r["src_view"]).split("__")[1].split("_")[0]
        idx[(host, str(r["op"]), inst)].add(r["view"])
    sec: list = []
    for (host, op, inst), vs in idx.items():
        ctl = _MATCHED_CTL.get(inst)
        if not ctl:
            continue
        for b in idx.get((host, op, ctl), ()):
            sec += [(a, b) for a in sorted(vs)]
    return inv, sec


def pool_sec(model, trans, vidx_t, views):
    """每个视图的 sec 表示（视图内节点 mean-pool）。"""
    h = model.sec_repr(trans.x, trans.edge_index)
    return {v: h[vidx_t[v]].mean(0) for v in views}


def train_split(args, cfg, orig, trans, vidx_t, train_views, val_views, test_views, rng,
                tag, device, amp=False):
    model = SecGIN(in_channels=orig.x.size(1), hidden=int(cfg["model"]["hidden_channels"]),
                   layers=int(cfg["model"]["num_layers"]), sec=int(args.sec_dim)).to(device)
    # M3：预计算 object 分组（verified object only + region pooling）
    per_view_obj = make_object_tensors(args.work_dir, device) if args.method == "M3" else None
    lam_const = 0.0 if args.method == "M3" else cfg["siamese"]["lambda_const"]
    opt = torch.optim.Adam(model.parameters(), lr=float(cfg["train"]["lr"]),
                           weight_decay=float(cfg["train"]["weight_decay"]))
    epochs = int(cfg["train"]["epochs"])
    best = {"score": -1.0, "state": None, "thr": 0.5, "epoch": -1}
    hardness, log_rows = {}, []
    # 配对埋点：安全对比项必须"真的跑到"，不能静默为 0
    pair_stats = {"n_inv_pairs": 0, "n_sec_pairs": 0, "n_sec_epochs": 0}
    # γ fold：若目录里有 views_meta.csv，就启用"同 src_view 等价重写 / 木马↔匹配对照"配对
    ga_meta = load_views_meta(args.work_dir) if args.method in ("M2", "M3") else None
    ga_inv, ga_sec = (gamma_view_pairs(ga_meta, train_views) if ga_meta is not None
                      else ([], []))
    if ga_meta is not None:
        print(f"    [pairs] {tag}: γ 配对 inv={len(ga_inv)}｜sec={len(ga_sec)}"
              f"（同 src_view 等价重写 / 木马↔结构匹配对照）")
    for epoch in range(epochs):
        t0 = time.time()
        if args.view_policy == "pred_hard" and epoch % max(1, args.hard_buffer) == 0:
            hardness = T23.view_hardness(model, trans, vidx_t, train_views, amp=amp)
        elif args.view_policy == "inspection_hard" and epoch % max(1, args.hard_buffer) == 0:
            hardness = T23.view_inspection_hardness(model, trans, vidx_t, train_views, amp=amp)
        sel, sel_desc = T23.select_train_views(train_views, args.view_policy, args.view_budget,
                                               rng, hardness)
        T23.apply_masks(orig, trans, sel, val_views, test_views, vidx_t)

        model.train()
        opt.zero_grad()
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
            preds_o = model(orig.x, orig.edge_index)
            preds_t = model(trans.x, trans.edge_index)
            loss_task, *_ = T22.siamese_loss(
                preds_o, preds_t, orig.y[orig.train_mask], trans.y[trans.train_mask],
                orig, trans, lambda_const=lam_const,
                lambda_det=cfg["siamese"]["lambda_det"], lambda_nor=cfg["siamese"]["lambda_nor"],
                lambda_pos=cfg["siamese"]["lambda_pos"], trojan_w=cfg["siamese"]["trojan_w"],
                loss_type=cfg["siamese"]["loss_type"], use_hnm=False,
                const_mode=cfg["siamese"]["const_mode"], include_trans_loss=True)

            # ---- 对抗（GRL）：sec 尽量不能预测 operator / depth ----
            lambd = float(args.lambda_adv) * min(1.0, (epoch + 1) / max(1, epochs * 0.3))
            sv = sorted(sel)
            # 配对项要在**全体 train 视图池**上算：预算只有 4 时，配对两端几乎不可能同时被选中
            # （这正是 d2 上 n_sec_pairs=0/100 的深层原因）；对抗头仍只用被选中的 sv。
            sec_all = pool_sec(model, trans, vidx_t, sorted(train_views))
            op, om, dep, dm = view_op_depth_labels(sv)
            z = torch.stack([sec_all[v] for v in sv])
            adv = torch.zeros((), device=device)
            if om.any():
                lo, _ = model.adv_logits(z[torch.tensor(om, device=device)], lambd)
                adv = adv + F.cross_entropy(lo, torch.tensor(op[om], device=device))
            if dm.any():
                _, ld = model.adv_logits(z[torch.tensor(dm, device=device)], lambd)
                adv = adv + F.cross_entropy(ld, torch.tensor(dep[dm], device=device))
            loss_adv = args.lambda_adv * adv

            # ---- M2：双干预约束 ----
            loss_inv = torch.zeros((), device=device)
            loss_sec = torch.zeros((), device=device)
            n_inv = n_sec = 0
            if args.method in ("M2", "M3"):        # M3 = M2 + object-aware consistency
                sp = synthesis_pairs(sorted(train_views))
                if not sp:                      # γ：同 src_view 的等价重写
                    sp = ga_inv
                n_inv = len(sp)
                for a, b in sp:
                    loss_inv = loss_inv + invariance_loss(sec_all[a].unsqueeze(0),
                                                          sec_all[b].unsqueeze(0))
                if sp:
                    loss_inv = loss_inv / len(sp)
                cp = security_pairs(sorted(train_views))
                if not cp:                      # γ：木马 ↔ 结构匹配的合法对照
                    cp = ga_sec
                n_sec = len(cp)
                if cp:
                    sa = torch.stack([sec_all[a] for a, b in cp])
                    sb = torch.stack([sec_all[b] for a, b in cp])
                    loss_sec = security_margin_loss(sa, sb, margin=float(args.margin))
                loss_m2 = args.lambda_inv * loss_inv + args.lambda_sec * loss_sec
            else:
                loss_m2 = torch.zeros((), device=device)
            pair_stats["n_inv_pairs"] += n_inv
            pair_stats["n_sec_pairs"] += n_sec
            if n_sec:
                pair_stats["n_sec_epochs"] += 1
            # ---- M3：object-aware consistency（verified object + region pooling）----
            loss_obj = torch.zeros((), device=device)
            if per_view_obj is not None:
                loss_obj = args.lambda_obj * object_consistency_loss(
                    preds_o, preds_t, per_view_obj, sorted(sel),
                    orig.train_mask, trans.train_mask, mode=args.obj_mode)
            loss = loss_task + loss_adv + loss_m2 + loss_obj
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()

        cur_ap_t = cur_ap_o = float("nan")
        if (epoch + 1) % max(1, args.val_every) == 0 or epoch == epochs - 1:
            model.eval()
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                lo = model(orig.x, orig.edge_index)
                lt = model(trans.x, trans.edge_index)
                vp_t = F.softmax(lt[trans.val_mask].float(), dim=1)
                vp_o = F.softmax(lo[orig.val_mask].float(), dim=1)
                vl_t, vl_o = trans.y[trans.val_mask], orig.y[orig.val_mask]
                thr = None
                for probs, labels in ((vp_t, vl_t), (vp_o, vl_o)):
                    s = int(labels.sum())
                    if len(labels) > 1 and 0 < s < len(labels):
                        thr = T23.calibrate_threshold_fast(
                            probs, labels, strategy=cfg["train"]["thr_strategy"],
                            target_recall=0.85, target_fpr=0.05)
                        break
                if 0 < int(vl_t.sum()) < len(vl_t):
                    cur_ap_t = float(T23._ap(vp_t[:, 1].cpu().numpy(), vl_t.cpu().numpy()))
                if 0 < int(vl_o.sum()) < len(vl_o):
                    cur_ap_o = float(T23._ap(vp_o[:, 1].cpu().numpy(), vl_o.cpu().numpy()))
            if thr is None:
                thr = float(best["thr"])
            score = cur_ap_t if not np.isnan(cur_ap_t) else (
                cur_ap_o if not np.isnan(cur_ap_o) else -1.0)
            if score > best["score"]:
                best.update({"score": score, "epoch": epoch, "thr": float(thr),
                             "state": {k: v.detach().clone()
                                       for k, v in model.state_dict().items()}})
        log_rows.append({"split": tag, "epoch": epoch, "loss": float(loss.detach().item()),
                         "loss_adv": float(loss_adv.detach().item()),
                         "loss_inv": float(loss_inv.detach().item()),
                         "loss_sec": float(loss_sec.detach().item()),
                         "loss_obj": float(loss_obj.detach().item()),
                         "n_inv_pairs": n_inv, "n_sec_pairs": n_sec,
                         "n_sel_views": len(sel), "sel_desc": sel_desc,
                         "epoch_sec": round(time.time() - t0, 2),
                         "val_AP_trans": cur_ap_t, "best_val_AP": best["score"]})
    model.load_state_dict(best["state"])
    model.eval()
    # ---- 硬校验：安全对比项必须真的跑到 ----
    if args.method in ("M2", "M3") and float(args.lambda_sec) > 0:
        print(f"    [pairs] {tag}: n_inv_pairs 累计={pair_stats['n_inv_pairs']}｜"
              f"n_sec_pairs 累计={pair_stats['n_sec_pairs']}｜"
              f"有配对的 epoch={pair_stats['n_sec_epochs']}/{len(log_rows)}")
        if pair_stats["n_sec_epochs"] == 0:
            msg = (f"[FAIL] {args.method} 的 security 配对 **一次都没配上** → 安全对比项全程为 0，"
                   f"这次运行等价于 M1。请检查 ident/benign（或 γ 的 inj↔ctlmatch）"
                   f"是否同时落在 train 且被选进 sel。")
            if args.strict_pairs:
                raise SystemExit(msg)
            print("    " + msg)
    return model, best["thr"], log_rows


def main() -> int:
    args = parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    cfg["train"]["epochs"] = int(args.epochs)
    cfg["train"]["seed_id"] = int(args.seed)
    T23.seed_everything(int(args.seed))
    device = torch.device(cfg["train"]["device"] if torch.cuda.is_available() else "cpu")
    amp = bool(args.amp) and device.type == "cuda"

    pt_dir = (args.work_dir / "data" / "processed").resolve()
    orig, trans, meta = T23.load_fold(pt_dir)
    for d in (orig, trans):
        d.x = d.x.to(device); d.edge_index = d.edge_index.to(device); d.y = d.y.to(device)
        if getattr(d, "alignment", None) is not None:
            d.alignment = d.alignment.to(device)
    cfg["model"]["in_channels"] = int(orig.x.size(1))
    vidx_t = {v: ix.to(device) for v, ix in T23.view_index(trans).items()}

    test_views_all = T23.views_of_role(trans, "test")
    test_circuits = sorted({v.split("__")[0] for v in test_views_all})
    tag = (f"{meta['fold']}_seed{args.seed}mode{cfg['train']['train_mode']}"
           f"_{args.view_policy}b{args.view_budget}_{args.fold_mode}_{args.method}")
    if args.tag:
        tag += f"_{args.tag}"
    out_dir = Path(args.out_root) / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== {args.method} ===  数据 {pt_dir}\n  fold={meta['fold']}｜设备={device}｜amp={amp}"
          f"｜epochs={cfg['train']['epochs']}｜policy={args.view_policy}(b={args.view_budget})")
    print(f"  测试视图 {len(test_views_all)}（{test_circuits}）-> {out_dir}")

    rng = random.Random(int(args.seed) + len(tag))
    all_rows, all_logs = [], []
    if args.fold_mode == "fold":
        splits = [("ALL", test_circuits, test_views_all)]
    else:
        splits = [(c, [c], [v for v in test_views_all if v.startswith(c + "__")])
                  for c in test_circuits]

    for name, circs, tviews in splits:
        tr_v = [v for v in T23.views_of_role(trans, "train")
                if v.split("__")[0] not in set(circs)]
        va_v = [v for v in T23.views_of_role(trans, "val")
                if v.split("__")[0] not in set(circs)]
        if args.fold_mode == "fold":
            tr_v, va_v = T23.views_of_role(trans, "train"), T23.views_of_role(trans, "val")
        if not tr_v:
            print(f"[WARN] 划分 {name} 没有训练视图，跳过")
            continue
        print(f"\n--- {name}: train={len(tr_v)} val={len(va_v)} test={len(tviews)} ---")
        model, thr, logs = train_split(args, cfg, orig, trans, vidx_t, tr_v, va_v, tviews,
                                       rng, name, device, amp=amp)
        safe = str(name).replace("/", "_").replace("\\", "_")
        torch.save({"state_dict": model.state_dict(), "threshold": float(thr),
                    "split": str(name), "fold": meta["fold"], "method": args.method,
                    "model_kind": "sec",
                    "model_kwargs": {"hidden": int(cfg["model"]["hidden_channels"]),
                                     "layers": int(cfg["model"]["num_layers"]),
                                     "sec": int(args.sec_dim)},
                    "in_channels": int(cfg["model"]["in_channels"]),
                    "view_policy": args.view_policy, "view_budget": int(args.view_budget),
                    "seed": int(args.seed),
                    "best_val_AP": float(max([l["best_val_AP"] for l in logs],
                                             default=float("nan")))},
                   out_dir / f"best_model_{safe}.pt")
        print(f"    [ckpt] best_model_{safe}.pt｜阈值={thr:.4f}｜最优 val AP="
              f"{max([l['best_val_AP'] for l in logs], default=float('nan')):.4f}")
        all_logs += logs
        all_rows += T23.evaluate_split(model, orig, trans, vidx_t, tviews, thr, meta, name, amp=amp)

    df, _cdf = T23.summarize(all_rows, out_dir, all_logs, cfg, args, tag, device, amp)
    print(f"\n[完成] {args.method}｜评测视图 {len(df)}｜结果目录 {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

