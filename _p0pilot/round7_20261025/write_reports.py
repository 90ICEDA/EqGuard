"""Publish evidence-backed round7 corrections without erasing historical results."""
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / '10.15/00_说明'
TABLES = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
OUT = TABLES / 'sat_repair_round7'
now = datetime.now().astimezone().isoformat(timespec='seconds')


def backed_write(path, text):
    if path.exists():
        backup = path.with_name(path.name + '.bak_round7_20261025')
        if not backup.exists():
            shutil.copy2(path, backup)
    path.write_text(text, encoding='utf-8')


def prepend(path, notice):
    text = path.read_text(encoding='utf-8-sig')
    if '<!-- round7_audit_notice -->' not in text:
        backed_write(path, '<!-- round7_audit_notice -->\n' + notice + '\n\n' + text)


def main():
    audit = json.loads((OUT / 'audit_manifest.json').read_text())
    cov = pd.read_csv(OUT / 'cumulative_coverage.csv')
    feat = json.loads((OUT / 'feature_diagnostics.json').read_text())
    verify = json.loads((OUT / 'evidence_validation.json').read_text())
    actual = json.loads((OUT / 'r7_nonlocal_manifest.json').read_text())
    rev = json.loads((OUT / 'r7_review_manifest.json').read_text())
    assert not verify['errors'] and verify['plan_hash_ok']
    assert actual['queries'] + rev['queries'] <= 544
    statuses = [
        ('P0', '部分完成，未闭环', '真实SAT日志和40条小样本关系可追溯；旧32936行是探针口径',
         '指定injalpha/injepsilon的合法控制影响、下游观测、可靠对应后的跨实现一致性仍缺完整案例链；当前relation_consistency.csv五行均consistent=0，且不是这两个指定案例',
         'functional_relations_p0v2.csv; relation_consistency.csv; sat_repair_round7/evidence_validation.json'),
        ('P1', '部分完成', 'node_pairs表974004行，630207 proved；624212同实例、5995跨实例',
         '证明相等不等于安全角色相同；region_pairs_v3的483行全为trusted_trojan，不能代表四类区域覆盖；需要真实边界对应、错误对应审计与匹配图闭环',
         'node_pairs_sat_node.csv; region_pairs_v3.csv; region_role_status_v3.csv'),
        ('P2', '正式A–E未完成', 'v2表A/B/C_n各3seed，D_n只有2seed；旧结果作为历史诊断保留',
         'E_n=0seed；当前真实SAT特征因果增益未证实；缺同预算、同结构基线的正式完整消融与必要控制，旧身份偏置结果不可替代',
         'fg_htl_ablation_v2.csv; sparse_sat_round1/round_manifest.json'),
        ('P3', '基线与试验表存在，完整模型对照未完成', 'LOCO/LRO/LIO汇总存在，已有单seed SAT变体试验',
         '完整E缺失；LRO需区分同源未见视图与独立实例，LIO需审核真实机制留出；未逐折重新认证全部配置/CEC/可信覆盖/正例分母',
         'loco_summary.csv; lro_summary.csv; lio_summary.csv; n4_seedwise_ap.csv'),
        ('P4', '图与CSV存在，机制验证不完整', 'F6/F7/F8/F9及F9输入/PCA/消融CSV已存在',
         '不能按文件存在或mtime判完成；F9原导出器重新全图zscore、宽松加载权重，未确保与训练输入一致；现已加保护，旧图需精确重导；832对稳定性不能替代门级对应叠图与干预验证',
         'phase2/ys/f9_gnn_internals.py; F9_embeddings_v2.csv; FGHTL_stability_832_summary.csv'),
        ('P5', '未完成', '有repro、图表目录和历史表',
         '正式三seed完整模型、机制验证和证据版本未收口；不能把旧legacy表或未跑E写成已完成投稿结果',
         '10.15/99_共用资产/repro/index.csv; 10.15/07_论文图表/FIG_INDEX.md'),
    ]
    pd.DataFrame(statuses, columns=['priority', 'status', 'verified_artifacts', 'remaining_gap', 'evidence']).to_csv(
        OUT / 'spec_completion_audit.csv', index=False, encoding='utf-8-sig')
    spec = '# 10.22新说明完成情况：第七轮证据审计\n\n'
    spec += f'审计时间：{now}。原始要求以 `10.15/10.22新说明.txt` 为准；旧排期和完成勾选不作为完成证明。\n\n'
    spec += '| 项目 | 审计状态 | 已有证据 | 尚缺 |\n|---|---|---|---|\n'
    spec += '\n'.join(f'| {p} | {s} | {v} | {gap} |' for p, s, v, gap, ev in statuses)
    spec += '\n\n本轮核验了CSV、生成脚本和查询证据，未重新运行历史模型、未重求全部P1证明、未做图片视觉验收。因此“部分完成”不等于全部产物已认证。\n'
    spec += '\nP1总量较大，但跨实例5995个proved不能自动进入同木马跨实现一致性训练；应结合可信角色、相位、边界和源实例逐条限定用途。\n'
    spec += '\n当前优先顺序：先完成指定两例的功能机制和跨实现对应；据其得到可推广的提取/落点规则，再做小规模训练。停止仅靠随机增加端点关系数量推进。共享PI/状态证明是传播语义的要求，不是所有条件功能统计的统一准入要求。\n'
    backed_write(DOC / '10.22完成情况_第七轮证据审计.md', spec)

    selected_cov = cov[cov.basis.isin(['r6', 'r7', 'input_comparable'])]
    report = '# 第七轮：累计口径修复、参与者审计与有界扩样\n\n'
    report += f'完成时间：{now}。训练0次；新增SAT512问、独立复核24问，共536问（预算544），复核24/24一致；无timeout/error。扩样墙钟{actual["wall_s"]}秒、复核{rev["wall_s"]}秒；不含解析和审计。\n\n'
    report += '## 修正的漏洞\n\n'
    report += '- 从旧特征第七列恢复精确train/val支持集3231/780，保存 `old_support_indices.npz`；旧集不是无法恢复。\n'
    report += '- 邻域统一为包含种子、按实际source-to-target边传播的距离≤h；不再混用恰好第h跳，也不再遗漏旧证据。第六轮相对完整累计基线净新增25节点，其train/val两跳内正例增量均0；旧报告28是仅相对round4+5，不是完整累计基线。\n'
    report += '- 旧24条关系中有3条完全无强制输出，不能计作cond_fact。已备份并修复 `analyze_r6.py` 的筛选条件；历史表不覆盖，以本轮证据等级表更正。扩样后40条中共5条无条件强制事实。\n'
    report += '- Yosys整数bit编号只在对应JSON导出内有效，审计严格使用各轮自己的struct快照，不能跨轮混用编号。\n'
    report += '- F9导出器现在要求实际checkpoint、对应模型配置及该运行的精确归一化输入，strict加载；随机权重只允许显式smoke，旧F9图未因此自动认证。\n'
    report += '- 旧消融收集器需显式 `--allow-legacy-runs` 才可重新生成历史结果，并标注历史用途；未重写任何旧模型数值。\n\n'
    report += '## 已完成的扩样与映射\n\n'
    report += '按每个role中未使用、非keep设计的固定hash取前四个设计，PO/DFF种类与目标hash排序，查询前冻结。8个新设计、16条四输入关系，6 proved/10 not_proved；所有16条逐视图映射成功，24个端点支持节点。reach未计算，计划中的reach数值明确标为未测量，不作为SAT传播结论。\n\n'
    report += f'累计40条关系、{feat["support"]}个端点支持节点，类别{feat["classes"]}；真实置换变化train={feat["changed_by_role"]["train"]}、val={feat["changed_by_role"]["val"]}。稀疏特征仅用于诊断，没有接入训练。\n\n'
    report += f'160条输入参与者记录中{audit["participant_mapping"].get("mapped",0)}条唯一映射；{audit["comparable_input_nodes"]}个输入节点存在可比较影响统计，{audit["changed_input_nodes"]}个输入节点观察到条件变化。未把目标输出函数或标签复制给这些节点。原声称full_boundary的关系没有发现逃逸依赖；部分探针保留未选依赖。\n\n'
    report += '## 统一累计覆盖\n\n| basis | role | ≤h | 支持节点 | 正例 | 基线 | 新节点 | 新正例 |\n|---|---|---:|---:|---:|---|---:|---:|\n'
    for row in selected_cov.itertuples():
        report += f'|{row.basis}|{row.role}|{row.max_hops}|{row.nodes}|{row.positives}|{row.parent}|{int(row.incremental_nodes)}|{int(row.incremental_positives)}|\n'
    report += '\n第七轮直接净新增23节点，但train/val两跳内新增正例仍0；已有及新增参与者方案亦未产生额外正例覆盖。该结果是在规则冻结后诊断，未据此替换候选。\n\n'
    report += '## 决策与局限\n\n不启动训练，暂停同类盲扩样。下一阶段回到10.22指定的rs232 injalpha/injepsilon功能链与可靠跨实现对应。当前稀疏证据不足以检验定位增益，不代表SAT功能信息无用。partial和可行性统计可作为特征；不要求全部关系为完整函数，也不以缺失miter作为所有训练的否决理由。\n\n'
    report += '语义仍为旧cellmap、seq1任意初态；无自然触发/复位可达性或共享PI/状态干预证明。未对测试集做查询或指标计算。GNN前向与训练均未运行。\n\n'
    report += '复现：`ginvenv/Scripts/python.exe -B -X utf8 _p0pilot/round7_20261025/audit_repair.py`、`features_r7.py`、`test_audit_repair.py`。SAT重跑需显式运行freeze/run/review脚本，不应为查看报告重跑。证据哈希核验见evidence_validation.json；6个回归检查通过，两个旧入口拒绝不安全默认调用。\n'
    backed_write(DOC / 'SAT第七轮_口径修复与任务审计_20261025g.md', report)
    notice = '> 第七轮审计更正：本文件包含历史快照，最新完成状态见 [10.22完成情况_第七轮证据审计.md](10.22完成情况_第七轮证据审计.md)。不能据旧“P0/P1主体完成”或运行中记录判断当前已完成。'
    for name in ['10.22完成情况.md', '10.22_FGHTL_任务状态.md']:
        prepend(DOC / name, notice)
    prepend(ROOT / '10.15/07_论文图表/FIG_INDEX.md', '> 第七轮证据审计：F9旧图尚未按checkpoint的精确输入预处理重新认证；F6/F7/F8文件存在不等于10.22机制闭环已完成。详见00_说明/10.22完成情况_第七轮证据审计.md。')
    section = '\n\n<!-- sat_repair_round7:start -->\n## 17. 第七轮：口径修复与任务审计（未训练）\n\n'
    section += f'更新时间：{now}。详见 [SAT第七轮_口径修复与任务审计_20261025g.md](SAT第七轮_口径修复与任务审计_20261025g.md)。\n\n'
    section += '- 恢复旧功能支持掩码3231/780；统一距离≤h和完整累计基线。第六轮净新增25而非完整口径下的28，train/val两跳新增正例均0。\n'
    section += '- 修复cond_fact将无强制输出关系计入的问题；旧24条有3条，累计40条有5条。各轮bit编号使用各自struct快照。\n'
    section += '- 8新设计16关系：512问，6 proved/10 not_proved；24复核全一致，共536问；新增24端点支持节点、累计40关系71节点、相对完整累计净新增23。\n'
    section += '- 审计160条cut输入记录，144唯一映射；92输入节点可比较、41观察到变化。未复制输出函数或标签。扩样及参与者方案的train/val两跳新增正例仍0。\n'
    section += '- 真实置换改变train40/val25节点，全部bounded；生成稀疏诊断文件，不接训练。F9与旧消融入口已加防误用保护。\n'
    section += '- **不训练，暂停同类盲扩样**。10.22的P0/P1仅部分完成，P2正式A–E和P3完整模型对照未闭环，P4机制证据需精确重导，P5未完成。下一步完成指定两例功能链及跨实现对应。\n'
    section += '- 原始SAT/旧模型/旧表保留；6回归检查通过；测试未评估，训练0次。产物tables/sat_repair_round7。\n<!-- sat_repair_round7:end -->\n'
    for name in ['SAT作用证明.md', 'SAT工作总结.md']:
        path = DOC / name
        text = path.read_text(encoding='utf-8')
        if '<!-- sat_repair_round7:start -->' not in text:
            backed_write(path, text + section)
    repro = ROOT / '10.15/99_共用资产/repro/index.csv'
    backup = repro.with_name(repro.name + '.bak_round7_20261025')
    if not backup.exists():
        shutil.copy2(repro, backup)
    with repro.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        ids = {r.get('id') for r in reader}
    if 'sat_repair_round7_20261025' not in ids:
        row = dict(kind='audit', id='sat_repair_round7_20261025', path=str(OUT.relative_to(ROOT)), seed='',
                   config='_p0pilot/round7_20261025', note='536 SAT solves; 24/24 replay; no training; cumulative <=h fixed; P0-P5 audit')
        with repro.open('a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writerow(row)
    print('Reports, historical notices, and repro updated.', flush=True)


if __name__ == '__main__':
    main()
