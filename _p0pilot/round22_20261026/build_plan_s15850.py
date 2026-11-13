"""Freeze the s15850 ys_abc coverage-extension plan without reading labels."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'

# Letter-matched control is used because the view metadata does not provide an
# explicit inj->control pairing. Selection is by source name/size only.
PAIRS = [
    ('alpha', 'train', 's15850t100__injalpha_d1_s42__ys_abc'),
    ('alpha', 'train', 's15850t100__ctlmatcha_d1_s42__ys_abc'),
    ('delta', 'train', 's15850t100__injdelta_d1_s42__ys_abc'),
    ('delta', 'train', 's15850t100__ctlmatchd_d1_s42__ys_abc'),
    ('epsilon', 'val', 's15850t100__injepsilon_d1_s42__ys_abc'),
    ('epsilon', 'val', 's15850t100__ctlmatche_d1_s42__ys_abc'),
    ('gamma', 'val', 's15850t100__injgamma_d1_s42__ys_abc'),
    ('gamma', 'val', 's15850t100__ctlmatchc_d1_s42__ys_abc'),
    ('zeta', 'test', 's15850t100__injzeta_d1_s42__ys_abc'),
    ('zeta', 'test', 's15850t100__ctlmatchf_d1_s42__ys_abc'),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    views = []
    for family, split, view in PAIRS:
        src = ROOT / 'generate_trans/folds/hosts_bt31/trans' / (view + '.v')
        assert src.exists(), src
        views.append(dict(view=view, family=family, split=split,
                          source=str(src.relative_to(ROOT)), bytes=src.stat().st_size,
                          source_sha=sha(src)))
    plan = dict(
        created='2026-10-26T19:15:00+08:00',
        scope='s15850t100 ys_abc; 5 injection families + letter-matched controls',
        views=views,
        selection='all s15850 ys_abc injection families with a letter-matched control; '
                  'selected by view/source names and size, not labels',
        split_scope='same host s15850; family-level split for feature audit; not training',
        context='native_unrestricted_combinational_physical_Q_v1',
        cut_rule=dict(max_inputs=4, max_depth=4,
                      choice='complete structural frontier in depth/bit order; <=4 leaves'),
        target_rule='one sample per graph cell: comb output; DFF D data-cone descriptor',
        sat_timeout=3, sat_batch_nodes=32,
        families=['alpha', 'delta', 'epsilon', 'gamma', 'zeta'],
        controls='letter-matched: alpha/a, delta/d, epsilon/e, gamma/c, zeta/f',
        no_labels_read_before_freeze=True,
    )
    plan['plan_sha'] = hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()).hexdigest()
    (OUT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(views=len(views), total_bytes=sum(x['bytes'] for x in views),
                          plan_sha=plan['plan_sha']), indent=2))


if __name__ == '__main__':
    main()
