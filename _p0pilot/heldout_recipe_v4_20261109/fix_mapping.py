"""Save corrected bidirectional mappings (new2old = rows, old2new over full split space)."""
import hashlib
import json
import numpy as np
from pathlib import Path

V3 = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\heldout_recipe_v3_20261109')
OUT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\heldout_recipe_v4_20261109')
RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')


def main():
    report = {}
    for rec in RECIPES:
        for split, fn in (('train', f'{rec}_trans.npz'), ('val', f'{rec}_val.npz'), ('test', f'{rec}_test.npz')):
            z = np.load(V3 / fn)
            rows = z['rows'].astype(np.int64)
            import json
            c = json.loads((Path(r'C:/Users/91344/Desktop/GraphSAINT/GIN_train/_p0pilot/control_boundary_v3_20261104/input_contract.json')).read_text(encoding='utf-8'))
            full = int(c['shared_inputs'][f'trans_{split}']['nodes'])
            old2new = np.full(full, -1, np.int64); old2new[rows] = np.arange(len(rows))
            new2old = rows
            assert np.array_equal(old2new[new2old], np.arange(len(rows)))
            out = {k: z[k] for k in z.files if k not in ('old2new', 'new2old')}
            out['old2new'] = old2new; out['new2old'] = new2old
            np.savez_compressed(OUT / f'{rec}_{split}_map.npz', **out)
            report[f'{rec}_{split}'] = dict(nodes=int(len(rows)), old2new_len=full,
                                            roundtrip=True, sha=hashlib.sha256(old2new.tobytes()).hexdigest())
    (OUT / 'MAPPING_FIX.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False)[:500])


if __name__ == '__main__':
    main()
