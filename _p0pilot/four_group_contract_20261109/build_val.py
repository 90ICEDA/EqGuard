"""Build common abc/id/opt validation subgraph (39 views) with aux/edges/mappings."""
import json, hashlib
from pathlib import Path
import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
BASE = ('ys_abc', 'ys_id', 'ys_opt')


def main():
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs']['trans_val']['views']}
    keep = [v for v in vs if v.split('__')[-1] in BASE]
    assert len(keep) == 39, len(keep)
    folder = B / 'inputs/trans_val'
    x = np.load(folder / 'x39.npy'); edge = np.load(folder / 'edge_index.npy')
    y = np.load(folder / 'y.npy'); tr = np.load(folder / 'trusted.npy'); ph = np.load(folder / 'physical.npy')
    rows, aux = [], 0
    for v in keep:
        lay = vs[v]; rows.extend(range(lay['start'], lay['stop'])); aux += lay['stop'] - lay['physical_stop']
    rows = np.array(rows, np.int64)
    o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows))
    src, dst = edge[0], edge[1]
    m = (o2n[src] >= 0) & (o2n[dst] >= 0)
    A = np.load(OUT / 'group_A.npz'); mean, std = A['mean'], A['std']
    xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
    np.savez_compressed(OUT / 'val_common.npz', x=xx, edge=np.stack([o2n[src[m]], o2n[dst[m]]]),
                        y=y[rows], trusted=tr[rows], physical=ph[rows], rows=rows,
                        old2new=o2n, new2old=rows, mean=mean, std=std,
                        views=np.array(keep))
    rep = dict(views=len(keep), nodes=len(rows), aux=int(aux), mean_sha=hashlib.sha256(np.concatenate([mean, std]).tobytes()).hexdigest())
    (OUT / 'VAL_COMMON.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
    print(rep)


if __name__ == '__main__':
    main()
