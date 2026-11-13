"""Describe the current dataset: views, hosts, instances, recipes, keeps (read-only)."""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V = ROOT / 'generate_trans/folds/hosts_bt31/views.json'
views = json.loads(V.read_text(encoding='utf-8'))


def parse(name):
    parts = name.split('__')
    host = parts[0]
    tail = parts[-1]
    mid = parts[1:-1]
    keep = next((x for x in mid if x.startswith('keep')), 'plain')
    inst = parts[1].replace('_d1_s42', '')
    return host, inst, keep, tail


def family(inst):
    if inst.startswith('a4trojan'):
        return 'a4trojan'
    if inst.startswith('a4ctl'):
        return 'a4ctl'
    if inst.startswith('inj'):
        return 'injection'
    return 'control'


out = {}
for split in ('train', 'val', 'test'):
    rows = [parse(v) for v in views[f'{split}_views']]
    c = collections.Counter()
    hosts = collections.Counter(); insts = collections.Counter(); recs = collections.Counter()
    keeps = collections.Counter(); fams = collections.Counter()
    for h, i, k, r in rows:
        hosts[h] += 1; insts[i] += 1; recs[r] += 1; keeps[k] += 1; fams[family(i)] += 1
    out[split] = dict(views=len(rows), hosts=dict(hosts), instances=dict(insts),
                      recipes=dict(recs), keeps=dict(keeps), families=dict(fams))
    print(split, len(rows))
    print('  hosts', dict(hosts))
    print('  families', dict(fams))
    print('  recipes', dict(recs))
    print('  keeps', dict(keeps))
    print('  instances', dict(insts))
print(json.dumps(out, ensure_ascii=False, indent=1))
(Path(__file__).resolve().parent / 'dataset_description.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
