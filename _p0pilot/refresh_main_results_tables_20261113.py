"""Render detailed tables from the frozen evaluations and prediction files."""
import csv
import itertools as it
import json
import math
import statistics as st
from pathlib import Path

import numpy as np

P = Path(__file__).resolve().parent
DOC = P.parent / '10.15/00_说明/EqGuard三项主实验结果汇报_20261113.md'
SEEDS = (42, 1, 2)
ARMS = ('N', 'NC')
POINTS = ('best', 'last')
FOLDS = ('abc', 'aig', 'nand')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def table(head, data):
    return '\n'.join('| ' + ' | '.join(map(str, row)) + ' |' for row in [head, ['---'] * len(head), *data])


def point(p):
    return '最佳' if p == 'best' else '末步'


def pair(values, fmt='.2f'):
    return ' → '.join(format(float(v), fmt) for v in values)


def task1():
    base = P / 'seed42_nc_eval_v3_20261109'
    agg = read(base / 'AGG_V3.json')['metrics']
    raw = read(base / 'EVAL_V3_ALL.json')
    definitions = [('val_ap', '变换验证节点 AP', '.4f'), ('test_ap', '变换测试节点 AP', '.4f'),
                   ('test_top1', '测试节点 Top-1% 召回', '.2%'),
                   ('test_normal_node_fpr', '测试正常对照可信节点 FPR', '.2%'),
                   ('test_normal_alarm', '测试正常对照整图 FPR', '.2%')]
    data = [[label, *[pair((agg[f'{p}|{key}'][a] for a in ARMS), fmt) for p in POINTS]]
            for key, label, fmt in definitions]
    each = [[seed, *[pair((raw[f'{a}_s{seed}_{p}']['test']['ap_view'] for a in ARMS), '.4f') for p in POINTS]]
            for seed in SEEDS]
    fpr = []
    for p, q in it.product(POINTS, ('0.8', '0.9', '0.95')):
        def mean_a(key, a):
            return st.mean(raw[f'{a}_s{s}_{p}']['equal_recall']['A_val_transfer'][q][key] for s in SEEDS)
        fpr.append([point(p), format(float(q), '.0%'), pair((mean_a('test_recall', a) for a in ARMS), '.2%'),
                    pair((mean_a('test_fpr', a) for a in ARMS), '.2%'),
                    pair((agg[f'{p}|B_test_recall@{q}'][a] for a in ARMS), '.2%'),
                    pair((agg[f'{p}|B_test_fpr@{q}'][a] for a in ARMS), '.2%')])
    return '\n\n'.join([
        '### 测试节点 AP 和 FPR 明细',
        table(['指标', '最佳 N→NC', '末步 N→NC'], data),
        table(['种子', '测试节点 AP 最佳 N→NC', '测试节点 AP 末步 N→NC'], each),
        '验证阈值迁移用验证集确定阈值，表中实际测试召回可能偏离目标。测试同召回在测试分数上离线定阈值，只用于比较排序代价。正常对照是 40 个有制造身份的 ctl 视图，可信节点 FPR 与整图报警分开。',
        table(['检查点', '目标召回', '验证阈值迁移后召回', '验证阈值迁移后 FPR', '测试同召回实际值', '测试同召回 FPR'], fpr)])


def task2():
    base = P / 'task2_nokeep_audit_20261113'
    data = []
    for label, name in [('s38417', 's38417t100/injdelta'), ('s38584', 's38584t100/injdelta'),
                        ('s38584_alpha', 's38584t100/injalpha'), ('s38417t300_beta', 's38417t300/injbeta')]:
        index = {(r['recipe'],r['keep'],r['kind'],r['point'],r['arm']):r for r in rows(base/f'{label}_N_NC_MEANS.csv')}
        assert len(index) == 32
        detail = []
        for f,p,k in it.product(('abc','nand'),POINTS,('D','PO')):
            for keep in ('keepcur','keepnone'):
                both = [index[f,keep,k,p,a] for a in ARMS]
                detail.append([f, 'keep' if keep=='keepcur' else 'no-keep',point(p),k,
                               *[pair((r[m] for r in both), fmt) for m,fmt in
                                 [('cone_ap','.4f'),('top5','.2%'),('recall512','.2%'),('equal_fp','.2f'),
                                  ('equal_unknown','.2f'),('equal_gates',',.2f')]]])
        data.extend([f'#### {name}',table(['recipe','状态','检查点','端点','锥 AP','Top-5','512 门召回','等召回误报数','等召回未知数','等召回去重门'],detail)])
    clean = rows(base/'CLEAN_PAIRED_V2/PAIRED_SUMMARY.csv')
    assert len(clean)==16 and all(r['keep_alarms']==r['none_alarms']=='3' for r in clean)
    alarms = {(r['host'],r['recipe'],r['point'],r['arm']):r for r in clean}
    clean_table = []
    for h,f,p in it.product(('s38417t100','s38584t100'),('abc','nand'),POINTS):
        clean_table.append([h,f,point(p),'3/3 → 3/3（N、NC 各自）',
                            *[pair((alarms[h,f,p,a][m] for m in ('keep_fraction','none_fraction')),'.2%') for a in ARMS]])
    return '\n\n'.join(['### 四格定位与干净网表误报明细',
        '逐源按三个种子平均，每格为 N→NC。相邻 keep／no-keep 行可对比同一模型。锥 AP 基于各配对视图共同已证的正负端点。当前配对面板缺少跨视图可比的节点级真值，测试节点 AP 和含木马视图的节点 FPR 留空。',
        *data, '#### 干净网表整图 FPR',
        '每个宿主、recipe、检查点及模型臂各有三个种子。下表为 keep→no-keep，报警节点占比的分母为对应干净网表的全部物理节点。',
        table(['宿主','recipe','检查点','整图误报次数','N 报警节点占比','NC 报警节点占比'],clean_table)])


def task3_node_fpr():
    base=P/'heldout_recipe_v5_eval2_20261109'
    v5=P/'heldout_recipe_v5_20261109'
    maps=P/'heldout_recipe_v4_20261109'
    closure=read(base/'CLOSURE.json')
    scored=read(P/'heldout_v5_endpoint_replay_20261112/SUMMARY.json')
    import hashlib
    data=[]
    for f in FOLDS:
        fold='ys_'+f
        with np.load(maps/f'{fold}_val_map.npz') as z:
            val_rows=z['rows']; vp=z['trusted'] & (z['y']==1)
        with np.load(maps/f'{fold}_test_map.npz') as z:
            test_rows=z['rows']; y=z['y']; trusted=z['trusted']; physical=z['physical']
        assert physical[trusted].all()
        pos, neg=trusted & (y==1), trusted & (y==0)
        grouped={}
        for audit in scored['audits'][f]['runs']:
            s,a,p=(audit[k] for k in ('seed','arm','point'))
            run=v5/fold/a
            if s!=42: run/=f'seed{s}'
            pred=run/f'{p}_pred.npz'
            assert hashlib.sha256(pred.read_bytes()).hexdigest()==audit['native_prediction_sha256']
            with np.load(pred) as z:
                assert np.array_equal(z['val_rows'],val_rows) and np.array_equal(z['test_rows'],test_rows)
                val=z['val']; margin=z['test']
            if s==42:
                full=base/f'{fold}_{a}_{p}_testpred.npz'
                assert hashlib.sha256(full.read_bytes()).hexdigest()==audit['scored_prediction_sha256']
                with np.load(full) as z:
                    ix=np.searchsorted(z['rows'],test_rows)
                    assert np.array_equal(z['rows'][ix],test_rows)
                    assert np.array_equal(z['y'][ix],y) and np.array_equal(z['trusted'][ix],trusted)
                    margin=z['scores'][ix]
            threshold=np.sort(val[vp])[::-1][math.ceil(.95*vp.sum())-1]
            same=np.sort(margin[pos])[::-1][math.ceil(.95*pos.sum())-1]
            result=[(float((margin[pos]>=t).mean()),float((margin[neg]>=t).mean())) for t in (threshold,same)]
            if s==42:
                old=closure[f'{fold}_{a}_{p}']['AB_heldout']['0.95']
                for (r,fp),k in zip(result,('A','B')):
                    assert math.isclose(r,old[k]['test_recall']) and math.isclose(fp,old[k]['test_fpr'])
            grouped[p,a,s]=result
        for p in POINTS:
            vals=[pair((st.mean(grouped[p,a,s][which][m] for s in SEEDS) for a in ARMS),'.2%')
                  for which,m in it.product(range(2),range(2))]
            data.append([f,point(p),f'{pos.sum():,}／{neg.sum():,}',*vals])
    return table(['recipe','检查点','测试可信正／负节点','验证阈值迁移后召回','验证阈值迁移后 FPR','测试同召回实际值','测试同召回 FPR'],data)


def task3():
    base=P/'heldout_v5_endpoint_replay_20261112'
    raw=rows(base/'BY_VIEW.csv')
    agg={(r['fold'],r['point'],r['kind'],r['metric']):r for r in rows(base/'TASK3_V5_BY_RECIPE.csv')}
    data=[]
    for f,p,k in it.product(FOLDS,POINTS,('D','PO')):
        picks=[r for r in raw if (r['fold'],r['point'],r['kind'])==(f,p,k) and int(r['positive'])>0]
        denom=[r for r in picks if int(r['negative'])>0]
        support={a:len({r['source'] for r in denom if r['arm']==a}) for a in ARMS}
        assert support['N']==support['NC']
        rates=pair((st.mean(float(r['allpos_fp'])/int(r['negative']) for r in denom if r['arm']==a) for a in ARMS),'.2%') if denom else 'NA'
        cells=[pair((agg[f,p,k,m][a] for a in ARMS),fmt) for m,fmt in
               [('top_5','.2%'),('allpos_fp','.2f'),('allpos_unknown','.2f'),('allpos_gates',',.2f')]]
        data.append([f,point(p),k,*cells,rates,support['N']])
    return '\n\n'.join(['### 留出测试节点 FPR 和端点检查开销明细',
        '节点 FPR 使用保存的 v5 预测和留出折可信物理节点，分母含同 recipe 的正常对照和含插入源视图中的可信负节点。阈值由折内验证集约 95% 召回确定。测试同召回只用于离线诊断。各格三种子等权，seed42 与原离线汇总复核一致。',
        task3_node_fpr(),
        '端点等召回用每源全部已证正端点及末位同分项。端点 FPR 为已证误报数除以该源已证负端点数，只在正负支持均非零的源上等权平均。其余端点指标沿用正式主表的含正源口径。',
        table(['recipe','检查点','端点','Top-5','等召回误报数','等召回未知数','等召回去重门','等召回端点 FPR','FPR 可评价源数'],data)])


def main():
    content=DOC.read_text(encoding='utf-8')
    for marker, block in [('[统一消融评价修正]', task1()), ('[第二家族核查与最小补齐方案]',task2()),
                          ('[三折主结果]',task3())]:
        assert content.count(marker)==1 and block.splitlines()[0] not in content
        content=content.replace(marker,block+'\n\n'+marker,1)
    DOC.write_text(content,encoding='utf-8')
    print('three detailed sections written')


if __name__=='__main__':
    main()
