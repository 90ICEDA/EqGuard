"""Aggregate three seeds: paired NC-N differences, mean and sample SD (no seed selection)."""
import json
import statistics as st
from pathlib import Path

OUT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\seed42_nc_ablation_20261109')
SEEDS = [42, 1, 2]

METRICS = [
    ('trans_val', 'ap_view'), ('trans_test', 'ap_view'),
    ('trans_val', 'top1'), ('trans_test', 'top1'),
    ('trans_val', 'top5'), ('trans_test', 'top5'),
    ('trans_val', 'pooled_ap'), ('trans_test', 'pooled_ap'),
    ('orig_val', 'ap_view'), ('orig_test', 'ap_view'),
    ('orig_val', 'top1'), ('orig_test', 'top1'),
]


def load(arm, seed):
    p = OUT / f'OFFLINE_{arm}_s{seed}.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


def main():
    rows, per_seed = [], {}
    for seed in SEEDS:
        n, c = load('N', seed), load('NC', seed)
        if not n or not c:
            print('missing', seed); continue
        seed_row = {}
        for split, key in METRICS:
            a = n[split][key]; b = c[split][key]
            seed_row[f'{split}|{key}'] = dict(N=a, NC=b, delta=b - a)
        for tgt in ('0.8', '0.9', '0.95'):
            a = n['trans_equal_recall']['test_transfer'][tgt]['fpr']
            b = c['trans_equal_recall']['test_transfer'][tgt]['fpr']
            seed_row[f'test_fpr@{tgt}'] = dict(N=a, NC=b, delta=b - a)
        for role in ('trigger', 'payload', 'output_hijack'):
            a = n['trans_val']['roles'].get(role, {}).get('recall')
            b = c['trans_val']['roles'].get(role, {}).get('recall')
            if a is not None and b is not None:
                seed_row[f'role_{role}'] = dict(N=a, NC=b, delta=b - a)
        a = n['trans_cones_test'].get('fpr_at_thr'); b = c['trans_cones_test'].get('fpr_at_thr')
        if a is not None and b is not None:
            seed_row['cone_test_fpr'] = dict(N=a, NC=b, delta=b - a)
        per_seed[seed] = seed_row
        rows.append(seed_row)

    names = sorted({k for r in rows for k in r})
    agg = {}
    for k in names:
        ds = [r[k]['delta'] for r in rows if k in r]
        ns = [r[k]['N'] for r in rows if k in r]
        cs = [r[k]['NC'] for r in rows if k in r]
        agg[k] = dict(n=len(ds), delta_mean=st.mean(ds),
                      delta_sd=st.stdev(ds) if len(ds) > 1 else None,
                      N_mean=st.mean(ns), NC_mean=st.mean(cs),
                      N_sd=st.stdev(ns) if len(ns) > 1 else None,
                      NC_sd=st.stdev(cs) if len(cs) > 1 else None)
    out = dict(seeds=SEEDS, per_seed=per_seed, aggregate=agg,
               note='paired NC-N per seed; sample SD (ddof=1); views are not independent designs')
    (OUT / 'AGGREGATE_SEEDS.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    for k, v in agg.items():
        print(k, round(v['N_mean'], 4), round(v['NC_mean'], 4), 'delta', round(v['delta_mean'], 4),
              'sd', (round(v['delta_sd'], 4) if v['delta_sd'] is not None else None), 'n', v['n'])


if __name__ == '__main__':
    main()
