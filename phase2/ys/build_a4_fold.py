"""build_a4_fold.py —— 为 **A4 结构匹配对照集** 建一个独立 fold（`_dev_a4` ✓，只读源网表 ✓）。

A4 每个 host 有 24 个视图 = 8 个 shape（`s0..s7`）× 3 类：
  `a4trojan_sK`（木马 ✓ 有标签）/ `a4ctldead_sK`（同结构、载荷接死线 ✓）/ `a4ctlequiv_sK`（结构等价 ✓）
→ 同 `K` 的三者是**结构匹配**的 ✓，正是 N1 要的诊断集 ✓。

划分 ✓（与 v3.1 同向 ✓，**按 host 分组 ✓ 不跨折 ✗**）：
  train = rs232t1000 / s15850t100 / s35932t200 ✓｜val = s38417t100 ✓｜test = s38584t100 ✓

用法：py -X utf8 phase2/ys/build_a4_fold.py
产出：`generate_trans/folds/_dev_a4/`（trans/*.v ✓ + views.json ✓ + gate 映射 ✓ + data/processed/*.pt ✓）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "generate_trans" / "hosts_a4"
DST = ROOT / "generate_trans" / "folds" / "_dev_a4"
BASE = ROOT / "generate_trans" / "folds" / "hosts_bt31"
TRAIN_HOSTS = ("rs232t1000", "s15850t100", "s35932t200")
VAL_HOSTS = ("s38417t100",)
TEST_HOSTS = ("s38584t100",)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--dst", type=Path, default=DST)
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    W = a.dst
    if W.exists() and a.rebuild:
        shutil.rmtree(W)
    for d in ("trans", "orig", "mappings", "logs", "data/for_train", "data/processed"):
        (W / d).mkdir(parents=True, exist_ok=True)

    # 1) 复制网表 + 元数据 ✓
    n = 0
    for hd in sorted(p for p in a.src.iterdir() if p.is_dir()):
        for v in sorted(hd.glob("*.v")):
            shutil.copy2(v, W / "trans" / v.name)
            n += 1
        pj = hd / "provenance.json"
        if pj.exists():
            shutil.copy2(pj, W / "mappings" / f"{hd.name}__provenance.json")
    for f in ("gatelookup_recommended.json", "gate_full_to_simplified_mapping.json", "verilog_lib.v"):
        if (BASE / f).exists():
            shutil.copy2(BASE / f, W / f)
    print(f"[copy] {n} 个 trans 视图 ✓ → {W / 'trans'}")

    # 2) views.json（按 host 分折 ✓）
    def pick(hosts):
        out = []
        for h in hosts:
            out += sorted(x.stem for x in (W / "trans").glob(f"{h}__*.v"))
        return out
    tr, va, te = pick(TRAIN_HOSTS), pick(VAL_HOSTS), pick(TEST_HOSTS)
    assert not (set(tr) & set(va)) and not (set(tr) & set(te)) and not (set(va) & set(te)), "划分重叠 ✗"
    spec = dict(fold="_dev_a4", level="structure_matched_control",
                train_views=tr, val_views=va, test_views=te,
                note="A4 三胞胎（trojan / ctldead / ctlequiv）× 8 shape × 5 host ✓；按 host 分折 ✓")
    (W / "views.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[views] train={len(tr)} val={len(va)} test={len(te)} ✓")

    # 2b) **orig 侧** ✓：hosts_a4/<host>/base/<host>_clean.v 就是**注入前**网表 ✓
    #     + `orig_view_map.json`（全部 24 视图 → 该 host 的 clean ✓）+ CEC 清单（从 hosts_bt31 过滤 ✓）
    keep = set(tr) | set(va) | set(te)
    ovm: dict[str, list[str]] = {}
    for hd in sorted(p for p in a.src.iterdir() if p.is_dir()):
        cv = hd / "base" / f"{hd.name}_clean.v"
        if not cv.exists():
            print(f"[orig] 缺 {cv} ✗")
            continue
        # ✓ 关键 1：orig 网表要**按视图名**放（parser2 靠名字做 alignment ✓，用 `<host>_clean` 会 0 对齐 ✗）
        # ✓ 关键 2：**模块名也要改成视图名** ✓（BASE 的 orig 就是 `module <view>` ✓；只改文件名不够 ✗）
        txt = cv.read_text(encoding="utf-8", errors="replace")
        txt = re.sub(r"^`timescale[^\n]*\n", "", txt)
        for v in sorted(x.stem for x in (W / "trans").glob(f"{hd.name}__*.v")):
            t2 = re.sub(rf"\bmodule\s+{re.escape(hd.name)}_clean\b", f"module {v}", txt, count=1)
            (W / "orig" / f"{v}.v").write_text(t2, encoding="utf-8")
            ovm[v] = [v]
    (W / "orig_view_map.json").write_text(json.dumps(ovm, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print(f"[orig] {len(ovm)} 个 clean 网表 ✓ → orig/；orig_view_map {len(ovm)} 项 ✓")

    import csv as _csv
    # CEC 清单 ✓：**优先**用 A4 自己的 benign 日志 ✓
    # （`10.15/01_数据与标签/A4_对照样本/logs/benign_<view>.log` ✓ → 120/120 覆盖 ✓、全 PASS ✓）
    # 之前只从 `hosts_bt31/view_manifest_cec.csv` 过滤 ✗ → 那份只有 rs232 且命名不同 ✗ → 0/120 ✗
    benign = ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "logs"
    cec_rows: list[dict] = []
    if benign.exists():
        for v in sorted(keep):
            f = benign / f"benign_{v}.log"
            if not f.exists():
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"\b(PASS|FAIL|ERROR|TIMEOUT)\b", txt, re.I)
            cec_rows.append({"view_name": v,
                             "cec_status": (m.group(1).upper() if m else "UNKNOWN")})
    if cec_rows:
        with open(W / "view_manifest_cec.csv", "w", encoding="utf-8", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=["view_name", "cec_status"])
            w.writeheader()
            w.writerows(cec_rows)
        npass = sum(1 for r in cec_rows if r["cec_status"] == "PASS")
        print(f"[cec] A4 benign 日志 {len(cec_rows)}/{len(keep)} ✓（PASS {npass} ✓；缺的记 UNKNOWN ✓）")
    else:
        src_cec = BASE / "view_manifest_cec.csv"
        if src_cec.exists():
            with open(src_cec, encoding="utf-8-sig", newline="") as fh:
                rows = [r for r in _csv.DictReader(fh) if r.get("view_name") in keep]
            with open(W / "view_manifest_cec.csv", "w", encoding="utf-8", newline="") as fh:
                if rows:
                    w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)
            npass = sum(1 for r in rows if str(r.get("cec_status")).upper() == "PASS")
            print(f"[cec] BASE 过滤 {len(rows)}/{len(keep)} ✓（PASS {npass} ✓）")
    src_vm = BASE / "views_meta.csv"
    if src_vm.exists():
        import pandas as _pd
        vm = _pd.read_csv(src_vm, encoding="utf-8-sig")
        col = "view" if "view" in vm.columns else vm.columns[0]
        vm[vm[col].isin(keep)].to_csv(W / "views_meta.csv", index=False, encoding="utf-8-sig")
        print("[meta] views_meta.csv 已过滤 ✓")

    # 3) parser2 → process_pt2 ✓
    p2 = ROOT / "data" / "verilog_data" / "parser2.py"
    pp = ROOT / "process_pt2.py"
    env = dict(**__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"
    with open(W / "logs" / "parser2.log", "w", encoding="utf-8") as lf:
        rc = subprocess.call([sys.executable, "-X", "utf8", str(p2),
                              "--out-root", "./data/for_train", "--skip-debug",
                              "--cycle-mode", "contract", "--prov-root", str(a.src)],
                             cwd=str(W), stdout=lf, stderr=subprocess.STDOUT, env=env)
    print(f"[parser2] rc={rc} ✓")
    if rc != 0:
        return rc
    rc = subprocess.call([sys.executable, "-X", "utf8", str(pp), "--work-dir", str(W),
                          "--fold-json", str(W / "views.json"), "--matrix-root", str(W),
                          "--trans-label", "transported"], cwd=str(ROOT), env=env)
    print(f"[process_pt2] rc={rc} ✓")
    mp = W / "data" / "processed" / "dataset_meta.json"
    if mp.exists():
        m = json.loads(mp.read_text(encoding="utf-8"))
        print(f"  orig={m.get('orig')} trans={m.get('trans')} views={m.get('n_views')} "
              f"({m.get('n_train_views')}/{m.get('n_val_views')}/{m.get('n_test_views')}) "
              f"cec_all_pass={m.get('cec_all_pass')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
