# -*- coding: utf-8 -*-
"""
build_hosts_fold.py —— 按 **γ 方案**打包受控主机 fold

γ 的设计（一个电路多份 orig，靠 mappings 的 src_verilog 建立真实血缘）：

  orig/    = **30 个感染基底**（每个 (host, instance) 一份）——它们带标签（Trojan* 门=1）
  trans/   = 140 个等价实现 + 40 个合法对照 = **180 个视图**
  mappings/= 每个 trans 视图 → **它自己的 orig**
               · 等价实现：直接用 rewrite_equiv 产出的 rw_mappings（含 1→2 的 node_alignment）
               · 合法对照：src_verilog 指向同 host 的**匹配木马**的感染基底
  orig_view_map.json = {orig_stem: [引用它的视图…]}（从 mappings 汇总）
              —— train_test2.3 的 apply_masks 用它按真实关系给 orig 打 mask

标签天然正确：orig 的 Trojan* 门→1 / 良性门→0；等价实现沿血缘拿标签；对照新增门默认 0 ✓

场景划分：
  test  = 全部 `rwbubble` 视图（**同 host、未见等价实现**）
  train = `rwdecomp3` + 全部合法对照
  「同类型木马、未见 host」→ 训练时用 `--fold-mode loco`（按 host 分组）
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import netlist_lib as NL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARSER2 = ROOT / "data" / "verilog_data" / "parser2.py"
PROCESS_PT2 = ROOT / "process_pt2.py"
MATRIX = ROOT / "generate_trans" / "matrix"
LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"

MATCH_OF = {"ctlmatcha": "injalpha", "ctlmatchb": "injbeta", "ctlmatchc": "injgamma",
            "ctlmatchd": "injdelta", "ctlmatche": "injepsilon", "ctlmatchf": "injzeta",
            "ctlmatchg": "injeta", "ctlmatchh": "injtheta",
            "ctlxor": "injalpha", "ctldup": "injalpha"}


def main() -> int:
    ap = argparse.ArgumentParser(description="打包 γ fold")
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts")
    ap.add_argument("--out-dir", type=Path,
                    default=ROOT / "generate_trans" / "folds" / "hosts_gamma")
    ap.add_argument("--val-every", type=int, default=4)
    ap.add_argument("--skip-parser", action="store_true")
    args = ap.parse_args()

    H, W = args.hosts_root.resolve(), args.out_dir.resolve()
    inst = pd.read_csv(H / "instances.csv")
    rwv = pd.read_csv(H / "rewrite_variants.csv")
    for d in ("orig", "trans", "mappings", "logs", "data/for_train", "data/not_for_train"):
        (W / d).mkdir(parents=True, exist_ok=True)

    # ---------- 1) orig ← 30 个感染基底 ----------
    tro = inst[inst["kind"] == "trojan"]
    for r in tro.itertuples():
        shutil.copy2(H / r.host / f"{r.view}.v", W / "orig" / f"{r.view}.v")

    # ---------- 2) trans ← 140 等价实现 + 40 对照 ----------
    ctl = inst[inst["kind"] == "control"]
    lib = NL.load_library(LIB_DEFAULT)
    ctl_views = set(ctl["view"])
    n_fix = 0
    for r in rwv.itertuples():
        shutil.copy2(H / r.host / "rw" / f"{r.rw_view}.v", W / "trans" / f"{r.rw_view}.v")
        mp = json.loads((H / r.host / "rw_mappings" / f"{r.rw_view}.json")
                        .read_text(encoding="utf-8"))
        src_stem = str(mp.get("src_verilog", "")).replace(".v", "")
        if src_stem in ctl_views:
            # ★ 对照派生出的改写变体：orig 里没有对照视图 → 必须把 src_verilog
            #   改指向「同一匹配木马的基底」，否则该视图会被 build_alignment 整条跳过（覆盖率为 0）
            ops = MATCH_OF.get(src_stem.split("__")[1].split("_")[0], "injalpha")
            mp["src_verilog"] = f"{r.host}__{ops}_d1_s42.v"
            n_fix += 1
        (W / "mappings" / f"{r.rw_view}.json").write_text(
            json.dumps(mp, ensure_ascii=False), encoding="utf-8")
    print(f"    (对照派生改写视图的 src_verilog 已重定向：{n_fix} 个)")
    ctl = inst[inst["kind"] == "control"]
    for r in ctl.itertuples():
        shutil.copy2(H / r.host / f"{r.view}.v", W / "trans" / f"{r.view}.v")
        src_ops = MATCH_OF.get(r.view.split("__")[1].split("_")[0], "injalpha")
        nl = NL.parse_netlist(H / r.host / f"{r.view}.v", lib)
        (W / "mappings" / f"{r.view}.json").write_text(json.dumps({
            "src_verilog": f"{r.host}__{src_ops}_d1_s42.v",
            "operator_family": "control", "ctl_type": r.ctl_type,
            "node_alignment": {i.name: [i.name] for i in nl.insts}},
            ensure_ascii=False), encoding="utf-8")

    # ---------- 3) orig_view_map（按真实引用关系） ----------
    ovm: dict = {}
    for f in sorted((W / "mappings").glob("*.json")):
        src = str(json.loads(f.read_text(encoding="utf-8")).get("src_verilog", "")).replace(".v", "")
        ovm.setdefault(src, []).append(f.stem)
    (W / "orig_view_map.json").write_text(json.dumps(ovm, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    print(f"[1] orig={len(tro)}  trans={len(list((W / 'trans').glob('*.v')))}"
          f"  mappings={len(list((W / 'mappings').glob('*.json')))}")
    print(f"[2] orig_view_map: {len(ovm)} 个 orig（例：{list(ovm.items())[:1]}）")

    # ---------- 4) assets ----------
    FD = ROOT / "generate_trans" / "folds" / "single_to_composed_d2"
    for a in ("verilog_lib.v", "gatelookup_recommended.json",
              "gate_full_to_simplified_mapping.json"):
        shutil.copy2(FD / a, W / a)

    # ---------- 5) views.json（test = rwbubble；train = 其余） ----------
    views = sorted(p.stem for p in (W / "trans").glob("*.v"))
    test_v = [v for v in views if "__rwbubble" in v]
    train_v = [v for v in views if v not in set(test_v)]
    (W / "views.json").write_text(json.dumps({
        "fold": W.name, "level": "controlled_cross_host",
        "train_views": train_v, "test_views": test_v,
        "note": "orig=30 个感染基底；test=未见等价实现(rwbubble)；loco 模式=未见 host"},
        indent=2, ensure_ascii=False), encoding="utf-8")
    (W / "views.txt").write_text("\n".join(views) + "\n", encoding="utf-8")
    print(f"[3] test={len(test_v)} / train={len(train_v)}")

    # ---------- 6) parser2 + process_pt2 ----------
    if not args.skip_parser:
        import os
        env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
        with open(W / "logs" / "parser2.log", "w", encoding="utf-8") as lf:
            rc = subprocess.call([sys.executable, "-X", "utf8", str(PARSER2),
                                  "--out-root", "./data/for_train", "--skip-debug",
                                  "--cycle-mode", "contract"],
                                 cwd=str(W), stdout=lf, stderr=subprocess.STDOUT, env=env)
        print(f"[4] parser2 rc={rc}")
        if rc != 0:
            return rc
        rc = subprocess.call([sys.executable, str(PROCESS_PT2), "--work-dir", str(W),
                              "--fold-json", str(W / "views.json"),
                              "--val-every", str(args.val_every),
                              "--matrix-root", str(MATRIX), "--trans-label", "transported"],
                             cwd=str(ROOT))
        print(f"[5] process_pt2 rc={rc}")
        mp = W / "data" / "processed" / "dataset_meta.json"
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            print("    orig:", m["orig"], "｜ trans:", m["trans"])
            print("    n_views=%d (train %d / val %d / test %d)" % (
                m["n_views"], m["n_train_views"], m["n_val_views"], m["n_test_views"]))

    # ---------- 7) views_meta.csv ----------
    # kind 必须**按 src 派生**：改写视图的"木马/合法"属性继承自它的 src_view，
    # 不能一律写 trojan —— 否则对照派生出的 80 个改写视图会被错标成木马，
    # provenance 不可用（而且是"静默错"，最危险）。另加 label1 便于下游对齐。
    rows = []
    for r in rwv.itertuples():
        inst = r.src_view.split("__")[1].split("_d1")[0]
        tro = int(inst.startswith("inj"))
        rows.append({"view": r.rw_view, "host": r.host, "src_view": r.src_view,
                     "inst_id": inst, "kind": ("trojan" if tro else "control"),
                     "ctl_type": "", "op": r.mode, "label1": tro, "seed": 42})
    for r in ctl.itertuples():
        inst = r.view.split("__")[1].split("_d1")[0]
        rows.append({"view": r.view, "host": r.host, "src_view": r.view,
                     "inst_id": inst, "kind": "control",
                     "ctl_type": (r.ctl_type or ""), "op": "inject",
                     "label1": 0, "seed": 42})
    pd.DataFrame(rows).to_csv(W / "views_meta.csv", index=False, encoding="utf-8-sig")
    print(f"[6] views_meta.csv -> {W / 'views_meta.csv'}（{len(rows)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

