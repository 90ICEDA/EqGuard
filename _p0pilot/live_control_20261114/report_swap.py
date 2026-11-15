"""Write the paired result report from the saved audit and metric tables."""
from run_swap import OUT, ROOT, read, rows


def percent(x):
    return f'{100*float(x):.2f}%' if x else '—'


def main():
    pre = read(OUT/'PREFLIGHT.json')
    audit = read(OUT/'INDEPENDENT_AUDIT.json')
    results = {arm:read(OUT/arm/'RESULT.json') for arm in ('base','swap')}
    assert all(r['init_sha']==audit['init_sha'] and r['schedule_sha']==audit['schedule_sha']
               for r in results.values())
    metrics = {(r['arm'],r['point'],r['calibration'],r['recipe']):r for r in rows(OUT/'NODE_SUMMARY.csv')}
    ep = {(r['arm'],r['point'],r['kind'],r['recipe']):r for r in rows(OUT/'ENDPOINT_SUMMARY.csv')}
    text = [
        '# 可达正常难负例等预算对照（seed42）', '',
        '复用 12 个已完成等价验证的训练侧改写视图。两组均在原始侧训练前向中附带这 12 个独立图组件，以固定消息传递和批归一化所见的图集合。基线组沿用 G0 索引，替换组每次用一个可达正常难负例替换一个同宿主的可信物理负例。旧冻结 NC 同时离线复评，用于识别共同附加图上下文与旧训练配置之间的差异。',
        '',
        f"每组 200 步。原始侧每步 {pre['orig_positives']} 正、{pre['orig_budget']-pre['orig_positives']} 负，"
        f"变换侧每步 {pre['trans_positives']} 正、{pre['trans_budget']-pre['trans_positives']} 负。"
        f"共替换 {pre['replacements']} 个槽位，两个宿主各 110 次，每步每宿主最多一次。"
        "32 个节点全部消费，s15850 的 10 个节点各 11 次，s35932 的 22 个节点各 5 次。"
        f"其中 {pre['same_gate']}/220 同简化门型，其余同宿主但门型不同。"
        "正例、变换侧索引及锥监督合同相同。24 个验证难负例仅用于评价。",
        '',
        f"同 seed42 初始化、39 维 v3、改进双分支和固定 L_cone。最佳检查点按原验证节点 AP 选取。"
        f"配对基线最佳步 {results['base']['best_step']}，替换组最佳步 {results['swap']['best_step']}，末步均为 200。",
        '',
        '## 含木马测试网表节点评价', '',
        '验证阈值由原验证可信物理正例确定。测试等召回阈值仅作事后比较。原生负例及其困难子集复用冻结血缘面板，FPR 先按源内视图均值再对源平均。角色召回按有角色证据的节点汇总。',
        '',
        '| 阈值 | 检查点 | 组 | 节点 AP | 木马召回 | 原生 FPR | 原生困难 FPR | 触发 | 载荷 | 载荷选择 | 验证改写难负例报警 |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for cal in ('val','test'):
        for point in ('best','last'):
            for arm in ('historical','base','swap'):
                r = metrics[arm,point,cal,'all']
                vals = [percent(r[k]) for k in ('ap','test_recall','native_fpr','hard_fpr','trigger_recall',
                                                'payload_recall','payload_select_recall')]
                vals.append(f"{r['val_control_fp']}/24" if r['val_control_fp'] else '—')
                text.append('| '+' | '.join([cal,point,arm,*vals])+' |')
    text.extend(['','## 独立 D/PO 端点定位','',
        '按冻结最大值打分与原 512 门去重检查队列。按源平均，正端点数为面板支持量。全正召回列分别报告已证负端点和未知端点的检查量。',
        '',
        '| 检查点 | 组 | 端点 | 正端点 | 512 门召回 | 去重门数 | 全正召回负锥 | 全正召回未知锥 |',
        '|---|---|---|---:|---:|---:|---:|---:|'])
    for point in ('best','last'):
        for arm in ('historical','base','swap'):
            for kind in ('D','PO'):
                r = ep[arm,point,kind,'all']
                vals = [point,arm,kind,r['positive'],percent(r['recall_512']),
                        *(f'{float(r[k]):.2f}' for k in ('gates_512','allpos_fp','allpos_unknown'))]
                text.append('| '+' | '.join(vals)+' |')
    text.extend(['','逐源和逐 recipe 证据见 `_p0pilot/live_control_20261114/nc_swap_seed42` 的 `NODE_BY_VIEW.csv`、'
        '`NODE_SUMMARY.csv`、`ENDPOINT_BY_VIEW.csv`、`ENDPOINT_SUMMARY.csv`。'
        '采样证据见 `PREFLIGHT.json`、`SWAPS.csv`、`INDEPENDENT_AUDIT.json`。'
        '本轮复用现有网表和标签，无新增网表、SAT 或 CEC。',''])
    (ROOT/'10.15/00_说明/可达正常难负例等预算对照_20261114.md').write_text('\n'.join(text),encoding='utf-8')


if __name__=='__main__':
    main()
