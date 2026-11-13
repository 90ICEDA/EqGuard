# -*- coding: utf-8 -*-
"""
make_summary_csv.py —— 把 10.10 的结果整理成几个独立的 csv，供《最终说明.md》引用。

产物（都在 10.10/results/ 下）：
  summary_answers.csv        三个核心问题的答案
  summary_blocks.csv         八块任务：做了什么、结果、证据在哪
  summary_data_ab.csv        两套数据（A 型 / B 型）的对照
  summary_methods_ab.csv     各方法在 A 型 / B 型的表现
  summary_features_*.csv     各特征在 A 型 / B 型上的漂移与区分力
  summary_checks.csv         检查预算指标（first-hit / AnyMiss 等）
  summary_corrections.csv    本轮更正过的说法
  summary_todo.csv           还没做完的事
  summary_artifacts.csv      落盘位置清单
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent
RES = ROOT / "10.10" / "results"


def w(df: pd.DataFrame, name: str) -> None:
    p = RES / name
    df.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"[OK] {p}（{len(df)} 行）")


def main() -> int:
    if not RES.exists():
        print("[ERROR] 先跑出 results 目录")
        return 1

    w(pd.DataFrame([
        {"问题": "固定木马类型后跨宿主还掉多少",
         "结论": "掉约四分之一。A 型（死线载荷）掉三分之一，但 A 型数据本身带伪信号，只当对照用",
         "关键数字": "B 型 3 个 seed：同 host 的 AP_T 是 0.1058，未见过 host 是 0.0797，掉 25%；A 型是 0.4501 对 0.2983，掉 34%",
         "数字在哪": "10.10/results/summary_blocks.csv 与 beta/simple_models_macro.csv"},
        {"问题": "有没有既在等价实现下稳定、换宿主又还能用的特征",
         "结论": "有，但目前都还弱，不足以支撑一个可用的检测器",
         "关键数字": "B 型满 5 个 host：扇入支撑集 1.16、逻辑深度 0.94、局部 cut 单故障可靠性 0.68（这三者的等价漂移只有 0.12 到 0.23）；但同类方法的 AP 只有 0.22 到 0.28",
         "数字在哪": "10.10/results/summary_features_beta.csv"},
        {"问题": "检测器是在认木马，还是只在认少见逻辑",
         "结论": "认的是这块逻辑有没有被人读过。只把载荷从死线改成接真实输出，几乎所有方法立刻失效，只剩监督学习留了一点弱信号",
         "关键数字": "单维结构启发式的 AP 从 0.808 掉到 0.008；GNN 的木马对对照 AUC 从 0.906 掉到 0.652；LR 和 MLP 只从 0.947 与 0.963 掉到 0.933 与 0.906",
         "数字在哪": "10.10/results/summary_methods_ab.csv；cec_ab.csv（A 型与干净基底 3/3 功能等价，B 型 3/3 不等价）"},
    ]), "summary_answers.csv")

    w(pd.DataFrame([
        {"块": "一 修正现有实验", "状态": "完成",
         "做了什么": "查出 M2 配对不生效有两层原因并都修掉；干净基底改成删木马加人工修悬空；统一划分与指标",
         "结果": "loss_sec 从 0 变成 0.87 到 0.92；n_sec_pairs 从 0 变成 450（fold）和 1800（LOCO）；strict_pairs 全通过；干净基底 5 个全干净",
         "证据": "logs_phase2_m2_*.txt、generate_trans/hosts/repair_summary.csv"},
        {"块": "二 造受控跨宿主数据", "状态": "完成",
         "做了什么": "5 个 host 各 6 个木马实例加 8 个合法对照；每个实例出 2 份等价实现并逐对做 CEC；另外造了一整套 B 型（载荷接真实输出）",
         "结果": "A 型和 B 型各 70 个源视图加 140 个等价实现；等价实现的 CEC 都是 140 对全通过；血缘覆盖率 100% 与 99.9%",
         "证据": "generate_trans/hosts 与 hosts_bt 下的 instances.csv、provenance.json、rw_cec_results.csv"},
        {"块": "三 审计 39 维并补功能特征", "状态": "完成",
         "做了什么": "审计原有 39 维；补 9 个功能特征（信号概率、翻转率、CC0 与 CC1、可观测性、影响力、扇入支撑、到输出与寄存器的可达性）；再补 6 个局部 cut 功能签名；另外用 yosys 真实综合生成等价网表并逐个 CEC",
         "结果": "A 型 139 个等价网表全通过；B 型 375 个里 371 个通过（4 个 opt 变体各差一个未证明点，已排除，记在失败案例里）",
         "证据": "generate_trans/yosys_netlists 与 yosys_netlists_beta 下的 ys_manifest.csv"},
        {"块": "四 特征四问", "状态": "完成",
         "做了什么": "逐特征看四件事：等价改写前后漂多少、注入前后怎么变、能不能区分木马与合法对照、换 host 还在不在；并留了分布图",
         "结果": "把对照改成与木马结构一一匹配之后，单特征区分木马与对照的 AUC 正好是 0.5000，说明原先的区分力全部来自结构差异",
         "证据": "10.10/results/gamma_per_view.csv、fig_gamma_per_view_box.png"},
        {"块": "五 简单模型阶梯", "状态": "完成",
         "做了什么": "严格留一 host：单特征、Logistic Regression、提升树、小 MLP，以及复用 GNN 的检查点在同一批节点上打分",
         "结果": "A 型单特征 0.819 最高、GNN 0.331 最低；B 型 LR 0.296 最高、GNN 0.149 最低。GNN 在两套数据上都输给 LR",
         "证据": "10.10/results 与 results/beta 下的 simple_models_macro.csv"},
        {"块": "六 特征分组消融", "状态": "完成",
         "做了什么": "比四组特征：原 39 维、39 维加功能特征、只按监督区分力筛、按区分力加等价稳定筛。稳定性用的是第三块在 yosys 等价网表上实测的漂移值，不是自己拍的；另外做了 M1、M2、M3 的一致性消融",
         "结果": "加功能特征提升最大；按区分力加稳定筛的那组稳定优于只按区分力筛的那组，并且会把门类型 one-hot 剔掉；一致性那一族在 3 个 seed 下定稿为不保留",
         "证据": "10.10/results 与 results/beta 下的 feature_groups_macro.csv、feature_groups_by_host.csv"},
        {"块": "七 评测口径与三种泛化场景", "状态": "完成",
         "做了什么": "按任务书列全七项指标；实现三种泛化场景：同 host 未见实现、未见过 host、以及这次新实现的未见过木马实例",
         "结果": "三种场景都能跑。B 型上要查 11.6% 的门才能命中第一个木马门，5% 预算内漏掉至少一个木马门的概率是 0.59；A 型这两个数是 2.85% 和 0.17",
         "证据": "results/phase2/loco_gamma 与 loco_beta 下的 loco_summary_ckpt.csv"},
        {"块": "八 现有方法当 baseline", "状态": "完成",
         "做了什么": "拿四个结构启发式、LR、小 MLP、DART 式域不变（MLP 加对 host 的梯度反转）、GNN、随机当对照。除了算木马 AP，还算木马与结构匹配对照之间的 AUC",
         "结果": "B 型上 MLP 与 LR 的 AUC 还能到 0.94 和 0.92，GNN 0.67，单维启发式 0.64，随机 0.51，DART 式 0.35（比随机还差，等于把对照排得更靠前）",
         "证据": "10.10/results 与 results/beta 下的 baselines_macro.csv"},
    ]), "summary_blocks.csv")

    w(pd.DataFrame([
        {"项": "载荷出口", "A 型": "接一条没有扇出的新线（死线）", "B 型": "触发选通后劫持一个真实输出端口"},
        {"项": "功能是否改变", "A 型": "不改变，与干净基底完全等价", "B 型": "改变：不触发时输出原值，触发时被载荷改写"},
        {"项": "干净基底与它的 CEC", "A 型": "3 个 host 全通过", "B 型": "3 个 host 全不通过"},
        {"项": "图上的痕迹", "A 型": "载荷不可观测、离输出极远", "B 型": "载荷直连输出，痕迹被抹掉"},
        {"项": "规模", "A 型": "5 个 host 各 6 个木马加 8 个对照，fold 180 个视图，orig 117771 个节点", "B 型": "同构"},
        {"项": "等价实现的 CEC", "A 型": "140 对全通过", "B 型": "140 对全通过"},
        {"项": "血缘覆盖率（orig / trans）", "A 型": "100% / 99.87%", "B 型": "100% / 99.92%"},
        {"项": "在本文里的定位", "A 型": "只当伪信号对照，引用时必须注明", "B 型": "主结果"},
    ]), "summary_data_ab.csv")

    rows = []
    for tag, fn in (("A 型", RES / "baselines_macro.csv"),
                    ("B 型", RES / "beta" / "baselines_macro.csv")):
        if not fn.exists():
            continue
        for r in pd.read_csv(fn).itertuples():
            rows.append({"数据": tag, "方法": r.method,
                         "木马AP": round(float(r.AP_trojan), 4),
                         "木马对合法对照的AUC": round(float(r.AUC_T_vs_Ctl), 4),
                         "Recall@5%": round(float(getattr(r, "_5")), 4)
                         if hasattr(r, "_5") else ""})
    if rows:
        w(pd.DataFrame(rows), "summary_methods_ab.csv")

    for tag, fn, out in (("A 型", RES / "ys_feature_table.csv", "summary_features_alpha.csv"),
                         ("B 型", RES / "beta" / "ys_feature_table.csv", "summary_features_beta.csv")):
        if not fn.exists():
            continue
        t = pd.read_csv(fn)[["feature", "group", "equiv_drift", "trojan_delta",
                             "ctrl_delta", "sel_vs_ctrl"]].copy()
        t.insert(0, "数据", tag)
        t.columns = ["数据", "特征", "类别", "等价漂移", "木马变化量", "对照变化量", "去对照后剩余"]
        w(t.round(4).sort_values("去对照后剩余", ascending=False), out)

    w(pd.DataFrame([
        {"指标": "AP_T（逐电路等权）", "A 型": 0.2982, "B 型": 0.0953, "含义": "整体排序质量"},
        {"指标": "Recall@5%", "A 型": 0.5844, "B 型": 0.1694, "含义": "前 5% 的门里能捞回多少木马门"},
        {"指标": "FirstHitRank_Norm", "A 型": 0.0285, "B 型": 0.1155, "含义": "命中第一个木马门要查多少比例的门"},
        {"指标": "AnyMiss@5%", "A 型": 0.1667, "B 型": 0.5917, "含义": "5% 预算内漏掉至少一个木马门的概率"},
        {"指标": "Paired_MAE", "A 型": 0.031, "B 型": 0.0139, "含义": "同一批门在原件与等价实现两侧的打分差"},
        {"指标": "Flip_Rate", "A 型": 0.1362, "B 型": 0.0928, "含义": "两侧判决翻转的比例"},
        {"指标": "合法对照误报率", "A 型": "0.1468（fold）/ 0.3556（LOCO）", "B 型": "改用 AUC 衡量，见 summary_methods_ab.csv", "含义": "把正常逻辑判成木马的比例"},
    ]), "summary_checks.csv")

    w(pd.DataFrame([
        {"原来的说法": "M0 在未见过 host 时反而比同 host 更好",
         "更正为": "3 个 seed 下是同 host 更好。原来的结论来自只看了一个 seed",
         "原因": "同 host 协议会把同一实例的另一份等价实现放进训练，不同 seed 的结果能差 5 倍"},
        {"原来的说法": "A 型上一致性损失有害，不该保留",
         "更正为": "结论保留，但理由要换。A 型数据本身带伪信号，支撑不了这个判断；换成 B 型后 3 个 seed 同样不支持保留",
         "原因": "补了 seed 43 和 44"},
        {"原来的说法": "检测器对木马门与合法对照门的报警率几乎相同，所以分不开",
         "更正为": "那两个数都是良性节点上的误报率，不是召回与误报的对比。木马与对照之间的 AUC 有 0.91 到 0.96，排序能力是真的，只是工作点太差",
         "原因": "复核口径时发现表述过强"},
        {"原来的说法": "B 型上 M2 和 M3 比 M1 好，一致性损失的结论被数据翻转了",
         "更正为": "那是单个 seed 的噪声。3 个 seed 下 M2 和 M3 的 AP_T 都不高于 M1",
         "原因": "补了 seed 43 和 44"},
    ]), "summary_corrections.csv")

    w(pd.DataFrame([
        {"项": "B 型只做了一种功能篡改", "状态": "待做",
         "说明": "现在只有触发选通后劫持输出。可以再加三种：载荷改写触发器数据端（时序篡改）、直接改组合输出（最容易被发现，作下界）、新增一个输出端口（最显眼），这样能画出检出难度谱"},
        {"项": "未见实例场景只跑了 M0 和 seed 42", "状态": "待做",
         "说明": "fold 模式已经实现并跑通，扩到 M1 到 M3 加 3 个 seed 只是算力问题"},
        {"项": "CEC 结果没有并进 run 目录的汇总表", "状态": "待做",
         "说明": "run 表里的 CEC_Status 还是 UNKNOWN。CEC 原始结果本身完整，在 rw_cec_results.csv 与 ys_manifest.csv 里，只是没 join 过去"},
        {"项": "特征分组只做了单变量 top-k 筛选", "状态": "待做",
         "说明": "没有做前向选择或递归消除。任务书要求的只在训练 host 内筛选已经满足"},
        {"项": "DeepGate2 没有接上", "状态": "无法复现",
         "说明": "本机没有仓库也没有预训练权重。它的功能表示角色由 9 个功能特征加 6 个 cut 签名顶上"},
        {"项": "部分 0/1 特征算不出归一化后的漂移", "状态": "待做",
         "说明": "degree、is_ff、is_pi、is_po、op_or、op_xor、op_not、op_mux 这些的四分位距是 0，改用 JS 散度或 KS 之类的分布距离即可"},
        {"项": "GNN 为什么不如 LR，只查到方向没修", "状态": "已定位未修",
         "说明": "去掉消息传递反而更好、LR 是它的两倍，说明问题在训练目标（双图 siamese 加视图预算加一致性损失）。下一步应做最小化复现：只用 orig 图做纯节点分类，看能否追平 LR"},
    ]), "summary_todo.csv")

    arts = [
        ("数据", "generate_trans/hosts/", "A 型：5 个 host 各一份干净基底、6 个木马视图、8 个合法对照视图，以及每个源视图的两份等价实现"),
        ("数据", "generate_trans/hosts/provenance.json", "逐视图的注入记录：插了哪些门、载荷接在哪、触发器规格、注入后的合法性检查结果"),
        ("数据", "generate_trans/hosts/instances.csv", "70 行视图清单：类型、触发器规格、载荷规格、新增门数、干净与否"),
        ("数据", "generate_trans/hosts/rewrite_variants.csv", "140 行：源视图与等价实现的对应，以及改写规模、对象数、一对多拆分次数、跳过原因"),
        ("数据", "generate_trans/hosts/repair_summary.csv", "干净基底的修复记录：删了哪些木马门、修了几处悬空、最终是否干净"),
        ("数据", "generate_trans/hosts/rw_cec_results.csv", "A 型等价实现的 CEC 结果，140 对全通过"),
        ("数据", "generate_trans/hosts_bt/", "B 型整套，结构同上；provenance 里额外记了 payload_target 与被劫持的输出端口"),
        ("数据", "generate_trans/hosts_bt/rw_cec_results.csv", "B 型等价实现的 CEC 结果，140 对全通过"),
        ("图数据", "generate_trans/folds/hosts_gamma/", "A 型 fold：views.json（每个视图的角色）与 views_meta.csv（视图来源与标签属性）"),
        ("图数据", "generate_trans/folds/hosts_gamma/data/processed/", "图数据本体：orig_graph.pt、trans_graph.pt、dataset_meta.json（含血缘覆盖率）"),
        ("图数据", "generate_trans/folds/hosts_gamma/mappings/", "每个改写视图到它自己源视图的节点对应，含一对二拆分的对齐"),
        ("图数据", "generate_trans/folds/hosts_gamma/orig_view_map.json", "哪些视图引用了同一个源视图，打训练掩码时用"),
        ("图数据", "generate_trans/folds/hosts_gamma/phase2_name_index.json", "实例名到图节点号的索引，把实例级特征对上图节点时用"),
        ("图数据", "generate_trans/folds/hosts_gamma/gatelookup_recommended.json", "25 种门类型的顺序，对应 39 维里的第 0 到 24 位"),
        ("图数据", "generate_trans/folds/hosts_beta/", "B 型 fold，结构完全同构"),
        ("等价网表", "generate_trans/yosys_netlists/ys_manifest.csv", "A 型：每个设计与配方的运行情况与 CEC 结果，只有通过的才会进审计"),
        ("等价网表", "generate_trans/yosys_netlists/logs/", "每个变体的 yosys 日志，以及每次 CEC 的原始日志"),
        ("等价网表", "generate_trans/yosys_netlists_beta/", "B 型：375 个任务，371 个 CEC 通过，覆盖满 5 个 host"),
        ("训练产物", "results/hosts_gamma_seed*_..._M[0-3]_*", "A 型：四个方法乘两种协议乘三个 seed"),
        ("训练产物", "results/hosts_beta_seed*_..._M[0-3]_beta", "B 型：同上，共 24 个 run"),
        ("训练产物", "results/hosts_beta_seed42..._lio_M0_lio_beta/", "B 型的未见实例场景，六折"),
        ("训练产物", "results/hosts_beta_seed42..._M0_noedge_beta/", "去掉消息传递的消融，只跑了 seed 42"),
        ("训练产物", "每个 run 目录内", "run_config.json（配置与种子）、train_log.csv（逐轮损失与配对计数）、variant_level_summary.csv（逐视图指标）、circuit_level_summary.csv（逐电路与宏平均）、best_model_*.pt（逐电路检查点）"),
        ("训练产物", "results/_prefix_noPairs/", "M2 配对修复之前的旧 run，留作前后对照"),
        ("训练产物", "results/phase2/loco_gamma/ 与 loco_beta/", "用逐电路检查点复算的命中排名与漏检率"),
        ("结果表", "10.10/results/summary_*.csv", "本文引用的小结表，全部在这里"),
        ("结果表", "10.10/results/gamma_*.csv 与 beta/gamma_*.csv", "A 型与 B 型的七项指标：逐 run、宏平均、逐视图"),
        ("结果表", "10.10/results/ys_feature_table.csv 与 beta/", "特征表：等价漂移、木马变化量、对照变化量、去对照后剩余"),
        ("结果表", "10.10/results/feature_groups_macro.csv 与 beta/", "特征分组消融的宏平均；每折实际选中的列在 by_host 那份里"),
        ("结果表", "10.10/results/simple_models_macro.csv 与 beta/", "简单模型阶梯，含 GNN 复算行"),
        ("结果表", "10.10/results/baselines_macro.csv 与 beta/", "各方法的木马 AP 与木马对合法对照的 AUC"),
        ("结果表", "10.10/results/cec_ab.csv", "干净基底对 A 型、对 B 型的 CEC 结果"),
        ("结果表", "10.10/results/deadline_ablation*.csv", "一锤定音实验：单特征在 A 型与 B 型上的区分力对比，以及逐个视图的细节"),
        ("结果表", "10.10/results/fig_*.png", "上面各表对应的图"),
        ("代码", "phase2/inject_trojan.py", "干净基底构建与木马、对照注入；payload_target 为 hijack_out 时就是 B 型"),
        ("代码", "phase2/netlist_lib.py", "网表解析、依赖分析、合法性检查、重新发射"),
        ("代码", "phase2/rewrite_equiv.py", "生成等价实现，以及生成 CEC 脚本"),
        ("代码", "phase2/build_hosts_fold.py", "打包 fold：视图、映射、源视图表、解析与特征流水线"),
        ("代码", "generate_trans/cec/direct_cec.py", "任意两个网表的 yosys 状态边界 CEC"),
        ("代码", "phase2/ys/build_yosys_netlists.py", "用 yosys 真实综合生成等价网表并逐个 CEC"),
        ("代码", "phase2/ys/netlist_feats.py", "特征抽取：精确门语义、9 个功能特征、6 个 cut 签名"),
        ("代码", "phase2/ys/feature_audit_yosys.py", "在等价网表上算特征漂移与木马变化量"),
        ("代码", "phase2/ys/cec_ab.py", "干净基底与 A 型、B 型的对照 CEC"),
        ("代码", "phase2/ys/deadline_ablation.py", "造 B 型并做单特征对比"),
        ("代码", "phase2/simple_models.py", "简单模型阶梯"),
        ("代码", "phase2/feature_groups.py", "特征分组消融"),
        ("代码", "phase2/baselines.py", "各方法对照，含 DART 式域不变与 AUC 指标"),
        ("代码", "phase2/report_gamma.py", "从已有 run 目录复算七项指标并出图，不重训"),
        ("代码", "phase2/loco_metrics.py", "用逐电路检查点复算命中排名与漏检率"),
        ("代码", "phase2/train_security.py", "M1、M2、M3 训练"),
        ("代码", "train_test2.3.py", "M0 与主流水线；fold-mode 支持 fold、loco、lio；另有 abl-no-edges 消融"),
        ("代码", "phase2/make_summary_csv.py", "生成本目录里的 summary_*.csv"),
        ("文档", "10.10/最终说明.md", "本文，人写的任务结果说明"),
        ("文档", "10.10/第三块_执行记录.md", "最详细的底稿，第 0 到 16 节，含全部数字与失败案例"),
        ("文档", "10.10/说明.md", "任务白话版与进度看板"),
        ("文档", "10.10/protocol.md", "冻结的实验协议"),
        ("文档", "10.10/10.10.txt", "原始任务书"),
        ("文档", "10.10/执行记录.md 与 10.10/第二块_执行记录.md", "早期分块执行记录"),
        ("日志", "logs_phase2_m*_* 与 logs_phase2_M[123]beta_*", "训练日志，含配对计数埋点"),
        ("日志", "logs_phase2_ys_*", "yosys 生成与特征审计的输出"),
        ("日志", "logs_phase2_loco_*", "命中排名与漏检率的复算输出"),
        ("日志", "logs_phase2_bt_*", "B 型的注入、等价实现、CEC、fold"),
        ("日志", "logs_phase2_gamma.txt", "fold 打包日志"),
    ]
    w(pd.DataFrame(arts, columns=["类别", "路径", "说明"]), "summary_artifacts.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
