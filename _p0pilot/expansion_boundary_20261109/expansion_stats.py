"""Expansion-boundary statistics per recipe/source from frozen test cache (no training)."""
import csv, json
from pathlib import Path
import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/expansion_boundary_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'


def main():
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
    y = np.load(B / 'inputs/trans_test/y.npy'); tr = np.load(B / 'inputs/trans_test/trusted.npy'); ph = np.load(B / 'inputs/trans_test/physical.npy')
    stats = {}
    # physical/pos/trusted per recipe
    for v, lay in vs.items():
        rec = v.split('__')[-1]; src = v.split('__ys_')[0]
        a, b = lay['start'], lay['stop']
        d = stats.setdefault(rec, dict(nodes=0, physical=0, trusted=0, positive=0, sources=set()))
        d['nodes'] += b - a; d['physical'] += int(ph[a:b].sum())
        d['trusted'] += int((tr[a:b] & ph[a:b]).sum()); d['positive'] += int(((y[a:b] == 1) & tr[a:b] & ph[a:b]).sum())
        d['sources'].add(src)
    for rec, d in stats.items():
        d['trusted_coverage'] = d['trusted'] / max(1, d['physical'])
        d['positive_density'] = d['positive'] / max(1, d['physical'])
        d['sources'] = len(d['sources'])
    # cones from test cache
    cones = {}
    with (OLD / 'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != 'test' or r['kind'] not in ('D', 'PO'):
                continue
            rec = r['view'].split('__')[-1]; kind = r['kind']
            mem = [int(x) for x in r['phys_rows'].split('|') if x]
            mem = [x for x in mem if bool(tr[x]) and bool(ph[x])]
            key = (rec, kind)
            e = cones.setdefault(key, dict(cones=0, sizes=[], max_agg=0, members=0, labels={1: 0, 0: 0, -1: 0}))
            e['cones'] += 1; e['sizes'].append(len(mem)); e['members'] += len(mem)
            e['max_agg'] = max(e['max_agg'], len(mem))
            e['labels'][int(r['label'])] += 1
    for (rec, kind), e in cones.items():
        e['mean_size'] = float(np.mean(e['sizes'])); e['max_size'] = int(max(e['sizes']))
        e['shared_exposure'] = e['members'] / max(1, e['cones'])
        del e['sizes']
        stats.setdefault(rec, {})[kind] = e
    (OUT / 'EXPANSION_STATS.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
    for rec, d in stats.items():
        print(rec, 'nodes', d.get('nodes'), 'physical', d.get('physical'), 'trusted_cov', round(d.get('trusted_coverage', 0), 3),
              'pos_density', round(d.get('positive_density', 0), 4), 'Dcones', d.get('D', {}).get('cones'), 'Dmax', d.get('D', {}).get('max_size'))


if __name__ == '__main__':
    main()
