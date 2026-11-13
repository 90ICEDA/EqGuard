"""merge_a3_ext.py —— A3-ext（keep 策略扩展对照）结果合并 + 事前判据裁决。

输入：`10.15/01_数据与标签/A3_keep三方案/tables/ext/<tag>/a3_keep_pilot.csv`
      （每个 tag = 1 个 (hosts-root, host, view) 跑出的 3 配方 × 4 方案 = 12 行）
输出：
  tables/ext/a3_keep_ext.csv            120 行合并表（含派生列）
  tables/ext/a3_keep_ext_summary.csv    scheme × recipe 汇总
  tables/ext/a3_keep_ext_verdict.csv    事前判据 D1–D5 与最终结论

判据（开跑前固定，见 A3 说明 §11）：
  D1 覆盖收益 : full 相对 cur 的 anchor_net 存活率均值提升 ≥ 0.02，或有 ≥2 个视图 full 更好
  D2 体积代价 : bytes(full)/bytes(cur) > 1.2 或 n_assign_in(full)/n_assign_in(cur) > 1.5
  D3 结构失真 : new_name_ratio(full) 相对 none 下降 > 3%，或 inst_ratio 偏离 none > 10%
  D4 保真对比 : dffq_surv / anchor_text_surv（bnd 预期最高）
  D5 等价性   : CEC 必须 PASS；非 PASS 单独列出，不参与均值
  结论        : D1 通过且 D2/D3 均不扣分 → FULL_OK；否则 REJECT_FULL
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEF_EXT = ROOT / "_a3ext" / "tables"
DOC_DIR = ROOT / "10.15" / "01_数据与标签" / "A3_keep三方案" / "tables" / "ext"


def load(ext: Path) -> pd.DataFrame:
    frames = []
    for p in sorted(ext.glob("*/a3_keep_pilot.csv")):
        d = pd.read_csv(p)
        tag = p.parent.name
        d["tag"] = tag
        d["src_root"] = tag.split("_")[0]
        frames.append(d)
        print(f"[读] {tag}: {len(d)} 行")
    if not frames:
        raise SystemExit(f"[ERROR] {ext} 下没有 */a3_keep_pilot.csv")
    d = pd.concat(frames, ignore_index=True)
    d["cec_pass"] = (d["cec"].astype(str).str.upper() == "PASS").astype(float)
    den_n = d["anchor_net_total"].replace(0, pd.NA)
    den_i = d["anchor_inst_total"].replace(0, pd.NA)
    d["anchor_net_rate"] = (d["anchor_net_alive"] / den_n).astype(float).fillna(0.0)
    d["anchor_inst_rate"] = (d["anchor_inst_alive"] / den_i).astype(float).fillna(0.0)
    for src, name in (("bytes", "bytes_rel"), ("lines", "lines_rel"),
                      ("n_assign_in", "assign_rel"), ("out_insts", "insts_rel")):
        base = d[d.scheme == "none"].set_index(["tag", "recipe"])[src]
        key = list(zip(d["tag"], d["recipe"]))
        d[name] = [v / base.loc[k] if (k in base.index and base.loc[k]) else float("nan")
                   for v, k in zip(d[src], key)]
    return d


def summarize(d: pd.DataFrame) -> pd.DataFrame:
    cols = {"n": ("view", "size"), "cec_pass": ("cec_pass", "mean"),
            "bytes_rel": ("bytes_rel", "mean"), "lines_rel": ("lines_rel", "mean"),
            "assign_rel": ("assign_rel", "mean"), "insts_rel": ("insts_rel", "mean"),
            "inst_ratio": ("inst_ratio", "mean"), "new_name": ("new_name_ratio", "mean"),
            "surv_net": ("surv_net_text", "mean"), "surv_net_struct": ("surv_net", "mean"),
            "dffq_surv": ("dffq_surv", "mean"), "anchor_text_surv": ("anchor_text_surv", "mean"),
            "anchor_net_rate": ("anchor_net_rate", "mean"),
            "anchor_inst_rate": ("anchor_inst_rate", "mean"),
            "overlap_none": ("overlap_with_none", "mean")}
    return d.groupby(["scheme", "recipe"]).agg(**cols).reset_index().round(4)


def verdict(d: pd.DataFrame) -> pd.DataFrame:
    m = d.groupby("scheme").agg(
        anchor_net_rate=("anchor_net_rate", "mean"),
        anchor_inst_rate=("anchor_inst_rate", "mean"),
        bytes=("bytes", "mean"), n_assign=("n_assign_in", "mean"),
        new_name=("new_name_ratio", "mean"), inst_ratio=("inst_ratio", "mean"),
        dffq=("dffq_surv", "mean"), anchor_text=("anchor_text_surv", "mean"),
        cec=("cec_pass", "sum"), n=("view", "size")).round(4)

    piv = d.pivot_table(index=["tag", "recipe"], columns="scheme",
                        values="anchor_net_rate", aggfunc="mean")
    piv_i = d.pivot_table(index=["tag", "recipe"], columns="scheme",
                          values="anchor_inst_rate", aggfunc="mean")
    better = int((piv.get("full", pd.Series(dtype=float)) >
                  piv.get("cur", pd.Series(dtype=float)) + 1e-9).sum())
    better_inst = int((piv_i.get("full", pd.Series(dtype=float)) >
                       piv_i.get("cur", pd.Series(dtype=float)) + 1e-9).sum())

    d1_gain = float(m.loc["full", "anchor_net_rate"] - m.loc["cur", "anchor_net_rate"])
    d1 = (d1_gain >= 0.02) or (better >= 2)
    d2_bytes = float(m.loc["full", "bytes"] / m.loc["cur", "bytes"])
    d2_assign = float(m.loc["full", "n_assign"] / m.loc["cur", "n_assign"])
    d2 = (d2_bytes > 1.2) or (d2_assign > 1.5)
    d3_nn = float(1 - m.loc["full", "new_name"] / m.loc["none", "new_name"])
    d3_inst = float(abs(m.loc["full", "inst_ratio"] - m.loc["none", "inst_ratio"])
                    / m.loc["none", "inst_ratio"])
    d3 = (d3_nn > 0.03) or (d3_inst > 0.10)
    nonpass = d[d.cec_pass < 1][["tag", "recipe", "scheme", "cec"]]
    full_ok = bool(d1 and not d2 and not d3)
    rec = "bnd" if float(m.loc["bnd", "dffq"] - m.loc["cur", "dffq"]) > 0.05 else "cur"

    rows = [
        ("D1_full_vs_cur_anchor_gain", round(d1_gain, 4),
         f"full 更好的视图数={better}/{len(piv)}（实例级 {better_inst}）",
         "PASS" if d1 else "FAIL"),
        ("D2_bytes_ratio_full_over_cur", round(d2_bytes, 3),
         f"assign 别名比={d2_assign:.3f}", "FAIL" if d2 else "PASS"),
        ("D3_newname_drop_full_vs_none", round(d3_nn, 4),
         f"inst_ratio 偏离={d3_inst:.4f}", "FAIL" if d3 else "PASS"),
        ("D4_dffq_surv",
         " ".join(f"{s}={m.loc[s, 'dffq']:.3f}" for s in ["none", "cur", "bnd", "full"]),
         "仅报告（越高=寄存器输出网结构存活越好）", "-"),
        ("D4_anchor_text_surv",
         " ".join(f"{s}={m.loc[s, 'anchor_text']:.3f}" for s in ["none", "cur", "bnd", "full"]),
         "仅报告", "-"),
        ("D5_cec",
         " ".join(f"{s}={int(m.loc[s, 'cec'])}/{int(m.loc[s, 'n'])}"
                  for s in ["none", "cur", "bnd", "full"]),
         f"非 PASS {len(nonpass)} 条", "PASS" if len(nonpass) == 0 else "WARN"),
        ("VERDICT_keep_all", "FULL_OK" if full_ok else "REJECT_FULL",
         f"推荐 keep={rec}（dffq: cur {m.loc['cur', 'dffq']:.3f} vs bnd {m.loc['bnd', 'dffq']:.3f}）",
         "-"),
    ]
    if len(nonpass):
        print("\n[非 PASS 明细]")
        print(nonpass.to_string(index=False))
    return pd.DataFrame(rows, columns=["item", "value", "detail", "status"])


def main() -> int:
    ap = argparse.ArgumentParser(description="合并 A3-ext 结果并裁决 keep=full 是否值得")
    ap.add_argument("--ext", type=Path, default=DEF_EXT)
    ap.add_argument("--doc-dir", type=Path, default=DOC_DIR,
                    help="合并结果额外拷贝到的文档目录（Unicode 路径由 Python 写，安全）")
    a = ap.parse_args()

    d = load(a.ext)
    s = summarize(d)
    table = verdict(d)

    a.ext.mkdir(parents=True, exist_ok=True)
    a.doc_dir.mkdir(parents=True, exist_ok=True)
    for name, df in (("a3_keep_ext.csv", d), ("a3_keep_ext_summary.csv", s),
                     ("a3_keep_ext_verdict.csv", table)):
        df.to_csv(a.ext / name, index=False, encoding="utf-8-sig")
        df.to_csv(a.doc_dir / name, index=False, encoding="utf-8-sig")

    print(f"\n=== 合并：{len(d)} 行 / {d.tag.nunique()} 个视图 / 配方 {sorted(d.recipe.unique())} ===")
    print(s.to_string(index=False))
    print("\n=== 事前判据裁决 ===")
    print(table.to_string(index=False))
    print(f"\n[导出] {a.ext}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
