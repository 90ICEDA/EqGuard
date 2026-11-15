"""Summarize per-view evidence with explicit macro and pooled denominators."""
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean

OUT = Path(__file__).resolve().parent


def read(name):
    with (OUT / name).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def groups(rows, *keys):
    out = defaultdict(list)
    for row in rows:
        out[tuple(row[k] for k in keys)].append(row)
    return out


def rate(rows, hit, denom):
    n = sum(int(r[denom]) for r in rows)
    return round(100 * sum(int(r[hit]) for r in rows) / n, 2) if n else None


def avg(rows, key, digits=3):
    a = [float(r[key]) for r in rows if r[key] != '']
    return round(mean(a), digits) if a else None


def joint():
    print('joint: AP, pos R, trigger R, payload R, select R, control FPR, added FPR')
    for (arm, point), rr in groups(read('JOINT_BY_VIEW.csv'), 'arm', 'point').items():
        trojan = [r for r in rr if r['kind'] == 'trojan']
        normal = [r for r in rr if r['kind'] == 'control']
        ap = [avg(g, 'node_ap', 10) for g in groups(trojan, 'source').values()]
        print(arm, point, round(mean(a for a in ap if a is not None), 4),
              rate(trojan, 'positive_hits', 'positives'),
              *(rate(trojan, f'{role}_hits', f'{role}_positive')
                for role in ('trigger', 'payload', 'payload_select')),
              rate(normal, 'negative_hits', 'negatives'),
              rate(normal, 'normal_primary_added_hits', 'normal_primary_added_n'))
    print('matched: target, actual, all FPR, added FPR')
    for (arm, point, target), rr in groups(read('JOINT_MATCHED_NODE_RECALL.csv'),
                                         'arm', 'point', 'target').items():
        print(arm, point, target, avg(rr, 'actual', 5), rate(rr, 'fp', 'neg'),
              rate(rr, 'added_fp', 'added'))
    print('joint D by recipe: Top-5, R512, equal recall FP, unknown, gates')
    endpoint = read('JOINT_ENDPOINTS.csv')
    for (arm, point, kind), rr in groups(endpoint, 'arm', 'point', 'kind').items():
        if kind != 'D':
            continue
        for recipe in ('abc', 'aig', 'nand'):
            matched = [r for r in rr if r['view'].endswith('__ys_' + recipe)]
            print(arm, point, recipe, *(avg(matched, k) for k in
                  ('top_5', 'recall_512', 'allpos_fp', 'allpos_unknown', 'allpos_gates')))


def half():
    print('half: AP, R, normal node FPR')
    for key, rr in groups(read('HALF_NODE_BY_VIEW.csv'), 'fold', 'arm', 'point').items():
        print(*key, avg(rr, 'ap', 4), rate(rr, 'tp', 'pos'),
              rate([r for r in rr if r['kind'] == 'control'], 'fp', 'neg'))
    print('half endpoints: Top-5, R512, eq recall FP, unknown, gates')
    for key, rr in groups(read('HALF_BY_ENDPOINT_VIEW.csv'), 'fold', 'arm', 'point', 'kind').items():
        print(*key, *(avg(rr, k) for k in ('top_5', 'recall_512', 'allpos_fp',
                                          'allpos_unknown', 'allpos_gates')))
    print('half circuit alarm: test TPR/FPR')
    aa = [r for r in read('HALF_ALARM_BY_VIEW.csv') if r['split'] == 'test']
    for key, rr in groups(aa, 'fold', 'arm', 'point', 'k').items():
        print(*key, *[avg([r for r in rr if r['kind'] == k], 'alarm') for k in ('trojan', 'control')])


if __name__ == '__main__':
    joint()
    if (OUT / 'HALF_NODE_BY_VIEW.csv').exists():
        half()
