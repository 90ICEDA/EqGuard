"""Three-seed unified evaluation (seed42 reuse CLOSURE; seeds 1/2 from saved preds)."""
import json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
V5 = R / '_p0pilot/heldout_recipe_v5_20261109'
E2 = R / '_p0pilot/heldout_recipe_v5_eval2_20261109'
sys.path.insert(0, str(V5)); sys.path.insert(0, str(E2)); sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105'))
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
import fold_io as F
import close_eval as CE

RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')
ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')
STRICT = ('s38584t100__injalpha_d1_s42', 's38584t100__injepsilon_d1_s42',
          's38584t100__injgamma_d1_s42', 's38584t100__injzeta_d1_s42')


def eval_pred(rec, arm, seed, tag):
    d = V5 / rec / arm / (f'seed{seed}' if seed != 42 else '') / f'{tag}_pred.npz'
    z = np.load(d)
    dv = np.load(F.V4 / f'{rec}_val_map.npz')
    dt = F.load_trans(rec, 'test')
    g = dict(rows=dt['rows'], y=dt['y'], trusted=dt['trusted'], physical=dt['physical'], views=F.views('test'))
    s = z['test']
    ho = CE.per_view_ap(s, g, (rec,))
    seen = CE.per_view_ap(s, g, tuple(r for r in ALL if r != rec))
    ho_src, ho_macro = CE.source_macro(ho); se_src, se_macro = CE.source_macro(seen)
    strict_ho = {k: v for k, v in ho_src.items() if k in STRICT}
    strict_se = {k: v for k, v in se_src.items() if k in STRICT}
    return dict(heldout_macro=ho_macro, seen_macro=se_macro,
                heldout_src=ho_src, seen_src=se_src,
                strict_ho=float(np.mean(list(strict_ho.values()))) if strict_ho else None,
                strict_se=float(np.mean(list(strict_se.values()))) if strict_se else None,
                strict_n=len(strict_ho),
                top1={r: CE.topk_recipe(s, g, r, 1) for r in ALL},
                top5={r: CE.topk_recipe(s, g, r, 5) for r in ALL},
                normal={t: CE.normal_fpr(s, g, v) for t, v in
                        {k: float(np.sort(z['val'][np.asarray(dv['trusted']) & (np.asarray(dv['y']) == 1)])[::-1][int(np.ceil(float(k) * (np.asarray(dv['trusted']) & (np.asarray(dv['y']) == 1)).sum())) - 1]) for k in ('0.8', '0.9', '0.95')}.items()})


def main():
    out = {}
    closure = json.loads((E2 / 'CLOSURE.json').read_text(encoding='utf-8'))
    for rec in RECIPES:
        for arm in ('N', 'NC'):
            for seed in (42, 1, 2):
                for tag in ('best', 'last'):
                    if seed == 42:
                        e = closure[f'{rec}_{arm}_{tag}']
                        out[f'{rec}_{arm}_{seed}_{tag}'] = dict(heldout_macro=e['heldout_macro'],
                                                                seen_macro=e['seen_macro'],
                                                                heldout_src=e['heldout_source_ap'], seen_src=e['seen_source_ap'])
                    else:
                        out[f'{rec}_{arm}_{seed}_{tag}'] = eval_pred(rec, arm, seed, tag)
    (E2 / 'SEEDS3.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    for rec in RECIPES:
        for tag in ('best', 'last'):
            for arm in ('N', 'NC'):
                vals = [out[f'{rec}_{arm}_{s}_{tag}']['heldout_macro'] for s in (42, 1, 2)]
                print(rec, tag, arm, [round(v, 4) for v in vals])
    print('done')


if __name__ == '__main__':
    main()
