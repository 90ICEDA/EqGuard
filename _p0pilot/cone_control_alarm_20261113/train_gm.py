"""Seed42 GM companions to the frozen task-one N and NC runs."""
import json
import hashlib
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
BASE = OUT.parent / 'seed42_nc_ablation_20261109'
sys.path.insert(0, str(BASE))
import train_pair as train


class GMNodeSupervision:
    def __init__(self, loader):
        self.loader = loader

    def torch_graph(self, *args):
        return self.loader.torch_graph(*args)

    def arrays(self, *args):
        return self.loader.arrays(*args)

    def step(self, domain, arm, step, seed):
        assert arm == 'G0'  # The frozen runner's requested default.
        return self.loader.step(domain, 'GM', step, seed=seed)


def verify(loader):
    ledgers = {}
    for domain, positives, negatives in (('orig', 136, 8296), ('trans', 829, 8336)):
        data = loader.arrays(domain)
        pool = loader.pools[domain]
        h_exposure = np.zeros(len(data['y']), np.int32)
        m_exposure = h_exposure.copy()
        changed_pairs = set()
        for step in range(200):
            g0 = loader.step(domain, 'G0', step, seed=42)
            gm = loader.step(domain, 'GM', step, seed=42)
            assert np.array_equal(g0.positive, gm.positive)
            assert np.array_equal(g0.common_negative, gm.common_negative)
            assert np.array_equal(g0.pair_ids, gm.pair_ids)
            changed = gm.replacement_negative != g0.replacement_negative
            assert changed.sum() == 48
            changed_pairs.update(gm.pair_ids[changed].tolist())
            assert np.array_equal(pool['H'][g0.pair_ids[changed]], g0.replacement_negative[changed])
            assert np.array_equal(pool['N'][gm.pair_ids[changed]], gm.replacement_negative[changed])
            for q, counts in ((g0, h_exposure), (gm, m_exposure)):
                idx = q.indices
                assert len(np.unique(idx)) == positives + negatives
                assert (data['trusted'][idx] & data['physical'][idx]).all()
                assert np.all(data['y'][idx[:positives]] == 1)
                assert np.all(data['y'][idx[positives:]] == 0)
                counts[idx[positives:]] += 1
        assert np.array_equal(np.sort(h_exposure), np.sort(m_exposure))
        assert h_exposure.max() == m_exposure.max() <= 128
        ledgers[domain] = dict(positive_per_step=positives, negative_per_step=negatives,
                               M_per_step=48, steps=200, matched_pair_ids=len(changed_pairs),
                               max_negative_exposure=int(m_exposure.max()))
    return ledgers


def main():
    assert 'ginvenv_gpu' in sys.executable and train.torch.cuda.is_available()
    train.torch.set_num_threads(2)
    loader = train.FiveGroupLoader()
    train.T.CONTRACT = loader.feature_contract
    train.T.NORM = loader.normalization
    train.T.arrays = loader.arrays
    assert train.T.MASK_MODE == 'old' and not train.T.EXTRA and train.T.EQ == 0
    ledger = verify(loader)
    (OUT / 'GM_BUDGET.json').write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    print('PASS GM budget', ledger, flush=True)
    trust = np.asarray(loader.arrays('trans')['trusted'])
    cones = train.CL.cone_tensors(train.CL.load_cones('train', 'D', trust=trust))
    baseline = json.loads((BASE / 'RESULTS_PAIR.json').read_text(encoding='utf-8'))
    historical = json.loads((OUT.parent / 'control_five_seed42_20261107/EXECUTION_CONTRACT.json')
                            .read_text(encoding='utf-8'))
    init_sha = hashlib.sha256((train.V / 'init_s42.pt').read_bytes()).hexdigest()
    assert init_sha == historical['initial_sha']
    for arm in ('N', 'NC'):
        train.OUT = OUT / f'{arm}_GM'
        if all((train.OUT / f'{arm}_s42_{suffix}').is_file()
               for suffix in ('best.pt', 'last.pt', 'scores.npz')):
            with np.load(train.OUT / f'{arm}_s42_scores.npz') as scores:
                assert all(np.isfinite(scores[k]).all() for k in ('val_best', 'val_last', 'test_best', 'test_last'))
            print('REUSED completed prediction and both checkpoints', arm, flush=True)
            continue
        train.OUT.mkdir()
        result = train.run(arm, GMNodeSupervision(loader), cones, seed=42)
        assert result['init_sha'] == init_sha
        assert len(result['history']) == len(baseline[arm]['history']) == 40
        assert np.isfinite([r[k] for r in result['history'] for k in ('orig', 'trans', 'val_ap')]).all()
        (train.OUT / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('DONE', arm, result['seconds'], result['best_step'], flush=True)


if __name__ == '__main__':
    main()
