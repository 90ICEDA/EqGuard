"""Expand the validation function-different certificate set (read-only, no SAT, no training).

Reuses the same val pair pool / witness contexts as the 2026-11-05 mechanism audit.
Difference from the original prepare.py: enumerate many candidate pairs per bucket
(instead of one) and keep up to MAX_PER_SOURCE per source, so source-balanced AUC is
not dominated by 1-block sources.
"""
from pathlib import Path
import collections
import json
import sys

R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
J = R / '_p0pilot/cec_joint_expand_20261105'
sys.path.insert(0, str(J))
from common import Store, read, sha, ident, SCHEMA, N  # noqa: E402

MAX_PER_SOURCE = 32


def forbidden(*a, **k):
    raise RuntimeError('No SAT or new structure export allowed')


N.P0.run_yosys = forbidden


def verify(store, cones, cert, env_src):
    env = {tuple(x['token']): (int(x['mask_hex'], 16) >> cert['pattern']) & 1 for x in env_src['input_masks']}
    models = {}
    outputs = []
    for cid in cert['cones']:
        c = cones[cid]; view = c['view']
        if view not in models:
            m = store.raw(view)
            leaf = {}; drivers = {}
            for n, p in m['ports'].items():
                if p['direction'] == 'input':
                    for j, b in enumerate(p['bits']):
                        leaf[b] = ('PI', n, j, 0)
            for n, g in m['cells'].items():
                if 'DFF' in g['type'].upper():
                    for pin in ['Q', 'QN']:
                        for b in g['connections'].get(pin, []):
                            leaf[b] = ('Q', n, 0, int(pin == 'QN'))
                else:
                    drivers[g['connections'][SCHEMA[g['type']][0]][0]] = g
            models[view] = (leaf, drivers)
        leaf, drivers = models[view]
        cache = {}

        def ev(b):
            if not isinstance(b, int):
                assert b in ['0', '1']; return int(b)
            if b in cache: return cache[b]
            if b in leaf:
                t = leaf[b]; z = env[t[:3]] ^ t[3]
            else:
                g = drivers[b]
                v = [ev(g['connections'][p][0]) for p in SCHEMA[g['type']][1]]
                t = g['type']
                z = (v[0] & v[1]) if t in ['AND2X2', '$and'] else (v[0] | v[1]) if t in ['OR2X1', '$or'] else (v[0] ^ v[1]) if t in ['XOR2X1', '$xor'] else (1 - v[0]) if t in ['INVX0', '$not'] else (v[1] if v[2] else v[0])
            cache[b] = z; return z
        outputs.append(ev(c['root_bit']))
    return outputs


def main():
    assert not (O / 'validation_negative_certificates.json').exists(), 'already built'
    pairs = read(J / 'final_pairs.json')
    cones = {c['cone_id']: c for c in read(J / 'final_cones.json')}
    store = Store()
    buckets = collections.defaultdict(list)
    for p in pairs:
        if p['split'] != 'val':
            continue
        a, b = [cones[p[k]] for k in ['left_cone', 'right_cone']]
        store.raw(a['view']); store.raw(b['view'])
        av, bv = store.evaluators[a['view']][a['root_bit']], store.evaluators[b['view']][b['root_bit']]
        assert av == bv
        buckets[p['source_object'], p['context_id'], a['view'], b['view']].append((p, av))

    candidates = collections.defaultdict(dict)
    for key, rr in buckets.items():
        rr = sorted(rr, key=lambda t: ident(['validation_neg_locator_v1', t[0]['pair_id']]))
        n = len(rr)
        for j in range(n):
            a, amask = rr[j]
            for offset in range(1, min(n, 65)):
                b, bmask = rr[(j + offset) % n]
                if amask == bmask:
                    continue
                x, y = sorted([a['pair_id'], b['pair_id']])
                cid = ident(['validation_function_different_v1', x, y])
                diff = amask ^ bmask
                pattern = (diff & -diff).bit_length() - 1
                candidates[key[0]][cid] = dict(
                    certificate_id=cid, source=key[0], context_id=key[1], pair_a=a['pair_id'], pair_b=b['pair_id'],
                    cones=[a['left_cone'], a['right_cone'], b['left_cone'], b['right_cone']], pattern=pattern,
                    expected_outputs=[(amask >> pattern) & 1] * 2 + [(bmask >> pattern) & 1] * 2)
                break

    chosen = []
    for source, vals in sorted(candidates.items()):
        ordered = sorted(vals.items(), key=lambda kv: ident(['validation_negative_select_v1', kv[0]]))
        chosen.extend(cc for cid, cc in ordered[:MAX_PER_SOURCE])

    for cert in chosen:
        outputs = verify(store, cones, cert, store.contexts[cert['context_id']])
        assert outputs == cert['expected_outputs'] and outputs[0] != outputs[2], cert['certificate_id']
        cert['independent_scalar_verified'] = True
        cert['selection'] = 'existing val pair pool;fixed hash;multi-offset;no labels/prediction filter;posthoc diagnostic only'

    (O / 'validation_negative_certificates.json').write_text(json.dumps(chosen, ensure_ascii=False, indent=2), encoding='utf-8')
    (O / 'validation_witness_contexts.json').write_text(json.dumps(store.contexts, ensure_ascii=False, indent=2), encoding='utf-8')
    per_source = collections.Counter(c['source'] for c in chosen)
    report = dict(blocks=len(chosen), per_source=dict(per_source), sources=len(per_source),
                  max_per_source=MAX_PER_SOURCE, candidate_pool={s: len(v) for s, v in candidates.items()},
                  new_SAT_queries=0, training_updates=0,
                  note='expanded from existing val pair pool; independent scalar replay verified; no SAT/yosys')
    (O / 'EXPAND_REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
