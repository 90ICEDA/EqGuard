"""Recompute core report cells and check the actual paired training ledgers."""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

P = Path('_p0pilot')
seeds = (42, 1, 2)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def compare(values):
    left, right = zip(*values)
    diff = [b - a for a, b in values]
    return [statistics.mean(left), statistics.mean(right), statistics.mean(diff),
            statistics.stdev(diff), sum(d > 0 for d in diff)]


one = P / 'seed42_nc_ablation_20261109'
base = [load(one / n) for n in ('RESULTS_PAIR.json', 'RESULTS_ALL.json')]
train = {s: {} for s in seeds}
for f in base:
    for v in f.values():
        if isinstance(v, dict) and v.get('arm') in ('N', 'NC'):
            train[v.get('seed', 42)][v['arm']] = v
for pair in train.values():
    assert pair['N'].get('init_sha') == pair['NC'].get('init_sha')
    for arm in pair.values():
        assert arm['best_step'] in range(5, 201, 5)
for point in ('best', 'last'):
    print('task1', point, compare(
        [tuple(train[s][a][point + '_test']['node_ap'] for a in ('N', 'NC')) for s in seeds]))
assert load(one / 'PRECHECK_TRAIN_MODE.json')['optimizer_steps'] == 0

five = {}
for s in seeds:
    d = P / f'control_five_seed{s}_20261107'
    run = load(d / 'TRAINING_COMPLETE.json')['runs']
    assert {r['arm'] for r in run} == {'G0', 'GB', 'GM', 'GBM', 'GAll'}
    assert len({r['initial_sha'] for r in run}) == 1
    assert all(r['updates'] == 200 and r['seed'] == s for r in run)
    five[s] = run[0]['initial_sha']
assert len(set(five.values())) == 3
assert load(P / 'control_five_multiseed_20261107' / 'VERIFIED.json')['same_indices_all_seeds']
print('five', len(five)*5, 'runs')

held = P / 'heldout_recipe_v5_20261109'
gate = load(held / 'GATE_V5.json')
assert gate['passed'] and all(x['passed'] for x in gate['checks'])
print('v5 gate', len(gate['checks']))
for rec in ('abc', 'aig', 'nand'):
    all_hash = []
    for s in seeds:
        arms = []
        init = []
        for a in ('N', 'NC'):
            path = held / f'ys_{rec}' / a
            path = path if s == 42 else path / f'seed{s}'
            run = load(path / 'LOG.json')
            assert run['best_step'] in range(5, 201, 5)
            seq = run.get('logs', run.get('log'))
            assert [x['step'] for x in seq] == list(range(1, 201))
            assert all(x['finite'] for x in seq)
            assert len(list(path.glob('*pred.npz'))) == 2
            init.append(run.get('init_sha'))
            arms.append([(x['orig_sha'], x['trans_sha']) for x in seq])
        assert arms[0] == arms[1]
        assert init[0] == init[1] and (s == 42 or init[0])
        all_hash.append(arms[0])
    assert all_hash[0] == all_hash[1] == all_hash[2]
print('heldout', 3*len(seeds)*2, 'runs')

two = P / 'task2_nokeep_audit_20261113'
replay = load(two / 'INDEPENDENT_METRIC_REPLAY.json')
assert replay['rows_reproduced'] == 192 and replay['optimizer_steps'] == replay['sat_cec_calls'] == 0
clean = rows(two / 'CLEAN_PAIRED_V2' / 'PAIRED_SUMMARY.csv')
assert len(clean) == 16 and sum(int(r['keep_alarms']) for r in clean) == 48
assert all(r['keep_alarms'] == r['none_alarms'] == '3' and r['alarm_transitions'] == '1->1|1->1|1->1'
           and abs(float(r['fraction_delta'])) < .006 for r in clean)
for prefix in ('s38417', 's38584', 's38584_alpha', 's38417t300_beta'):
    part = rows(two / f'{prefix}_N_NC_BY_SEED.csv')
    assert len(part) == 96, (prefix, len(part))
clean_manifest = load(two / 'CLEAN_PAIRED_V2' / 'MANIFEST.json')
assert len(clean_manifest) == 8 and all(r['proven'] > 0 and r['unproven'] == 0 for r in clean_manifest)
for row in clean_manifest:
    paths = {k: Path(row[k].replace('\\', '/').split('/GIN_train/', 1)[-1])
             for k in ('source', 'target')}
    paths['cec'] = two / 'CLEAN_PAIRED_V2' / (row['view'] + '_cec.log')
    for k, path in paths.items():
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == row[k + '_sha256'], path
print('task2', '16 injected views, 8 clean views')

h = P / 'legacy_h_cone_20261115'
src, agg = rows(h / 'SUMMARY.csv'), rows(h / 'AGGREGATE.csv')
assert len(src) == 12 and all(int(x['step']) == 200 for x in src if x['point'] == 'last')
for x in agg:
    m = x['metric']
    part = {(int(r['seed']), r['arm']): r[m] for r in src if r['point'] == x['point']}
    if not all(part.values()):
        continue
    got = compare([tuple(float(part[s, a]) for a in ('H', 'H_D')) for s in seeds])
    assert all(math.isclose(val, float(x[key]), rel_tol=1e-10, abs_tol=1e-12)
               for val, key in zip(got, ('H', 'H_D', 'delta', 'delta_sd'))), (m, got, x)
for s in seeds:
    p = load(h / f'PREFLIGHT_S{s}.json')
    assert all(d['slots_per_step'] == 320 for d in p['population'].values())
    assert p['cone_loss'] == dict(kind='D', domain='trans', weight=1, pos_weight=10)
print('H', 'paired summaries recomputed')
