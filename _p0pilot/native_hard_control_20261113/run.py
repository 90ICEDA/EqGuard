"""Run two fixed-slot NC comparisons through the frozen task-one trainer."""
from prepare import OUT, BASE, digest, np, read, torch
import hashlib
import train_pair as t
from types import SimpleNamespace
import json
import sys


class FixedSlots:
    def __init__(self, loader, orig, trans):
        self.loader, self.orig, self.trans = loader, orig, trans

    def arrays(self, *args):
        return self.loader.arrays(*args)

    def torch_graph(self, domain, split, device):
        data = self.loader.arrays(domain, split)
        raw = data['x39']
        x = torch.empty(raw.shape, dtype=torch.float32, device=device)
        mean, std = (self.loader.normalization[k][25:] for k in ('mean', 'std'))
        for lo in range(0, len(raw), 65536):
            hi = min(lo + 65536, len(raw))
            block = np.array(raw[lo:hi], dtype=np.float32, copy=True)
            block[:, 25:] = np.clip((block[:, 25:] - mean) / std, -10, 10)
            x[lo:hi].copy_(torch.from_numpy(block))
        edge = torch.tensor(data['edge_index'], dtype=torch.long, device=device)
        y = torch.tensor(data['y'], dtype=torch.long, device=device)
        return dict(x=x, edge=edge, y=y)

    def step(self, domain, arm, step, seed):
        assert arm == 'G0' and seed == 42
        return SimpleNamespace(indices=(self.orig if domain == 'orig' else self.trans)[step])


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    gate = read(OUT/'GATE.json')
    assert gate['schedule_sha'] == digest(OUT/'SCHEDULE.npz')
    assert gate['matched_slots'] > 0 and gate['source_count'] >= 2
    with np.load(OUT/'SCHEDULE.npz') as z:
        orig,g0,high,low = (z[k] for k in ('orig','g0','high','low'))
    loader = t.FiveGroupLoader()
    t.T.CONTRACT, t.T.NORM, t.T.arrays = loader.feature_contract, loader.normalization, loader.arrays
    assert t.T.MASK_MODE == 'old' and not t.T.EXTRA and t.T.EQ == 0
    for step in range(200):
        assert np.array_equal(loader.step('orig','G0',step).indices,orig[step])
        assert np.array_equal(loader.step('trans','G0',step).indices,g0[step])
    baseline = {f:digest(BASE/f) for f in ('NC_best.pt','NC_last.pt','NC_scores.npz')}
    cones = t.CL.cone_tensors(t.CL.load_cones('train','D',trust=np.asarray(loader.arrays('trans')['trusted'])))
    for name, trans in [('high',high),('low',low)]:
        t.OUT = OUT/name
        t.OUT.mkdir(exist_ok=True)
        if (t.OUT/'RESULT.json').exists():
            continue
        print('START',name,flush=True)
        result = t.run('NC',FixedSlots(loader,orig,trans),cones,seed=42)
        assert len(result['history']) == 40
        assert all(hashlib.sha256(trans[r['step']-1].tobytes()).hexdigest() == r['idx_sha']
                   for r in result['history'])
        assert np.isfinite([[r['orig'],r['trans'],r['val_ap']] for r in result['history']]).all()
        (t.OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('DONE',name,result['best_step'],result['seconds'],flush=True)
    assert all(digest(BASE/f)==s for f,s in baseline.items())


if __name__=='__main__':
    main()
