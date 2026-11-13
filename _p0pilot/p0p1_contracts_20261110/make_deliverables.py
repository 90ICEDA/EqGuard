"""P0/P1/P2/P3 deliverables: contracts, matrices, GT V5, consistency check."""
import csv, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
D = R / '_p0pilot/p0p1_contracts_20261110'; D.mkdir(exist_ok=True)
DOC = R / '10.15/00_说明'

# ---------------- P0 A ----------------
(json.dump(dict(
    goal='仅确认 L_cone 开关的收益', arms=['N', 'NC'], seeds=[42, 1, 2], runs=6, updates=200,
    unique_factor='L_cone on/off', frozen=['encoder', '39v3 features', 'graph/splits', 'init', 'node indices/exposure',
                                          'Adam', '200 updates', 'AMP BF16', 'model selection', 'threshold'],
    stop=['non-finite loss/grad', 'save failure', 'asset hash mismatch'],
    status='contract_only_not_run'), open(D / 'RUN_CONTRACT_A.json', 'w', encoding='utf-8'), indent=2))

items = [
    ('encoder', 'GIN 3层 hidden128', 'same', 'L_cone runner'),
    ('features', '39v3 first25 raw, 25:39 clip', 'same', 'group_A mean/std'),
    ('graph/splits', 'group_A 535069 nodes / aux154', 'same', 'group_A.npz'),
    ('init', 'init_s42/1/2', 'same', 'per seed'),
    ('node indices', '502 pos + 8192 common + 144 H; 200 steps', 'same', 'sup_A.npz'),
    ('cones', '11187 (558/10629), per-source matched', 'same', 'cones_A.npz'),
    ('optimizer', 'Adam 2e-4 wd1e-3', 'same', 'runner'),
    ('updates', '200', 'same', 'runner'),
    ('AMP', 'BF16 autocast', 'same', 'runner'),
    ('selection', 'val_common mean per-view AP', 'same', 'hoco val 39 views'),
    ('threshold', 'val_common 80/90/95', 'same', 'evaluation'),
    ('L_cone', 'off', 'on', 'unique factor'),
]
with (D / 'A_CONFIG_MATRIX.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['item', 'N', 'NC', 'same_or_diff', 'evidence'])
    for x in items: w.writerow(x)

(D / 'CONE_LABEL_CONTRACT_A.md').write_text("""# CONE_LABEL_CONTRACT_A

- D 锥：历史 DFF 的 D 输入锥（组合逻辑反向可达至 PI/DFF-Q 边界）；PO 锥：PO 驱动锥。
- 身份 `(split,view,cone_id)`；完整成员与 trusted∧physical 成员分列。
- 标签：含可信正节点 → 正；全部可信成员为负 → 负；否则 unknown。
- **无可信正节点 ≠ 可信负锥**；unknown 不默认负。
- 区域标签来源为制造来源/既有可信标签，不是功能影响 GT。
- 正负锥分母分别记录；允许重叠，重叠计数只作属性。
""", encoding='utf-8')

(D / 'A_REUSE.md').write_text("""# A_REUSE（旧 N 复用判定）

| 运行 | 资产 | 冻结项 | 复用 |
|---|---|---|---|
| L_cone N seed42 | group_A 502/11187 | 一致 | ✅ 可复用 |
| L_cone N seed1/2 | group_A | 一致 | ✅ 可复用 |
| L_cone NC seed42/1/2 | group_A | 一致 | ✅ 可复用 |
| v5 折 N/NC | 折资产 614/703/648 | 不同 | ❌ 不复用 |
| 四组 A-N | group_A 502/11187 | 一致 | ✅ 可复用（同一 runner） |

- 结论：A 的 6 次（N/NC×3 seed）已有 L_cone 对应运行，**新训练=0**；仅需按 A_METRICS 重评。
""", encoding='utf-8')

(D / 'A_METRICS.md').write_text("""# A_METRICS

- 节点 AP；DFF 锥 AP、PO 锥 AP；Top-1%/5%；正常误报（trusted/allphys、视图报警）。
- 预算：节点 502/8192/144；锥 11187（558 正/10629 负），分开报告。
- 聚合：逐视图 AP → 源宏 → 三种子配对均值/SD。
- 预计算锥成员索引；禁止逐步 unique/重建。
""", encoding='utf-8')

# ---------------- P1 C ----------------
(D / 'LRO_DIFF_C.md').write_text("""# LRO_DIFF_C（v5 vs C）

| 项 | v5 | C |
|---|---|---|
| 留出 | abc/aig/nand 三折 | h=abc 单折 |
| A 组成 | abc/id/opt（各折不同） | id/opt |
| B 组成 | A+aig/nand | id/opt+aig/nand |
| 归一化 | 各折拟合 | 共同 A 拟合 |
| 验证 | 折内 val | id/opt 共同 val 39 视图 |
| 锥 | 5 源/折混合 | 10,742（358/10,384） |
| 命名 | heldout_recipe_v5 | hoco h=abc |

结论：v5 与 C 设计不同，v5 结果不能作 C 正式报告。
""", encoding='utf-8')

rows = []
for seed in (42, 1, 2):
    for arm in ('N', 'NC'):
        for fold in ('abc', 'aig', 'nand'):
            rows.append(dict(seed=seed, arm=arm, fold=fold, v5_status='not_reusable',
                             reason='不同留出/组成/归一化/锥预算', c_status='needs h=abc assets'))
with (D / 'C_REUSE_MATRIX.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

(json.dump(dict(
    design='h=abc single-fold 2x2, seeds 42/1/2',
    folds=['h=abc'], arms=['A-N', 'A-NC', 'B-N', 'B-NC'],
    data=dict(A='hoco_A.npz 106 views/358012 nodes', B='hoco_B.npz 190/1072063',
              val='hoco_val.npz 26 views/277554', norm='A orig+trans fit sha ec8fded7',
              positives=287, cones='10742 (358/1084)'),
    status='assets_exist_training_exists_for_seed42/1/2'), open(D / 'C_DATA_LIST.json', 'w', encoding='utf-8'), indent=2))

with (D / 'C_RUN_MATRIX.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['seed', 'arm', 'exists', 'reuse', 'gpu_new'])
    for seed in (42, 1, 2):
        for arm in ('A-N', 'A-NC', 'B-N', 'B-NC'):
            w.writerow([seed, arm, 'yes', 'yes (hoco runs)', '0'])

(D / 'C_EVAL_GAP.md').write_text("""# C_EVAL_GAP

已有：节点 AP/Top-k/正常 FPR/A-B（hoco 三 seed）。
缺：DFF/PO 锥 AP、预算召回、覆盖、CEC 范围、失败分层；
未见实现 vs 未见流程（同源/独立源）未分开。
""", encoding='utf-8')

# ---------------- P2 B GT ----------------
p = json.loads((H / 'PANEL_STATUS.json').read_text(encoding='utf-8'))
p['cec_plan'] = 'done'; p['gt'] = 'partial (host-level only)'
(H / 'PANEL_STATUS.json').write_text(json.dumps(p, indent=2), encoding='utf-8')
s = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
s['gt'] = '20-combo panel: host-level GT only'
s['cec'] = '40/40 PASS'
(H / 'STATUS.json').write_text(json.dumps(s, indent=2), encoding='utf-8')
# strip BOM from CEC json/csv
for f in ('CEC_STAGE3A.json', 'CEC_STAGE3B.json', 'CEC_STAGE3A.csv', 'CEC_STAGE3B.csv'):
    q = H / f
    if q.exists():
        t = q.read_text(encoding='utf-8-sig')
        q.write_text(t, encoding='utf-8')
g3 = json.loads((H / 'GT_AVAILABILITY_V3.json').read_text(encoding='utf-8'))
g5 = dict(host_status=[dict(host='rs232t1000', status='verified_example'),
                       dict(host='s15850t100', status='can_attempt'),
                       dict(host='s35932t200', status='can_attempt'),
                       dict(host='s38417t100', status='missing'),
                       dict(host='s38584t100', status='can_attempt')],
          endpoint_example=dict(host='rs232t1000', design='tr45', rows=g3['rows'], counts=g3['counts']),
          panel_gt='not_built', note='CEC equivalence is not functional impact GT')
(H / 'GT_AVAILABILITY_V5.json').write_text(json.dumps(g5, indent=2), encoding='utf-8')
with (H / 'GT_AVAILABILITY_V5.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'status'])
    for x in g5['host_status']: w.writerow([x['host'], x['status']])
(D / 'FUNCTIONAL_GT_DESIGN.md').write_text("""# 功能影响 GT 设计（不执行）

- 与制造来源区域标签分开命名；来源=插入位置、端点对应、影响证据。
- 影响证据需独立于弱 MIL/结构可达/CEC 等价；CEC 40/40 只证实现等价。
- unknown 不默认负；面板级 GT 未建。
""", encoding='utf-8')
print('files written', len(list(D.iterdir())))
