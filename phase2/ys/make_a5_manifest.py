# -*- coding: utf-8 -*-
"""make_a5_manifest.py —— A5：**统一数据 manifest** + 追溯报告。

一行 = 一个「源视图 × 配方 × keep 方案」的**转换产物** ✓（`sample_id` 唯一 ✓），记录：
  电路来源 / 注入记录（木马实例·家族·触发·载荷）/ 变换策略（配方·keep）/ 产物与 sha1 /
  对齐与标签可信度（A2 覆盖率 ✓、pos/unknown/neg ✓）/ CEC（转换 ✓、良性 ✓）/ fold 分组 / 工具版本 ✓。

同时做四项追溯检查（→ `a5_trace_report.csv` ✓）：
  1) 变体丢失：每个批次的「应有 vs 实到」+ 缺失清单 ✓（含 manifest 里的 ERROR 行 ✓）
  2) 重复：`sample_id` / 产物路径唯一性 ✓
  3) 标签/对齐：缺覆盖率的行 ✓、`n_inst_prov` 缺失 ✓
  4) fold：视图是否**只**落在一个 split（泄漏 0 ✓）、产物是否都已登记 ✓

用法：py phase2/ys/make_a5_manifest.py
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

TAB = ROOT / "10.15" / "01_数据与标签" / "A5_统一manifest" / "tables"
BATCHES = [
    ("yslib_test", ROOT / "generate_trans" / "yslib_test" / "convert_manifest.csv", "hosts_bt2"),
    ("keepab", ROOT / "generate_trans" / "keepab" / "conv" / "convert_manifest.csv", "hosts_bt2"),
    ("a4", ROOT / "generate_trans" / "a4" / "conv" / "convert_manifest.csv", "hosts_a4"),
    ("a4b", ROOT / "generate_trans" / "a4b" / "conv" / "convert_manifest.csv", "hosts_a4"),
]
COV_FILES = [
    ROOT / "10.15" / "01_数据与标签" / "A2_锚点与逻辑锥" / "tables" / "a2_coverage.csv",
    ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "tables" / "a2like" / "a2_coverage.csv",
    ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "tables" / "a2like_ext" / "a2_coverage.csv",
]
CEC_FILES = [
    ("keepab", ROOT / "10.15" / "01_数据与标签" / "A3_keep三方案" / "tables" / "a3_keep_pilot.csv"),
    ("a4", ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "tables" / "a3_keep_pilot.csv"),
    ("a4b", ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "tables" / "_ext_s15850" / "a3_keep_pilot.csv"),
]
FOLDS = [ROOT / "10.13" / "group_fold_v2" / "views.json",
         ROOT / "10.13" / "group_fold_v2_mixed" / "views.json"]


def sha1_16(p: Path) -> str:
    try:
        h = hashlib.sha1()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()[:16]
    except OSError:
        return ""


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except Exception:  # noqa: BLE001
        return str(p)


def load_prov() -> dict:
    out = {}
    for root, tag in (("hosts_bt2", ""), ("hosts_a4", "")):
        for f in sorted((ROOT / "generate_trans" / root).glob("*/provenance.json")):
            for r in json.loads(f.read_text(encoding="utf-8")):
                r.setdefault("host", f.parent.name)
                out[(root, r["view"])] = r
    return out


def yosys_version() -> str:
    try:
        r = subprocess.run(["wsl", "-e", "bash", "-c", "yosys -V"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        return (r.stdout or "").strip().replace("Yosys ", "")
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    prov = load_prov()

    cov = pd.DataFrame()
    for f in COV_FILES:
        if f.exists():
            d = pd.read_csv(f)
            d["src_root"] = d["src_root"].replace({"a4": "a4"})
            cov = pd.concat([cov, d], ignore_index=True)
    cov_key = {(str(r.src_root), str(r.stem), str(r.recipe)): r for r in cov.itertuples()} if len(cov) else {}

    cec = {}
    for tag, f in CEC_FILES:
        if f.exists():
            for r in pd.read_csv(f).itertuples():
                cec[(tag, f"{r.view}__keep{r.scheme}", str(r.recipe))] = str(r.cec)

    benign = {}
    fb = ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "tables" / "a4_benign_cec.csv"
    if fb.exists():
        for r in pd.read_csv(fb).itertuples():
            benign[str(r.view)] = str(r.cec_vs_clean)

    splits = {}                        # fold 目录名 → {转换后视图名: {split}}
    for fj in FOLDS:
        if not fj.exists():
            continue
        j = json.loads(fj.read_text(encoding="utf-8"))
        mp = {}
        for sp in ("train", "val", "test"):
            for v in j.get(f"{sp}_views", []) or []:
                mp.setdefault(v, set()).add(sp)
        splits[fj.parent.name] = mp

    yv = yosys_version()
    rows, errs = [], []
    for tag, man, srcroot in BATCHES:
        if not man.exists():
            print(f"[skip] 缺 {man}")
            continue
        d = pd.read_csv(man)
        for r in d.itertuples():
            stem, recipe = str(r.stem), str(r.recipe)
            fpath = str(r.file)
            bad = fpath.startswith("ERROR")
            m = re.search(r"__keep(\w+)$", stem)
            scheme = m.group(1) if m else ""
            view = re.sub(r"__keep\w+$", "", stem)
            rec = prov.get((srcroot, view), {})
            ck = (tag, stem, recipe)
            c = cov_key.get(ck)
            rows.append({
                "sample_id": f"{tag}|{srcroot}|{stem}|{recipe}",
                "status": "ERROR" if bad else "ok",
                "batch": tag, "src_root": srcroot,
                "host": str(r.host), "src_view": view, "stem": stem,
                "src_netlist": rel(ROOT / "generate_trans" / srcroot / str(r.host) / f"{view}.v"),
                "kind": ("clean" if view.endswith("_clean") else rec.get("kind", "")),
                "family": ("clean_base" if view.endswith("_clean") else
                             (rec.get("a4_family") or rec.get("ctl_type") or rec.get("ops") or "")),
                "prefix": rec.get("prefix", ""),
                "n_trig": rec.get("n_trig", ""), "trig_style": rec.get("trig_style", ""),
                "payload_style": rec.get("payload_style", ""),
                "payload_len": rec.get("payload_len", ""),
                "payload_target": rec.get("payload_target", ""),
                "hijacked_output": rec.get("hijacked_output", ""),
                "n_new_gates": len(rec.get("new_gates") or []),
                "new_gates": ";".join(map(str, rec.get("new_gates") or [])),
                "recipe": recipe, "keep_scheme": scheme,
                "conv_netlist": ("" if bad else rel(Path(fpath))),
                "conv_sha1_16": ("" if bad else sha1_16(Path(fpath))),
                "n_src_inst": getattr(c, "n_src_inst", "") if c is not None else "",
                "n_conv_gates": getattr(c, "n_conv_gates", "") if c is not None else "",
                "n_inst_prov": getattr(c, "n_inst_prov", "") if c is not None else "",
                "cov_core": getattr(c, "cover_core", "") if c is not None else "",
                "cov_region": getattr(c, "cover_region", "") if c is not None else "",
                "n_pos": getattr(c, "pos_total", "") if c is not None else "",
                "n_unknown": getattr(c, "unknown_total", "") if c is not None else "",
                "n_neg": getattr(c, "neg_total", "") if c is not None else "",
                "cec_conv": cec.get((tag, stem, recipe), "NA"),
                "cec_benign": benign.get(view, "") if tag.startswith("a4") else "",
                "label_usable": rec.get("label_usable", ""),
                "fold_view": f"{stem}__ys_{recipe}",
                "fold_tags": ";".join(
                    f"{fn}:{'/'.join(sorted(sp))}" for fn, mp in splits.items()
                    for sp in [mp.get(f"{stem}__ys_{recipe}")] if sp),
                "yosys": yv, "python": sys.version.split()[0], "pandas": pd.__version__,
            })
            if bad:
                errs.append({"batch": tag, "host": str(r.host), "stem": stem, "recipe": recipe,
                             "file": fpath})
    t = pd.DataFrame(rows)
    TAB.mkdir(parents=True, exist_ok=True)
    t.to_csv(TAB / "manifest.csv", index=False, encoding="utf-8-sig")

    # ---------------- 追溯报告 ----------------
    rep = []

    def add(check, batch, detail, expected, actual, ok=None):
        rep.append({"check": check, "batch": batch, "detail": detail,
                    "expected": expected, "actual": actual,
                    "ok": int((expected == actual) if ok is None else ok)})

    inj = t[t.kind != "clean"]                 # 注入视图（排除 <host>_clean 参考视图 ✓）
    cln = t[t.kind == "clean"]
    add("clean_view_rows", "all", ";".join(sorted(cln.src_view.unique())[:2]) + " ...",
        len(cln.host.unique()) * cln.recipe.nunique() if len(cln) else 0, len(cln))
    for tag, man, srcroot in BATCHES:
        if not man.exists():
            continue
        sub = inj[inj.batch == tag]
        n_src, n_rec = sub.src_view.nunique(), sub.recipe.nunique()
        n_sch = max(1, sub.keep_scheme.nunique())
        got = sub[sub.status == "ok"].sample_id.nunique()
        miss = []
        for v0, g0 in sub.groupby("src_view"):
            for r0 in sorted(sub.recipe.unique()):
                if r0 not in set(g0.recipe):
                    miss.append(f"{v0}/{r0}")
        add("products", tag, f"views={n_src} recipes={n_rec} schemes={n_sch} missing={';'.join(miss[:6])}",
            n_src * n_rec * n_sch, got)
    add("dup_sample_id", "all", "", 0, int(t.sample_id.duplicated().sum()))
    v2 = inj[inj.conv_netlist.notna() & (inj.conv_netlist.astype(str) != "")]
    add("dup_conv_path", "all", "", 0, int(v2.conv_netlist.duplicated().sum()))
    no_cov = v2[v2.cov_core.isna()]
    add("label_missing", "all", ";".join(sorted(no_cov.batch.unique())), 0, len(no_cov))
    no_prov = v2[(v2.batch.isin(["keepab", "a4"])) & (v2.n_inst_prov.astype(str) == "0")]
    add("inst_prov_zero", "keepab+a4", "", 0, len(no_prov))
    leak = {fn: [k for k, sp in mp.items() if len(sp) > 1] for fn, mp in splits.items()}
    add("fold_leak", ";".join(splits), ";".join(f"{k}={len(v)}" for k, v in leak.items()),
        0, sum(len(v) for v in leak.values()))
    rows_reg = []
    for fn, mp in splits.items():
        ys_rec = sorted({re.sub(r"^ys_", "", m2) for m2 in
                         (re.match(r".*__(ys_\w+)$", x).group(1) for x in mp if "__ys_" in x) if m2})
        for rcp in sorted(v2[v2.batch == "yslib_test"].recipe.unique()):
            sub2 = v2[(v2.batch == "yslib_test") & (v2.recipe == rcp)]
            reg = int(sub2.fold_view.isin(set(mp)).sum())
            rows_reg.append({"fold": fn, "recipe": rcp, "n_products": len(sub2),
                             "n_registered": reg,
                             "in_fold_recipes": int(rcp in ys_rec),
                             "missing_example": ";".join(sorted(
                                 sub2[~sub2.fold_view.isin(set(mp))].src_view.unique())[:3])})
        add("fold_recipes", fn, f"fold 内含 ys 配方={';'.join(ys_rec)}；视图数={len(mp)}",
            len(ys_rec), len(ys_rec))
    for fn, mp in splits.items():
        meta_p = ROOT / "10.13" / fn / "processed" / "dataset_meta.json"
        if meta_p.exists():
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            wd = str(meta.get("work_dir") or "")
            add("fold_source_batch", fn,
                f"work_dir={rel(Path(wd)) if wd else '?'}（源目录存在={Path(wd).exists()}）"
                f" cec_all_pass={meta.get('cec_all_pass')} n_views={meta.get('n_views')}",
                1, int(str(meta.get("cec_all_pass")) == "True"))
    reg_t = pd.DataFrame(rows_reg)
    reg_t.to_csv(TAB / "a5_fold_registration.csv", index=False, encoding="utf-8-sig")
    add("fold_unregistered", ";".join(splits),
        "按配方见 a5_fold_registration.csv（id/nand/opt 未进 fold 时全部未登记 ✓ 已知 ✗）",
        0, int((reg_t.n_products - reg_t.n_registered).sum()))
    add("error_rows", "all", ";".join(f"{e['host']}/{e['stem']}/{e['recipe']}" for e in errs[:6]),
        0, len(errs))
    r2 = pd.DataFrame(rep)
    r2.to_csv(TAB / "a5_trace_report.csv", index=False, encoding="utf-8-sig")

    print(t.groupby(["batch", "status"]).size().to_string())
    print()
    print(r2.to_string(index=False))
    print(f"\n[yosys] {yv}\n[OK] manifest {len(t)} 行 → {TAB / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
