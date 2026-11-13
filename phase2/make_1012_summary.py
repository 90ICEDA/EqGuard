# -*- coding: utf-8 -*-
"""make_1012_summary.py —— 生成 10.12 的扫描汇总表与记录问题清单。"""
from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "10.12" / "results"


def macro(d: str):
    p = os.path.join(d, "circuit_level_summary.csv")
    if not os.path.exists(p):
        return None
    m = pd.read_csv(p)
    mm = m[m.Circuit == "MACRO_MEAN"]
    if not len(mm):
        return None
    r = mm.iloc[0]
    return {"AP_T": round(float(r.Anchor_AP_Trans), 4), "AP": round(float(r.AP), 4),
            "Recall@5%": round(float(r.get("Recall@5%", float("nan"))), 4),
            "Paired_MAE": round(float(r.Paired_MAE), 4),
            "Flip": round(float(r.Flip_Rate), 4)}


CONF = {
    "sw_base": "lr1e-3, 100 轮, 预算 16（单折基准）", "sw_ep30": "lr1e-3, 30 轮, 预算 16",
    "sw_ep300": "lr1e-3, 300 轮, 预算 16", "sw_lr1e4": "lr1e-4, 100 轮, 预算 16",
    "sw_lr1e2": "lr1e-2, 100 轮, 预算 16", "sw_b4": "lr1e-3, 100 轮, 预算 4",
    "sw_b32": "lr1e-3, 100 轮, 预算 32", "sw_lc0": "lambda_const=0", "sw_lc5": "lambda_const=5",
    "sw_ld5": "lambda_det=5", "sw_tw20": "trojan_w=20", "sw_smoke": "只跑 5 轮（参照）",
    "c1_lr1e3_ep100_b16": "lr1e-3, 100 轮, 预算 16", "c2_lr1e3_ep300_b16": "lr1e-3, 300 轮, 预算 16",
    "c3_lr1e2_ep100_b16": "lr1e-2, 100 轮, 预算 16", "c4_lr1e3_ep100_b4": "lr1e-3, 100 轮, 预算 4",
    "c5_lr1e3_ep200_b16": "lr1e-3, 200 轮, 预算 16",
    "diag_all": "lr1e-3, 300 轮, 预算 16, 特征标准化", "M0_beta": "原配置 lr1e-4, 30 轮, 预算 4",
}


def collect(pattern: str, folds: str):
    rows = []
    for d in sorted(glob.glob(str(ROOT / "results" / pattern))):
        k = os.path.basename(d).split("_loco_")[-1] if "_loco_" in d else os.path.basename(d)
        r = macro(d)
        if r is None:
            continue
        r.update({"运行": k, "配置": CONF.get(k, ""), "折数": folds})
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    s0 = collect("hosts_beta_seed42mode4_pred_hardb*_loco_sw_*", "rs232 单折")
    if len(s0):
        s0 = s0.sort_values("AP_T", ascending=False)
        s0.to_csv(OUT / "stage0_singlefold.csv", index=False, encoding="utf-8-sig")
        print(f"[OK] stage0_singlefold.csv（{len(s0)} 行）")

    s1 = collect("hosts_beta_seed42mode4_pred_hardb*_loco_c[1-5]_*", "五折")
    ref = macro(str(ROOT / "results" / "hosts_beta_seed42mode4_pred_hardb4_loco_M0_beta"))
    if ref:
        ref.update({"运行": "M0_beta（参照）", "配置": CONF["M0_beta"], "折数": "五折"})
        s1 = pd.concat([s1, pd.DataFrame([ref])], ignore_index=True)
    if len(s1):
        s1 = s1.sort_values("AP_T", ascending=False)
        s1.to_csv(OUT / "stage1_5fold.csv", index=False, encoding="utf-8-sig")
        print(f"[OK] stage1_5fold.csv（{len(s1)} 行）")

    rows = []
    for d in sorted(glob.glob(str(ROOT / "results" / "hosts_beta_seed*mode4_pred_hardb16_loco_c1_*"))):
        s = int(re.search(r"seed(\d+)", os.path.basename(d)).group(1))
        r = macro(d)
        if r:
            r["seed"] = s
            rows.append(r)
    if rows:
        t = pd.DataFrame(rows).sort_values("seed")
        t.to_csv(OUT / "stage2_3seed.csv", index=False, encoding="utf-8-sig")
        print(f"[OK] stage2_3seed.csv（{len(t)} 行）  AP_T 均值 {t.AP_T.mean():.4f} "
              f"± {t.AP_T.std():.4f} | AP 均值 {t.AP.mean():.4f} ± {t.AP.std():.4f}")

    s3 = collect("hosts_beta_seed42mode4_pred_hardb*_loco_c[6-9]_*", "五折")
    if len(s3):
        s3 = s3.sort_values("AP_T", ascending=False)
        s3.to_csv(OUT / "stage3_refine.csv", index=False, encoding="utf-8-sig")
        print(f"[OK] stage3_refine.csv（{len(s3)} 行）")

    rows = []
    for tag in ("c1_lr1e3_ep100_b16", "c7_lr3e3_ep100_b16", "c8_lr1e3_ep100_b32"):
        for d in sorted(glob.glob(str(ROOT / "results" / f"hosts_beta_seed*mode4_pred_hardb*_loco_{tag}"))):
            p = os.path.join(d, "circuit_level_summary.csv")
            if not os.path.exists(p):
                continue
            s = int(re.search(r"seed(\d+)", os.path.basename(d)).group(1))
            r = macro(d)
            if r:
                r.update({"配置": tag, "seed": s})
                rows.append(r)
    if rows:
        t = pd.DataFrame(rows).sort_values(["配置", "seed"])
        t.to_csv(OUT / "stage4_3seed.csv", index=False, encoding="utf-8-sig")
        g = t.groupby("配置")["AP_T"].agg(["size", "mean", "std"]).round(4)
        print(f"[OK] stage4_3seed.csv（{len(t)} 行）")
        print(g.to_string())

    lessons = [
        ("单折扫出来的排序在大盘上不成立",
         "lr 1e-2 在 rs232 单折略胜 1e-3，五折上明显更差（0.2234 对 0.2624）",
         "扫描至少在五折上确认一次，单折只用来筛掉明显不行的方向"),
        ("一致性指标与检测能力反向",
         "原配置配对漂移 0.0174 看着最稳但基本不检测；调好后漂移 0.16 到 0.29 检测才上来",
         "不能只看一致性；输出接近常数的模型漂移天然低"),
        ("单种子会骗人", "一轮里被同一个坑骗了三次（协议方向、M2/M3 结论、预算 32 看着最好）；A 型同电路协议跨种子标准差 0.247，未见过电路只有 0.047",
         "任何方法对比至少三个种子；单种子的表必须标注"),
        ("对比没对齐训练预算", "GNN 是 30 步、lr 1e-4、只看 4 个视图、原始特征；LR 是 max_iter 400、自适应步长、全量、标准化。我却拿这个差距推断瓶颈",
         "报方法对比必须写清步数、学习率、每次梯度看到的样本量、输入是否标准化"),
        ("消融两边都要各自可信", "去掉消息传递的消融，两边一样欠训练，所以只能说明消息传递无额外收益，推不出瓶颈在目标函数",
         "用消融定位瓶颈前，先确认每条分支自己已收敛"),
        ("数据可能自带伪信号", "A 型载荷接死线，于是不可观测等于木马身份证；换成接真实输出后，单维启发式从 0.808 掉到 0.008",
         "先检查数据有没有捷径，并造结构匹配的负对照"),
        ("结论写得比证据强", "一是把良性节点的误报率当成召回与误报的对比；二是把欠训练说成目标函数的问题",
         "把观察到什么与推断什么分开写，推断要写明还缺哪个对照"),
        ("口径要一次说清", "逐电路等权与逐视图等权混引；误报率没说总体；宏平均没标种子数",
         "每张表头写清聚合方式、样本范围、种子数、指标定义"),
        ("特征与指标会静默消失", "可观测性 59% 到 77% 是无穷大；cut 真值表整数溢出成 1.59e75；四分位距为零的特征无法归一",
         "算不出来或退化的要单独记账，不能静默当零或直接丢"),
        ("输出命名不带区分度会互相覆盖", "评测脚本输出名写死，跑 B 型把 A 型表覆盖；同名 tag 下不同 view-budget 混在一起，对比时拿错基准",
         "先定命名方案，数据、种子、配置、轮数、预算都进目录名"),
        ("长跑干扰短跑", "后台 yosys 生成占着进程，等空闲再跑的串行链被卡死；日志被占用时重定向直接失败",
         "长短任务分开日志、分开输出目录，不写等空闲的串行链"),
        ("失败案例要留档", "四个 yosys 变体没通过 CEC，各差一个未证明点；还有若干跳过改写的实例",
         "每个批量步骤都落一份含失败原因的总表"),
        ("单折排序不能搬到全量", "lr 1e-2 在 rs232 单折略胜 1e-3，五折上明显更差（0.2234 对 0.2624）",
         "扫描至少在五折上确认一次，单折只用来筛掉明显不行的方向"),
        ("一致性指标与检测能力反向", "原配置配对漂移 0.0174 看着最稳但基本不检测；调好后漂移 0.23 到 0.35 检测才上来",
         "不能只看一致性；输出接近常数的模型漂移天然低"),
    ]
    pd.DataFrame(lessons, columns=["问题", "实际情况", "规矩"]).to_csv(
        OUT / "lessons.csv", index=False, encoding="utf-8-sig")
    print(f"[OK] lessons.csv（{len(lessons)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
