"""Score half-weight checkpoints on the same full graph as the seed42 baselines."""
import importlib.util
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'heldout_recipe_v5_eval2_20261109'))
import close_eval as frozen

spec = importlib.util.spec_from_file_location('cone_control_evaluation', OUT / 'evaluate.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
write, source_macro, circuit_score = common.write, common.source_macro, common.circuit_score

np, torch = frozen.np, frozen.torch
sys.path.insert(0, str(P / 'lcone_endpoint_overlap_20261112'))
from audit import load, csv_rows
sys.path.insert(0, str(P / 'c2_endpoint_replay_20261112'))
from replay import endpoint_metrics


def main():
    layouts, panel = load()
    rows, alarms, nodes = [], [], []
    metadata = list(csv_rows(P / 'control_loader_po_20261105/view_dictionary.csv'))
    prior = {(r['fold'], r['view'], r['kind'], r['arm'], r['point']): r for r in
             csv_rows(P / 'heldout_v5_endpoint_replay_20261112/BY_VIEW.csv') if r['seed'] == '42'}
    for fold in frozen.RECIPES:
        recipe = fold.removeprefix('ys_')
        mean, std = frozen.F.fold_stats(fold)
        graph = frozen.test_graph(mean, std)
        gx = torch.as_tensor(graph['x'], device='cuda')
        ge = torch.as_tensor(graph['edge'], device='cuda')
        val_map = frozen.F.load_trans(fold, 'val')
        active = val_map['trusted'] & val_map['physical'] & (val_map['y'] == 1)
        for arm in ('N', 'NC', 'half'):
            run = (OUT / 'half_weight' / fold / 'NC' if arm == 'half'
                   else frozen.V5 / fold / arm)
            for point in ('best', 'last'):
                if arm == 'half':
                    model = frozen.Model().cuda()
                    model.load_state_dict(torch.load(run / f'{point}.pt', map_location='cuda', weights_only=True))
                    model.eval()
                    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                        logit = model(gx, ge).float()
                        scores = (logit[:, 1] - logit[:, 0]).cpu().numpy()
                    del model, logit
                else:
                    with np.load(frozen.OUT / f'{fold}_{arm}_{point}_testpred.npz') as prediction:
                        assert np.array_equal(prediction['rows'], graph['rows'])
                        scores = prediction['scores']
                with np.load(run / f'{point}_pred.npz') as val_file:
                    assert np.array_equal(val_file['val_rows'], val_map['rows'])
                    val = val_file['val']
                assert np.array_equal(graph['rows'], np.arange(len(graph['y'])))
                test_global = scores
                test_views = [v for v in metadata if v['key'] == 'trans_test' and v['recipe'] == fold]
                val_views = [v for v in metadata if v['key'] == 'trans_val' and v['recipe'] != fold]
                assert all(np.array_equal(
                    val_map['rows'][np.searchsorted(val_map['rows'], int(v['start'])):
                                    np.searchsorted(val_map['rows'], int(v['physical_stop']))],
                    np.arange(int(v['start']), int(v['physical_stop']))) for v in val_views)
                for k in (1, 5):
                    val_scores = [(v, circuit_score(val[np.searchsorted(val_map['rows'], int(v['start'])):
                                                       np.searchsorted(val_map['rows'], int(v['physical_stop']))], k))
                                  for v in val_views]
                    val_pos = [(v, s) for v, s in val_scores if v['kind'] == 'trojan']
                    cut = next(t for t in sorted({s for _, s in val_pos}, reverse=True)
                               if source_macro(val_pos, t) >= .90)
                    for split, split_scores in [('val', val_scores), ('test', [
                        (v, circuit_score(test_global[int(v['start']):int(v['physical_stop'])], k))
                        for v in test_views])]:
                        for v, score in split_scores:
                            alarms.append(dict(fold=fold, arm=arm, point=point, k=k, split=split,
                                               view=v['view'], kind=v['kind'], source=v['source'],
                                               score=score, cut=cut, alarm=int(score >= cut)))
                node_cut = float(np.sort(val[active])[::-1][int(np.ceil(.95 * active.sum())) - 1])
                for v in test_views:
                    lo, hi = int(v['start']), int(v['physical_stop'])
                    select = graph['trusted'][lo:hi] & graph['physical'][lo:hi]
                    y = graph['y'][lo:hi][select]
                    score = test_global[lo:hi][select]
                    nodes.append(dict(fold=fold, arm=arm, point=point, view=v['view'], source=v['source'],
                                      kind=v['kind'], node_cut=node_cut, pos=int((y == 1).sum()),
                                      tp=int(((y == 1) & (score >= node_cut)).sum()),
                                      neg=int((y == 0).sum()),
                                      fp=int(((y == 0) & (score >= node_cut)).sum()),
                                      ap=frozen.average_precision_score(y, score) if (y == 1).any() else ''))
                for (view, kind), group in panel.items():
                    if view.endswith('__ys_' + recipe):
                        assert np.isfinite(test_global[layouts[view]['start']:layouts[view]['physical_stop']]).all()
                        metrics = endpoint_metrics(group, test_global)
                        if arm != 'half':
                            ref = prior[recipe, view, kind, arm, point]
                            assert all((ref[key] == '' if value is None else float(ref[key]) == value)
                                       for key, value in metrics.items()), (fold, arm, point, view, kind)
                        rows.append(dict(fold=fold, arm=arm, point=point, view=view, kind=kind, **metrics))
        del gx, ge
        torch.cuda.empty_cache()
    write('HALF_BY_ENDPOINT_VIEW.csv', rows)
    write('HALF_ALARM_BY_VIEW.csv', alarms)
    write('HALF_NODE_BY_VIEW.csv', nodes)


if __name__ == '__main__':
    main()
