#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench_device.py — 同一张真实 fold 图上的 CPU vs CUDA 训练步基准（含 bf16 AMP 与显存峰值）

测量的是**真实训练步**：整图前向 + `train_test2.2.siamese_loss`（mode4：trans CE + 一致性）+ 反向 + optimizer.step，
与 `train_test2.3.py` 的训练循环同构，因此数字可直接换算成「每轮耗时」。

用法：
  python bench_device.py --pt-dir generate_trans/folds/single_to_composed_d2/data/processed
  python bench_device.py --pt-dir ... --devices cpu,cuda --amp --steps 3
  python bench_device.py --pt-dir ... --subgraph-per-circuit 4      # 额外测「按视图诱导子图」训练
  python bench_device.py --pt-dir ... --json bench_device.json      # 落盘结果
"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import torch

CUR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR))

from models.gin_net import GINNodeClassifier  # noqa: E402


def load_t22():
    spec = importlib.util.spec_from_file_location("t22", str(CUR / "train_test2.2.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T22 = load_t22()


def load_graphs(pt_dir: Path):
    orig = torch.load(pt_dir / "orig_graph.pt", weights_only=False)
    trans = torch.load(pt_dir / "trans_graph.pt", weights_only=False)
    return orig, trans


def view_index(trans):
    out = {}
    for i, v in enumerate(trans.file_ids):
        out.setdefault(v, []).append(i)
    return {v: torch.tensor(i, dtype=torch.long) for v, i in out.items()}


def set_masks(orig, trans):
    """与 train_test2.3.apply_masks 同语义：orig 按电路、trans 按视图角色"""
    role = trans.view_role
    tr_v = {v for v, r in role.items() if r == "train"}
    va_v = {v for v, r in role.items() if r == "val"}
    tr_c = {v.split("__")[0] for v in tr_v}
    va_c = {v.split("__")[0] for v in va_v}

    def mask_of(n, file_ids, circuits):
        m = torch.zeros(n, dtype=torch.bool)
        for i, p in enumerate(file_ids):
            if p in circuits:
                m[i] = True
        return m

    orig.train_mask = mask_of(orig.num_nodes, orig.file_ids, tr_c)
    orig.val_mask = mask_of(orig.num_nodes, orig.file_ids, va_c)
    trans.train_mask = mask_of(trans.num_nodes, trans.file_ids, tr_v)
    trans.val_mask = mask_of(trans.num_nodes, trans.file_ids, va_v)
    return tr_v


def to_device(d, dev):
    d.x = d.x.to(dev)
    d.edge_index = d.edge_index.to(dev)
    d.y = d.y.to(dev)
    if getattr(d, "alignment", None) is not None:
        d.alignment = d.alignment.to(dev)
    for k in ("train_mask", "val_mask", "test_mask"):
        if getattr(d, k, None) is not None:
            setattr(d, k, getattr(d, k).to(dev))
    return d


def build_subgraph(trans, views, vidx, per_circuit):
    """所选视图的诱导子图（含 alignment 重映射）→ 归纳式训练用"""
    by_c = {}
    for v in sorted(views):
        by_c.setdefault(v.split("__")[0], []).append(v)
    sel = [v for c, vs in sorted(by_c.items()) for v in vs[:per_circuit]]
    keep = torch.unique(torch.cat([vidx[v] for v in sel]))
    new_id = torch.full((trans.num_nodes,), -1, dtype=torch.long)
    new_id[keep] = torch.arange(len(keep))
    ei = trans.edge_index
    m = (new_id[ei[0]] >= 0) & (new_id[ei[1]] >= 0)
    a = trans.alignment
    am = new_id[a[1]] >= 0
    sub = SimpleNamespace(
        num_nodes=len(keep), x=trans.x[keep], edge_index=new_id[ei[:, m]], y=trans.y[keep],
        train_mask=torch.ones(len(keep), dtype=torch.bool),
        val_mask=torch.zeros(len(keep), dtype=torch.bool),
        test_mask=torch.zeros(len(keep), dtype=torch.bool),
        alignment=torch.stack([a[0][am], new_id[a[1][am]]]),
    )
    return sub, len(sel)


def bench_once(dev, amp, steps, orig, trans, train_mode=4):
    """返回 (每步秒, 纯前向秒, 峰值显存 MB)"""
    include_trans = train_mode in (2, 3, 4)
    lambda_const = 1.0 if train_mode in (3, 4) else 0.0
    model = GINNodeClassifier(orig.x.size(1), 64, 2, 4).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-3)

    def one_step():
        model.train()
        opt.zero_grad(set_to_none=True)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
            po = model(orig.x, orig.edge_index)
            pt_ = model(trans.x, trans.edge_index)
            loss, *_ = T22.siamese_loss(
                po, pt_, orig.y[orig.train_mask], trans.y[trans.train_mask], orig, trans,
                lambda_const=lambda_const, lambda_det=1.4, lambda_nor=0.0, lambda_pos=0.0,
                trojan_w=6.0, loss_type="ce", use_hnm=False, const_mode="mse_logit",
                include_trans_loss=include_trans)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()
        return float(loss.detach().item())

    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dev)
        torch.cuda.synchronize()
    one_step()                                     # warmup（含 cudnn/cublas 初始化）
    if dev.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(steps):
        one_step()
    if dev.type == "cuda":
        torch.cuda.synchronize()
    step_sec = (time.time() - t0) / steps

    model.eval()
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
        if dev.type == "cuda":
            torch.cuda.synchronize()
        t1 = time.time()
        model(orig.x, orig.edge_index)
        model(trans.x, trans.edge_index)
        if dev.type == "cuda":
            torch.cuda.synchronize()
        fwd_sec = time.time() - t1
    peak = (torch.cuda.max_memory_allocated(dev) / 2 ** 20) if dev.type == "cuda" else float("nan")
    del model, opt
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return step_sec, fwd_sec, peak


def main():
    ap = argparse.ArgumentParser(description="CPU vs CUDA 训练步基准")
    ap.add_argument("--pt-dir", type=Path, required=True)
    ap.add_argument("--devices", type=str, default="cpu,cuda")
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--amp", action="store_true", help="追加测 bf16 autocast")
    ap.add_argument("--subgraph-per-circuit", type=int, default=0,
                    help="额外测「每电路取 N 个训练视图的诱导子图」训练（>0 生效）")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    orig, trans = load_graphs(args.pt_dir)
    tr_v = set_masks(orig, trans)
    vidx = view_index(trans)
    print(f"图规模：orig {orig.num_nodes} 节点 / {orig.edge_index.shape[1]} 边｜"
          f"trans {trans.num_nodes} 节点 / {trans.edge_index.shape[1]} 边")
    print(f"训练视图 {len(tr_v)} 个｜train_mask: orig {int(orig.train_mask.sum())} / "
          f"trans {int(trans.train_mask.sum())} 节点")
    print(f"torch {torch.__version__}｜cuda 可用={torch.cuda.is_available()}"
          + (f"｜{torch.cuda.get_device_name(0)}" if torch.cuda.is_available() else ""))

    devices = []
    for name in args.devices.split(","):
        name = name.strip()
        if name == "cuda" and not torch.cuda.is_available():
            print("[SKIP] cuda 不可用")
            continue
        devices.append(torch.device(name))

    variants = [("full-graph", 0)]
    if args.subgraph_per_circuit > 0:
        variants.append((f"subgraph@{args.subgraph_per_circuit}pc", args.subgraph_per_circuit))

    results = []
    for vname, k in variants:
        o, t = load_graphs(args.pt_dir)
        if k:
            t, n_sel = build_subgraph(trans, tr_v, vidx, k)
            o.train_mask = torch.ones(o.num_nodes, dtype=torch.bool)   # 子图训练时 orig 侧保留整图（19.7k，很小）
            print(f"\n[{vname}] 视图 {n_sel} 个 → 子图 {t.num_nodes} 节点 / {t.edge_index.shape[1]} 边")
        else:
            set_masks(o, t)
            print(f"\n[{vname}]")
        for dev in devices:
            for amp in ([False, True] if (args.amp and dev.type == "cuda") else [False]):
                od, td = to_device(o, dev), to_device(t, dev)
                tag = f"{vname} | {dev.type}{'+bf16' if amp else ''}"
                try:
                    s, f, peak = bench_once(dev, amp, args.steps, od, td)
                except RuntimeError as e:
                    print(f"  [FAIL] {tag}: {type(e).__name__}: {str(e)[:160]}")
                    results.append({"variant": vname, "device": dev.type, "amp": amp,
                                    "error": f"{type(e).__name__}: {str(e)[:200]}"})
                    del od, td
                    if dev.type == "cuda":
                        torch.cuda.empty_cache()
                    continue
                print(f"  {tag:<40s} 每步 {s:6.2f}s｜纯前向 {f:5.2f}s｜峰值显存 {peak:7.0f} MB")
                results.append({"variant": vname, "device": dev.type, "amp": amp,
                                "step_sec": round(s, 3), "fwd_sec": round(f, 3),
                                "peak_mem_mb": None if peak != peak else round(peak, 1),
                                "n_nodes": int(td.num_nodes), "n_edges": int(td.edge_index.shape[1])})
                del od, td
                if dev.type == "cuda":
                    torch.cuda.empty_cache()

    base = {r["variant"]: r for r in results if r["device"] == "cpu" and not r.get("error")}
    for r in results:
        if r["device"] == "cuda" and not r.get("error") and r["variant"] in base:
            r["speedup_vs_cpu"] = round(base[r["variant"]]["step_sec"] / r["step_sec"], 2)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[OK] 基准结果 -> {args.json}")
    print("\n=== 汇总（每步秒 / 提速）===")
    for r in results:
        if r.get("error"):
            print(f"  {r['variant']:<26s} {r['device']:<6s} amp={r['amp']!s:<5s} FAILED: {r['error'][:80]}")
        else:
            sp = f"｜提速 {r['speedup_vs_cpu']}×" if "speedup_vs_cpu" in r else ""
            print(f"  {r['variant']:<26s} {r['device']:<6s} amp={r['amp']!s:<5s} "
                  f"{r['step_sec']:6.2f}s｜{r['n_nodes']} 节点{sp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

