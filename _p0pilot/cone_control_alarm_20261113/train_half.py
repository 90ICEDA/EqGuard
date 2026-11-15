"""Run the seed42 v5 weight-only contrast without changing frozen runs."""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
V5 = OUT.parent / 'heldout_recipe_v5_20261109'
sys.path.insert(0, str(V5))
import train_v5 as train


def main():
    assert 'ginvenv_gpu' in sys.executable and train.torch.cuda.is_available()
    train.torch.set_num_threads(2)
    loader = train.FiveGroupLoader()
    train.T.CONTRACT = loader.feature_contract
    train.T.NORM = loader.normalization
    train.T.arrays = loader.arrays
    assert train.T.MASK_MODE == 'old' and not train.T.EXTRA and train.T.EQ == 0
    train.OUT = OUT / 'half_weight'
    train.OUT.mkdir()
    full_loss = train.CL.cone_loss
    train.CL.cone_loss = lambda logits, cones: 0.5 * full_loss(logits, cones)

    # Recreate the same v5 draws once and verify against both frozen histories.
    draws = {}
    for recipe in train.F.RECIPES:
        with train.np.load(train.F.V4 / f'{recipe}_train_map.npz') as data:
            pos, common_pool, h_pool = (data[k] for k in ('pos', 'common_pool', 'h_pool'))
        references = [json.loads((V5 / recipe / arm / 'LOG.json').read_text(encoding='utf-8'))['logs']
                      for arm in ('N', 'NC')]
        for step in range(200):
            rng = train.np.random.default_rng(42 + step)
            ids = train.np.concatenate([pos, rng.choice(common_pool, 8192, replace=False),
                                        rng.choice(h_pool, 144, replace=False)]).astype(train.np.int64)
            assert len(train.np.unique(ids)) == len(pos) + 8336
            original = loader.step('orig', 'G0', step).indices
            assert all(train.F.sha_ids(ids) == log[step]['trans_sha'] and
                       train.F.sha_ids(original) == log[step]['orig_sha'] for log in references)
            draws[recipe, step] = ids, (len(pos), 8192, 144)
    train.F.step_indices = lambda recipe, step: draws[recipe, step]
    print('PASS: 600 draws match frozen N and NC in both domains', flush=True)
    for recipe in train.F.RECIPES:
        result = train.run(loader, recipe, 'NC')
        output = train.OUT / recipe / 'NC'
        log = json.loads((output / 'LOG.json').read_text(encoding='utf-8'))
        assert len(log['logs']) == 200 and all(row['finite'] for row in log['logs'])
        (output / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('DONE', recipe, result['best_step'], result['best_score'], flush=True)


if __name__ == '__main__':
    main()
