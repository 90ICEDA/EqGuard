"""Generate the SAT feature dictionary and current-evidence verdict table.

No training/SAT; reads the descriptive feature audit and writes Markdown/CSV.
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_round21/feature_diff'
OUT_MD = ROOT / '10.15/00_说明/SAT第二十一轮附_SAT特征字典与作用判断_20261026w.md'

# group, definition, verdict code, note
DEFS = {
    # 18 summary + covered
    'k_over_4': ('18D', 'k/4；k 是 cut 输入数（0–4）', 'E',
                 '表大小/上下文代理；原始正例偏高，固定 k 后失效'),
    'feasibility_known_fraction': ('18D', '(2^k - #unknown)/2^k', 'G',
                                   '当前完整 cut 上恒为 1；只作有效性元数据'),
    'feasible_fraction': ('18D', '#feasible/2^k', 'E',
                          '与 forced_fraction 相同；表可展开性'),
    'forced_fraction': ('18D', '#forced(feasible且输出0/1)/2^k', 'E',
                        '表可展开性；非功能语义'),
    'undecided_fraction': ('18D', '#feasible_undecided/2^k', 'G',
                           '当前恒为 0；无信息'),
    'infeasible_fraction': ('18D', '#infeasible/2^k', 'H',
                            '原始正例偏低，但 gate 内方向不一致'),
    'determinism_on_feasible': ('18D', 'forced/feasible；feasible=0 时为0', 'G',
                                '当前恒为 1；记账字段'),
    'determinism_valid': ('18D', '1[feasible>0]', 'G',
                          '当前恒为 1；记账字段'),
    'ones_on_forced': ('18D', 'ones/forced；forced=0 时为0', 'D',
                       '接近随机；判定值本身不区分正负例'),
    'ones_valid': ('18D', '1[forced>0]', 'G',
                   '当前恒为 1；记账字段'),
    'comparable_pair_fraction': ('18D', '#comparable/(k*2^(k-1))', 'D',
                                 '覆盖率代理；弱且不稳定'),
    'change_on_comparable': ('18D', '#changed/#comparable；无比较时为0', 'A',
                             '条件候选；k=4、INV/XOR/MX 有信号，AND/OR 反向'),
    'influence_valid': ('18D', '1[comparable>0]', 'G',
                        '当前近恒定；只作有效性元数据'),
    'max_input_influence': ('18D', 'max_b change_fraction_b', 'B',
                            '次级候选；与 input_change_max 重复，gate 间不稳定'),
    'complete_full_domain': ('18D', '1[unknown=0, forced=feasible, feasible=2^k]', 'C',
                             '覆盖/完整性元数据；弱'),
    'complete_restricted_domain': ('18D', '1[unknown=0, forced=feasible, 0<feasible<2^k]', 'C',
                                   '与 complete_full 互补；覆盖元数据'),
    'partial_forcing': ('18D', '1[0<forced<feasible]', 'G',
                        '当前恒为 0；无信息'),
    'has_unknown': ('18D', '1[unknown>0]', 'G',
                    '当前恒为 0；无信息'),
    'covered': ('18D', '1[目标节点属于 SAT 支持]', 'F',
                '37/37 正例覆盖；负例也覆盖 2254/2398，无区分度'),
    # Full-table scalars
    'n_infeasible': ('FULL', 'valid 行中 infeasible 的数量', 'H',
                     '原始差异被 gate 组成驱动，方向不稳定'),
    'frac_infeasible': ('FULL', 'n_infeasible/n_patterns', 'H',
                        '同 n_infeasible；不能作全局特征'),
    'n_forced_zero': ('FULL', 'valid 行中 forced_zero 的数量', 'E',
                      '表可展开性；固定 k=4 后接近随机'),
    'frac_forced_zero': ('FULL', 'n_forced_zero/n_patterns', 'D',
                         '归一化后更弱；不作主特征'),
    'n_forced_one': ('FULL', 'valid 行中 forced_one 的数量', 'E',
                     '原始偏高但 beta/AND 反向；k 控制后不稳定'),
    'frac_forced_one': ('FULL', 'n_forced_one/n_patterns', 'D',
                        '近随机；不作主特征'),
    'n_forced': ('FULL', 'n_forced_zero+n_forced_one', 'E',
                 '表行数/可展开性；与 k 的 Spearman 约 0.82'),
    'frac_forced': ('FULL', 'n_forced/n_patterns', 'E',
                    '与 forced_fraction 同类；非语义'),
    'frac_ones_on_forced': ('FULL', 'n_forced_one/n_forced', 'D',
                            '与 ones_on_forced 重复；接近随机'),
    'n_feasible_undecided': ('FULL', 'valid 行中 feasible_undecided 的数量', 'G',
                             '当前恒为 0；无信息'),
    'frac_feasible_undecided': ('FULL', 'n_feasible_undecided/n_patterns', 'G',
                                '当前恒为 0；无信息'),
    'n_solver_unknown': ('FULL', 'valid 行中 solver_unknown 的数量', 'G',
                         '当前恒为 0；无信息'),
    'frac_solver_unknown': ('FULL', 'n_solver_unknown/n_patterns', 'G',
                            '当前恒为 0；无信息'),
    'n_patterns': ('FULL', 'canonical 16 行中有效模式数（通常 2^k）', 'E',
                   '展开规模；不是功能内容'),
    'n_distinct_states': ('FULL', 'valid 行中不同状态类别数', 'D',
                          '弱；接近随机'),
    'state_entropy': ('FULL', '5 状态计数的 Shannon 熵', 'D',
                      '接近随机；不作主特征'),
    'input_pair_coverage_mean': ('FULL', '有效输入 pair_coverage 的均值', 'D',
                                 '覆盖统计；弱'),
    'input_pair_coverage_max': ('FULL', '有效输入 pair_coverage 的最大值', 'D',
                                '覆盖统计；弱'),
    'n_inputs_pair_coverage_positive': ('FULL', 'pair_coverage>0 的输入数', 'E',
                                        '与 k/有效输入数强相关；原始差异是规模'),
    'input_change_fraction_mean': ('FULL', '有效输入 change_fraction 的均值', 'A',
                                   '条件候选；k=4、INV/XOR/MX 富集，AND/OR 反向'),
    'input_change_fraction_max': ('FULL', '有效输入 change_fraction 的最大值', 'B',
                                  '与 max_input_influence 相同；次级候选'),
    'n_inputs_change_fraction_positive': ('FULL', 'change_fraction>0 的输入数', 'D',
                                          '原始方向一致但 k=4 后仅 AUC 0.531'),
    'input_influence_valid_mean': ('FULL', '有效输入 influence_valid 的均值', 'G',
                                   '近恒定；只作有效性元数据'),
    'input_influence_valid_max': ('FULL', '有效输入 influence_valid 的最大值', 'G',
                                  '近恒定；只作有效性元数据'),
    'n_inputs_influence_valid_positive': ('FULL', 'influence_valid>0 的输入数', 'E',
                                          '与 k/有效输入数强相关；原始差异是规模'),
    'n_inputs': ('FULL', '有效输入数（=k）', 'E',
                 '表大小；与 k_over_4 重复'),
}


def fmt(v, digits=3):
    if v is None:
        return 'NA'
    try:
        v = float(v)
    except Exception:
        return str(v)
    if not np.isfinite(v):
        return 'NA'
    if abs(v) >= 100:
        return f'{v:.1f}'
    return f'{v:.{digits}f}'


def table(df, group, title):
    sub = df[df.feature.isin([k for k, v in DEFS.items() if v[0] == group])].copy()
    order = [k for k, v in DEFS.items() if v[0] == group]
    sub['_o'] = sub.feature.map({k: i for i, k in enumerate(order)})
    sub = sub.sort_values('_o')
    lines = [f'### {title}', '',
             '| 特征 | 定义 | 正例均值 | 负例均值 | AUC | AP | fam+ | gate+ | 当前判断 |',
             '|---|---|---:|---:|---:|---:|---:|---:|---|']
    for _, r in sub.iterrows():
        _, definition, code, note = DEFS[r.feature]
        verdict = JUDGMENTS[code]
        lines.append(f"| `{r.feature}` | {definition} | {fmt(r.pos_mean)} | {fmt(r.neg_mean)} | "
                     f"{fmt(r.auc)} | {fmt(r.ap)} | {fmt(r.family_positive_fraction)} | "
                     f"{fmt(r.gate_positive_fraction)} | {verdict}<br>{note} |")
    return '\n'.join(lines)


def main():
    df = pd.read_csv(T / 'feature_overall.csv')
    missing = set(DEFS) - set(df.feature)
    extra = set(df.feature) - set(DEFS)
    assert not missing, missing
    assert not extra, extra
    assert len(DEFS) == 45
    global JUDGMENTS
    JUDGMENTS = {
        'A': 'A 条件候选',
        'B': 'B 次级候选',
        'C': 'C 元数据/覆盖',
        'D': 'D 证据不足',
        'E': 'E 规模/混杂',
        'F': 'F 覆盖伪信号',
        'G': 'G 常量/无信息',
        'H': 'H 反向/不稳定',
    }
    head = f'''# SAT 特征字典与当前作用判断

更新时间：2026-10-26。范围：当前小训练集（Round 18/21，8 个小网表、2,435 节点、37 正例）实际使用或审计过的 SAT 特征。  
**无新增 SAT、无训练、无测试调参。** 统计均为 covered 节点上的 posthoc 描述性统计；正例 37、负例 2,254，AP 随机基线 **37/2291 = 0.0161**。

## 0. 先记住三个混杂

1. 正例 37/37 是 `comb_output`，35/37 是 `k=4`；
2. gate 分布为 INVX0 14、XOR2X1 12、MX2X1_RS 5、AND2X2 5、OR2X1 1，DFF 为 0；
3. 因此“正例 vs 全部负例”的原始 AUC 会混入 gate/role/k；严格结论应看 `within_comb_output`、`comb_k4` 和 `family × driver × k`。

判断代码：

| 代码 | 含义 |
|---|---|
| A | 条件候选：只在特定 gate/context 使用，不能当全局特征 |
| B | 次级候选：有信号但与 A 高度相关或 gate 不稳定 |
| C | 元数据/覆盖：应作为 mask、分层或覆盖记账，不作为功能语义 |
| D | 证据不足：弱、方向不稳定或接近随机 |
| E | 规模/混杂：表大小/可展开性，原始差异主要由 k/gate 导致 |
| F | 覆盖伪信号：覆盖几乎无类间对比 |
| G | 常量/无信息：当前数据上恒定或近恒定 |
| H | 反向/不稳定：原始方向与分层方向相反 |

## 1. 18 维摘要 + covered

{''.join([table(df, '18D', '1.1 18D 摘要（18 列）与 covered')])}
'''
    raw = '''
## 2. 完整表的原始块（不是标量特征）

| 字段 | 形状 | 含义 | 当前判断 |
|---|---|---|---|
| `canonical_state_onehot` | 2,435×16×5 | 每个 canonical pattern 的 5 状态 one-hot | 表示本体；保留为条件/模式编码，不能直接把 flatten 当语义 |
| `pattern_valid` | 2,435×16 | 哪些 pattern 行有效 | C：mask，不是特征 |
| `input_valid` | 2,435×4 | 哪些输入槽有效（k 个） | C：mask，不是特征 |
| `per_input_original` | 2,435×4×3 | 每个输入的 pair_coverage / change_fraction / influence_valid | A/B 候选的来源；按输入池化 |
| `k` | 2,435 | cut 输入数 | E：规模/上下文 |
| `covered` | 2,435 | 是否有 SAT 表 | F：覆盖记账 |

对应的 114 维标量布局（21A 使用）：state one-hot `0:80`、pattern mask `80:96`、k/4 `96`、covered `97`、per-input `98:110`、input mask `110:114`；再加 39 维结构底图 = 153 维。

完整表的 **16×5 状态本身**没有被证明是通用的木马标签；它只保留局部函数。第二十轮已表明：局部真值表可以同时出现在正例和负例中。
'''
    body = head + raw
    body += '\n\n' + table(df, 'FULL', '3. 完整表派生的 26 个标量')

    body += '''

## 4. 重复/恒等关系（避免重复堆列）

- `feasible_fraction` = `forced_fraction`（当前数据上所有 feasible 都已 decided）。
- `ones_on_forced` = `frac_ones_on_forced`。
- `max_input_influence` = `input_change_fraction_max`。
- `n_inputs` = `k`；`k_over_4` = `k/4`。
- `n_patterns` = `2^k`（k>0；未展开时 0）。
- `n_forced` = `n_forced_zero + n_forced_one`。
- `input_change_fraction_mean` 与 `change_on_comparable` 的 Spearman 约 0.97。
- `n_forced` 与 k/`n_inputs` 的 Spearman 约 0.82；`max_input_influence` 与 input change 的 Spearman 约 0.83。
- 因此不能把 `n_forced`、`n_inputs`、`n_patterns`、`k_over_4` 当作四个独立功能证据。

## 5. 当前作用判断（结论汇总）

### A. 可作为条件候选

- `change_on_comparable`（18D）
- `input_change_fraction_mean`（完整表派生）

证据：固定 comb_output+k=4 后 AUC 约 **0.739/0.733**、AP 约 **0.214/0.201**（prevalence 2.84%）；但只在 INV/XOR/MX 中成立（AUC 0.660/0.688/0.694），AND/OR 反向（AUC 0.446/不可稳定估计），beta family 反向（AUC 0.292）。  
**用法**：gate-conditioned/interaction，不做全局无条件列。

### B. 次级候选

- `max_input_influence`（18D）
- `input_change_fraction_max`（完整表派生；与前者重复）

证据：k=4 的 AUC 约 0.711，但 AP 仅 0.082；在 INV/XOR/MX 有信号，AND/OR 反向，XOR 中常为常数 1。**只作补充，不与 A 重复堆列。**

### C. 只作元数据/覆盖

`k_over_4`、`k`、`n_inputs`、`n_patterns`、`pattern_valid`、`input_valid`、`covered`、`determinism_*`、`influence_valid`、`complete_*`、`feasibility_known_fraction`。  
用途：mask、分层、归一化、覆盖记账；不要当功能语义。

### D. 证据不足/接近随机

`ones_on_forced`、`frac_ones_on_forced`、`comparable_pair_fraction`、`n_distinct_states`、`state_entropy`、`input_pair_coverage_*`、`n_inputs_change_fraction_positive`（k 控制后 AUC 0.531）、`n_inputs_influence_valid_positive`。

### E. 规模/混杂，不应作为 SAT 语义

`n_forced`、`n_forced_zero`、`n_forced_one`、`n_forced` 的归一化版本、`n_patterns`、`k_over_4`、`n_inputs`。  
它们原始看似突出（`n_forced` AUC 0.746），但固定 comb_output+k=4 后 AUC 约 0.639/0.614/0.522；与表大小/k 强相关。

### F. 覆盖伪信号

`covered`：37/37 正例覆盖，负例也有 2,254/2,398；仅用覆盖排序的 AP 接近 prevalence。覆盖不是瓶颈，也不能作为增益证据。

### G/H. 常量或无信息/方向不稳定

恒定列：`feasibility_known_fraction`、`undecided_fraction`、`determinism_on_feasible`、`determinism_valid`、`ones_valid`、`influence_valid`、`partial_forcing`、`has_unknown`。  
不稳定/反向：`infeasible_fraction`、`n_infeasible`、`frac_infeasible`、`n_forced_one`（beta/AND）。

## 6. 数值与解释边界

- 未定义 AUC/AP（常量列）在 CSV 中写空字段、在 JSON 中写 `null`，不写 `NaN`。
- 所有统计来自现有 `real.npy` 和 `candidate_boundary_repr.npz`，没有新增 SAT、训练或测试调参。
- 单特征 AUC/AP 是描述性的，不是因果识别；正例只有 37 个，且 gate/k 高度不平衡。
- 所有正例 covered、全为 comb_output；不声称跨 host 泛化。
- 具体表：`feature_overall.csv`、`feature_within_inj.csv`、`feature_within_comb_output.csv`、`feature_gate_k4.csv`、`feature_by_family.csv`、`feature_by_gate.csv`、`feature_matched_strata.csv`。
- 脚本：`feature_diff.py`、`feature_diff_extra.py`、`feature_dictionary.py`。

## 7. 一句话判断

**当前最值得保留的是 gate-conditioned 的 `input_change_fraction_mean` / `change_on_comparable`；`max_input_influence` 次之；`n_forced` 等表行数特征是 k/gate 混杂的表象；判定列、covered 和常量 validity 列没有可用的节点级语义。**
'''
    OUT_MD.write_text(body, encoding='utf-8')
    pd.DataFrame([dict(feature=k, group=v[0], definition=v[1], code=v[2],
                       judgment=JUDGMENTS[v[2]], note=v[3])
                  for k, v in DEFS.items()]).to_csv(
        T / 'feature_dictionary.csv', index=False, encoding='utf-8-sig')
    print(dict(status='written', features=len(DEFS), markdown=str(OUT_MD), rows=len(df)))


if __name__ == '__main__':
    main()

