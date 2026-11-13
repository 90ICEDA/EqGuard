# -*- coding: utf-8 -*-
"""
counterfactual.py —— 任务3：双干预数据（小规模 pilot）

两种干预：
  A) **安全干预**（security intervention）：同一个 netlist、同一份综合实现，
     只把 **Trojan 子图删掉** → benign 反事实。安全语义变了，实现尽量不变。
     本仓库 5 个电路里，`s15850t100 / s38417t300` 删掉 Trojan 门后**没有任何良性门**
     的输入来自 Trojan 门（已验证 USED_IN_BENIGN=0），因此删除是干净的；
     rs232/s35932/s38584 会有 1–4 个良性门失去一个输入，故本 pilot 只用前两个。
  B) **实现干预**（implementation intervention）：同一个 Trojan，套上不同 rewrite 算子
     （直接硬链接 matrix 里已有的 depth-1 单算子视图），安全语义不变。

由此可以比较两个量：
  ImplementationSensitivity = 同 Trojan、不同 rewrite 之间 score 的变化量
  SecuritySensitivity       = 同实现、Trojan↔benign 之间 score 的变化量
好模型 = 前者低、后者高。

子命令：
  python phase2/counterfactual.py build   --out-dir generate_trans/folds/dual_pilot \
      --name-index-from generate_trans/folds/single_to_composed_d2 --ops decomp,balance,refactor,resub
  # 然后正常训练（train_test2.3.py + --save-ckpt），再：
  python phase2/counterfactual.py measure --work-dir generate_trans/folds/dual_pilot \
      --ckpt-dir results/<run>
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import p2common as C  # noqa: E402

ORIG_DIR = C.ROOT / "generate_trans" / "orig"
MATRIX = C.ROOT / "generate_trans" / "matrix"
PARSER2 = C.ROOT / "data" / "verilog_data" / "parser2.py"
PROCESS_PT2 = C.ROOT / "process_pt2.py"

PILOT_CIRCUITS = ["s15850t100", "s38417t300"]
PILOT_OPS = ["decomp", "balance", "refactor", "resub"]
# val 视图按"每个 stem 内排序后每 N 个取 1"划分。N=3 时落在 val 的是第 3、6 个，
# 对 dual_pilot 的 6 个视图（balance, benign, decomp, ident, refactor, resub）
# 正好是 decomp / resub —— 保证 ident 与 benign 同时留在 train（配对才有效）。
# 用 N=2 会把 benign 和 ident 都抢进 val（上一轮的坑）。
VAL_EVERY = 3


def benign_netlist(text: str) -> str:
    """把含 'trojan' 的语句整体删掉（语句以 ';' 分隔，与 parser2 的切分一致）。"""
    parts = text.split(";")
    kept = [p for p in parts if "trojan" not in p.lower()]
    return ";".join(kept)


def trojan_names(orig_names) -> set:
    return {n for n in orig_names if "trojan" in str(n).lower()}


def build(out_dir: Path, name_index_from: Path, circuits, ops, seed: int,
          holdout_circuit: str = "") -> int:
    from phase2.name_index import build_name_index
    out = out_dir.resolve()
    for sub in ("orig", "trans", "mappings", "logs", "data/for_train", "data/not_for_train"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    idx_src = build_name_index(name_index_from.resolve())

    train_views, test_views = [], []
    for stem in circuits:
        orig_names = idx_src["orig"].get(stem)
        if not orig_names:
            raise SystemExit(f"[ERROR] name_index 里没有 {stem}（--name-index-from 需含该电路）")
        src = ORIG_DIR / f"{stem}.v"
        shutil.copy2(src, out / "orig" / src.name)
        ident_view = f"{stem}__ident_d0_s0"
        shutil.copy2(src, out / "trans" / f"{ident_view}.v")   # trojan（未改写）
        (out / "mappings" / f"{ident_view}.json").write_text(json.dumps({
            "src_verilog": f"{stem}.v",
            "node_alignment": {n: [n] for n in orig_names}}, ensure_ascii=False),
            encoding="utf-8")
        train_views.append(ident_view)

        tn = trojan_names(orig_names)
        ben_view = f"{stem}__benign_d0_s0"
        txt = benign_netlist(src.read_text(encoding="utf-8", errors="replace"))
        (out / "trans" / f"{ben_view}.v").write_text(txt, encoding="utf-8")
        (out / "mappings" / f"{ben_view}.json").write_text(json.dumps({
            "src_verilog": f"{stem}.v",
            "node_alignment": {n: [n] for n in orig_names if n not in tn}},
            ensure_ascii=False), encoding="utf-8")
        test_views.append(ben_view)

        for op in ops:
            v = f"{stem}__{op}_d1_s{seed}"
            vv, mm = MATRIX / "verilog" / f"{v}.v", MATRIX / "mappings" / f"{v}.json"
            if not (vv.exists() and mm.exists()):
                print(f"[WARN] 缺少 {v}，跳过")
                continue
            shutil.copy2(vv, out / "trans" / vv.name)
            shutil.copy2(mm, out / "mappings" / mm.name)
            train_views.append(v)

    for asset in ("verilog_lib.v", "gatelookup_recommended.json",
                  "gate_full_to_simplified_mapping.json"):
        s = MATRIX.parent / asset
        if not s.exists():
            s = C.ROOT / "data" / "verilog_data" / asset
        if s.exists():
            shutil.copy2(s, out / asset)

    if holdout_circuit:
        all_v = sorted(set(train_views + test_views))
        test_views = [v for v in all_v if v.split("__")[0] == holdout_circuit]
        train_views = [v for v in all_v if v.split("__")[0] != holdout_circuit]
        print(f"[build] holdout={holdout_circuit}：train={len(train_views)} test={len(test_views)}"
              f"（benign 视图进训练集，安全泛化在留出电路上测）")

    (out / "views.txt").write_text("\n".join(sorted(set(train_views + test_views))) + "\n",
                                   encoding="utf-8")
    fold_json = {"fold": out.name, "level": "dual_intervention_pilot",
                 "train_views": sorted(set(train_views)),
                 "test_views": sorted(set(test_views)),
                 "note": "A=同 Trojan 不同 rewrite（实现干预）；B=Trojan↔benign 删子图（安全干预）"}
    (out / "views.json").write_text(json.dumps(fold_json, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
    print(f"[build] 视图 {len(set(train_views + test_views))} 个"
          f"（train {len(set(train_views))} / test {len(set(test_views))}）-> {out}")

    env = dict(**__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"
    log = out / "logs" / "parser2.log"
    with open(log, "w", encoding="utf-8") as lf:
        rc = subprocess.call([sys.executable, str(PARSER2), "--out-root", "./data/for_train",
                              "--skip-debug", "--cycle-mode", "contract"],
                             cwd=str(out), stdout=lf, stderr=subprocess.STDOUT, env=env)
    print(f"[parser2] rc={rc}｜log={log}")
    if rc != 0:
        return rc
    rc = subprocess.call([sys.executable, str(PROCESS_PT2), "--work-dir", str(out),
                          "--fold-json", str(out / "views.json"), "--val-every", str(VAL_EVERY),
                          "--matrix-root", str(MATRIX), "--trans-label", "transported"],
                         cwd=str(C.ROOT))
    print(f"[process_pt2] rc={rc}")
    if rc == 0:
        verify_pair_roles(out)
    return rc


def verify_pair_roles(out: Path) -> int:
    """**建集后的硬校验**：每个 stem 的 ident / benign 必须都落在 train。

    为什么需要：`--val-every` 是按排序位置划 val 的，很容易把配对的两个视图
    一个划进 train、一个划进 val —— 那样 `security_pairs(train_views)` 会返回空，
    安全对比项就**静默失效**（我们上一轮就是这么翻车的：loss_sec 全程为 0）。
    """
    meta_path = out / "data/processed" / "dataset_meta.json"
    if not meta_path.exists():
        print("[verify] 跳过（还没有 dataset_meta.json）")
        return 1
    pv = json.loads(meta_path.read_text(encoding="utf-8"))["per_view"]
    by_stem: dict = {}
    for v, x in pv.items():
        stem, _, tail = v.partition("__")
        by_stem.setdefault(stem, {})[tail.split("_")[0]] = x.get("role")
    bad = []
    for stem, ops in sorted(by_stem.items()):
        line = ", ".join(f"{k}={v}" for k, v in sorted(ops.items()))
        print(f"[verify] {stem}: {line}")
        ri, rb = ops.get("ident"), ops.get("benign")
        if ri is None or rb is None:
            bad.append(f"{stem}: 缺少 ident/benign（ri={ri}, rb={rb}）")
            continue
        # 不变量 1：配对的两个视图必须同角色（否则一个进损失、一个没进）
        if ri != rb:
            bad.append(f"{stem}: ident={ri} 与 benign={rb} 角色不同 → 配对会被拆散")
            continue
        # 不变量 2：不能两个都在 val（val 不参与损失，pair 白配）
        if ri == "val":
            bad.append(f"{stem}: ident/benign 都落在 val → 不参与损失，配对白配")
    if bad:
        print("[verify][FAIL] 配对视图的角色有问题 → security loss 会静默失效：")
        for b in bad:
            print("        ", b)
        print(f"        修法：调整 --val-every（当前 {VAL_EVERY}）或显式指定角色。"
              "（注意：被 --holdout-circuit 留出的电路整支为 test 是正常的）")
        return 1
    print("[verify][OK] 每个 stem 的 ident/benign 同角色且不在 val，配对可用。")
    return 0


def measure(work_dir: Path, ckpt_glob: str, amp: bool, out_dir: Path) -> int:
    """比较 ImplementationSensitivity 与 SecuritySensitivity（同一模型、同一 fold）。"""
    import torch
    from phase2.name_index import build_name_index
    work = work_dir.resolve()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    orig, trans, meta = C.load_fold(work / "data" / "processed")
    for d in (orig, trans):
        d.x = d.x.to(device); d.edge_index = d.edge_index.to(device); d.y = d.y.to(device)
    vidx = C.view_index(trans)
    idx = build_name_index(work)
    cks = sorted(C.ROOT.joinpath("results").rglob(ckpt_glob))
    if not cks:
        print(f"[WARN] {work} 下找不到 {ckpt_glob}")
        return 1

    stems = sorted({C.parse_view(v).stem for v in vidx})
    rows = []
    for ck in cks:
        model, blob = C.load_ckpt(ck, device)
        with C.Embedder(model) as emb:
            _, lt = emb.forward(trans.x, trans.edge_index, amp=amp)
        p = torch.softmax(lt, 1)[:, 1].cpu().numpy()
        for stem in stems:
            names_t = idx["trans"]
            v_ident, v_ben = f"{stem}__ident_d0_s0", f"{stem}__benign_d0_s0"
            if v_ident not in vidx or v_ben not in vidx:
                continue
            s_ident, s_ben = names_t.get(v_ident, {}), names_t.get(v_ben, {})
            common = sorted(set(s_ident) & set(s_ben))
            pi = np.array([p[s_ident[n]] for n in common])
            pb = np.array([p[s_ben[n]] for n in common])
            sec_sens = float(np.abs(pi - pb).mean()) if len(common) else np.nan
            # 实现干预：同一个 Trojan 的不同 rewrite 视图 vs ident
            ops = {}
            for v in vidx:
                info = C.parse_view(v)
                if info.stem == stem and info.operators not in ("ident", "benign") and info.depth == 1:
                    sv = names_t.get(v, {})
                    c2 = sorted(set(s_ident) & set(sv))
                    if c2:
                        ops[info.operators] = float(np.abs(
                            np.array([p[s_ident[n]] for n in c2])
                            - np.array([p[sv[n]] for n in c2])).mean())
            impl_sens = float(np.mean(list(ops.values()))) if ops else np.nan
            # 视图级：Trojan 区域平均分（ident 中）
            troj_names = [n for n in s_ident if "trojan" in n.lower()]
            tp = float(np.mean([p[s_ident[n]] for n in troj_names])) if troj_names else np.nan
            bp = float(np.mean([p[s_ident[n]] for n in common])) if common else np.nan
            rows.append({"ckpt": ck.parent.name, "circuit": C.short_circuit(stem),
                         "n_matched_objects": len(common), "n_trojan_objects": len(troj_names),
                         "SecuritySens": round(sec_sens, 5),
                         "ImplementationSens": round(impl_sens, 5),
                         "SensRatio": round(sec_sens / (impl_sens + 1e-6), 3) if impl_sens else np.nan,
                         "trojan_mean_p": round(tp, 4), "benign_mean_p_ident": round(bp, 4),
                         **{f"impl_{k}": round(val, 5) for k, val in ops.items()}})
    d = pd.DataFrame(rows)
    C.ensure_dir(out_dir)
    d.to_csv(out_dir / "dual_intervention_sensitivity.csv", index=False, encoding="utf-8-sig")
    print("\n=== 双干预敏感性（同一模型：实现干预应低、安全干预应高）===")
    print(d.to_string(index=False))
    if not d.empty:
        print(f"\n[汇总] mean SecuritySens={d['SecuritySens'].mean():.4f}｜"
              f"mean ImplementationSens={d['ImplementationSens'].mean():.4f}｜"
              f"mean Ratio={d['SensRatio'].mean():.3f}")
    print(f"[导出] {out_dir / 'dual_intervention_sensitivity.csv'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="任务3：双干预（实现干预 vs 安全干预）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out-dir", type=Path, default=C.ROOT / "generate_trans" / "folds" / "dual_pilot")
    b.add_argument("--name-index-from", type=Path,
                   default=C.ROOT / "generate_trans" / "folds" / "single_to_composed_d2")
    b.add_argument("--circuits", type=str, default=",".join(PILOT_CIRCUITS))
    b.add_argument("--ops", type=str, default=",".join(PILOT_OPS))
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--holdout-circuit", type=str, default="",
                   help="把该 stem 的全部视图留作 test、其余（含 benign）作 train；"
                        "M2 需要 benign 进训练集，故用这个划分")

    m = sub.add_parser("measure")
    m.add_argument("--work-dir", type=Path, required=True)
    m.add_argument("--ckpt-glob", type=str,
                   default="dual_pilot_*/best_model_ALL.pt",
                   help="相对 results/ 的 glob，用来挑要评的双干预模型")
    m.add_argument("--amp", action="store_true")
    m.add_argument("--out-dir", type=Path, default=C.ROOT / "results" / "phase2" / "counterfactual")
    a = ap.parse_args()
    if a.cmd == "build":
        return build(a.out_dir, a.name_index_from,
                     [c for c in a.circuits.split(",") if c], [o for o in a.ops.split(",") if o],
                     a.seed, a.holdout_circuit)
    return measure(a.work_dir, a.ckpt_glob, a.amp, a.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())

