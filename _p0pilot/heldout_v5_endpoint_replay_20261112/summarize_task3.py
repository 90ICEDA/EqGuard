"""Assemble Task 3 tables from verified held-out v5 prediction evaluations."""
import csv
import hashlib
import itertools
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
DOCS = OUT.parents[1] / '10.15' / '00_说明'
FOLDS = ('abc', 'aig', 'nand')
POINTS = ('best', 'last')
SEEDS = (42, 1, 2)
ARMS = ('N', 'NC')
KINDS = ('D', 'PO')
RECALL = ('top_1', 'top_5', 'top_10', 'recall_512')
ENDPOINT_METRICS = (*RECALL, 'gates_512', 'allpos_fp', 'allpos_unknown', 'allpos_gates')
LABEL = {'best': '最佳', 'last': '末步', 'top_1': 'Top-1', 'top_5': 'Top-5', 'top_10': 'Top-10',
         'recall_512': '512 门召回', 'gates_512': '512 门实际门数', 'allpos_fp': '等召回误报',
         'allpos_unknown': '等召回未知锥', 'allpos_gates': '等召回去重门', 'node_ap': '节点 AP'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def stats(n, nc):
    if not n:
        return dict(zip(('N','NC','delta','delta_sd','pos','tie','neg'), (None,)*7))
    assert len(n) == len(nc) == len(SEEDS)
    differences = [b-a for a,b in zip(n,nc)]
    positive = sum(x > 1e-12 for x in differences)
    negative = sum(x < -1e-12 for x in differences)
    return dict(N=st.mean(n), NC=st.mean(nc), delta=st.mean(differences), delta_sd=st.stdev(differences),
                pos=positive, tie=len(SEEDS)-positive-negative, neg=negative)


def fmt(metric, r):
    if r['N'] is None:
        return '—'
    if metric in RECALL:
        return f"{r['N']:.2%}→{r['NC']:.2%}"
    digits = 5 if metric == 'node_ap' else 2
    return f"{r['N']:,.{digits}f}→{r['NC']:,.{digits}f}"


def md_table(header, rows):
    return '\n'.join('| ' + ' | '.join(str(x) for x in row) + ' |' for row in [header, ['---']*len(header), *rows])


def assemble():
    evaluated = OUT / 'BY_VIEW.csv'
    node_results = OUT.parent / 'heldout_recipe_v5_eval2_20261109' / 'SEEDS3.json'
    summary_path = OUT / 'SUMMARY.json'
    summary = read(summary_path)
    node = read(node_results)
    assert hashlib.sha256(node_results.read_bytes()).hexdigest() == summary['original_node_eval_sha256']
    assert summary['verified_sample_pairs'] == 9
    endpoint = {}
    support = {}
    for r in csv_rows(evaluated):
        fold, point, seed, arm, kind, source = (r[k] for k in ('fold','point','seed','arm','kind','source'))
        key = fold,point,int(seed),arm,kind,source
        assert key not in endpoint
        endpoint[key] = r
        counts = tuple(int(r[k]) for k in ('positive','negative','unknown'))
        group = fold,kind,source
        assert support.setdefault(group, counts) == counts
        assert int(r['gates_512']) <= 512
        if counts[0]:
            assert int(r['allpos_endpoints']) == counts[0]+int(r['allpos_fp'])+int(r['allpos_unknown'])
        else:
            assert all(not r[k] for k in (*RECALL, 'allpos_fp', 'allpos_unknown', 'allpos_gates'))
    assert len(endpoint) == 360
    sources = {f: sorted({s for ff, _, s in support if ff==f}) for f in FOLDS}
    assert all(sources[f] == sources['abc'] and len(sources[f]) == 5 for f in FOLDS)
    primary, per_source, paired = {}, {}, []
    for f, p in itertools.product(FOLDS, POINTS):
        for seed, arm in itertools.product(SEEDS, ARMS):
            record = node[f'ys_{f}_{arm}_{seed}_{p}']
            assert set(record['heldout_src']) == set(sources[f])
            assert math.isclose(st.mean(record['heldout_src'].values()), record['heldout_macro'], abs_tol=1e-12)
        for kind, metrics in [('node', ('node_ap',)), *((k, ENDPOINT_METRICS) for k in KINDS)]:
            for metric in metrics:
                seed_values = {a: defaultdict(list) for a in ARMS}
                for s in sources[f]:
                    values = {a: [] for a in ARMS}
                    for seed in SEEDS:
                        for a in ARMS:
                            val = (node[f'ys_{f}_{a}_{seed}_{p}']['heldout_src'][s] if kind=='node'
                                   else endpoint[f,p,seed,a,kind,s][metric])
                            if val == '':
                                continue
                            values[a].append(float(val))
                            seed_values[a][seed].append(float(val))
                        paired.append(dict(fold=f, point=p, kind=kind, source=s, metric=metric, seed=seed,
                                           N=values['N'][-1] if values['N'] else None,
                                           NC=values['NC'][-1] if values['NC'] else None))
                    per_source[f,p,kind,s,metric] = stats(values['N'], values['NC'])
                primary[f,p,kind,metric] = stats(*[[st.mean(seed_values[a][seed]) for seed in SEEDS] for a in ARMS])

    for r in summary['aggregate']:
        for k in (*RECALL, 'allpos_fp', 'allpos_unknown', 'allpos_gates'):
            t = primary[r['fold'],r['point'],r['kind'],k]
            assert all(math.isclose(t[key], r['metrics'][k][key], abs_tol=1e-12) for key in ('N','NC','delta'))
    for r in summary['node_ap_pairs']:
        assert all(math.isclose(node[f"ys_{r['fold']}_{a}_{r['seed']}_{r['point']}"]['heldout_macro'],r[a],abs_tol=1e-12) for a in ARMS)

    write_csv(OUT / 'TASK3_V5_BY_RECIPE.csv', [dict(fold=f, point=p, kind=k, metric=m, **v)
             for (f,p,k,m),v in primary.items()])
    write_csv(OUT / 'TASK3_V5_BY_SOURCE.csv', [dict(fold=f, point=p, kind=k, source=s, metric=m,
             positive=support[f,k,s][0] if k in KINDS else None, **v) for (f,p,k,s,m),v in per_source.items()])
    write_csv(OUT / 'TASK3_V5_SEED_PAIRS.csv', paired)
    return primary, per_source, support, sources


def write_tables(primary, per_source, support, sources):
    ap = []
    for f,p in itertools.product(FOLDS,POINTS):
        r = primary[f,p,'node','node_ap']
        ap.append([f,LABEL[p],fmt('node_ap',r),f"{r['delta']:+.5f} ± {r['delta_sd']:.5f}",f"{r['pos']}/{r['tie']}/{r['neg']}"])
    metrics = (*RECALL, 'allpos_fp', 'allpos_unknown', 'allpos_gates', 'gates_512')
    endpoint = [[f,LABEL[p],k,*[fmt(m,primary[f,p,k,m]) for m in metrics]]
                for f,p,k in itertools.product(FOLDS,POINTS,KINDS)]
    main = md_table(['留出 recipe','检查点','节点 AP','配对差均值 ± 样本 SD','升／平／降种子数'],ap)
    main += '\n\n' + md_table(['留出 recipe','检查点','端点',*[LABEL[m] for m in metrics]],endpoint)
    detail = ['# 任务三逐独立源结果', '', '留出宿主均为 s38584t100。箭头为 N → NC，按三个配对种子取均值。无正端点时召回和等召回记为 —。512 门实际用门仍报告。']
    for f in FOLDS:
        detail.extend(['',f'## {f} 留出','',md_table(['独立源','检查点','节点 AP'],[
            [s.split('__')[1].split('_')[0],LABEL[p],fmt('node_ap',per_source[f,p,'node',s,'node_ap'])]
            for s,p in itertools.product(sources[f],POINTS)]),'',md_table(
            ['独立源','检查点','端点','可信正数',*[LABEL[m] for m in metrics]], [
                [s.split('__')[1].split('_')[0],LABEL[p],k,support[f,k,s][0],*[fmt(m,per_source[f,p,k,s,m]) for m in metrics]]
                for s,p,k in itertools.product(sources[f],POINTS,KINDS)])])
    with (DOCS / '任务三heldout_v5逐独立源表_20261113.md').open('x',encoding='utf-8') as f:
        f.write('\n'.join(detail)+'\n')
    with (OUT / 'TASK3_V5_RECIPE_TABLES.md').open('x',encoding='utf-8') as f:
        f.write(main+'\n')
    print(main)


if __name__ == '__main__':
    write_tables(*assemble())
