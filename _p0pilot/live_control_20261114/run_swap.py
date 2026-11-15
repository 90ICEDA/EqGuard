"""Paired NC arms with an identical graph and a fixed native-negative swap schedule."""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from build import OUT as ASSETS, ROOT, digest, read

P = ASSETS.parent
OUT = ASSETS / 'nc_swap_seed42'
BASE = P / 'seed42_nc_ablation_20261109'
sys.path.insert(0, str(BASE))
import train_pair as t

import numpy as np
import torch


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def normalized(x, norm):
    x = x.copy()
    x[:,25:] = np.clip((x[:,25:] - norm['mean'][25:]) / norm['std'][25:], -10, 10)
    return x


class PairedLoader:
    def __init__(self, loader, additions, schedule, arm):
        self.loader, self.additions, self.schedule, self.arm = loader, additions, schedule, arm

    def arrays(self, *args):
        return self.loader.arrays(*args)

    def step(self, domain, arm, step, seed):
        assert arm == 'G0' and seed == 42
        return SimpleNamespace(indices=self.schedule[self.arm if domain == 'orig' else 'trans'][step])

    def torch_graph(self, domain, split, device):
        a = self.loader.arrays(domain, split)
        xraw = a['x39']
        x = torch.empty(xraw.shape, dtype=torch.float32, device=device)
        for lo in range(0,len(xraw),65536):
            hi = min(lo+65536,len(xraw))
            x[lo:hi].copy_(torch.from_numpy(normalized(np.array(xraw[lo:hi]), self.loader.normalization)))
        e = torch.tensor(a['edge_index'], dtype=torch.long, device=device)
        y = torch.tensor(a['y'], dtype=torch.long, device=device)
        if (domain,split) == ('orig','train'):
            extra_x,extra_e = self.additions
            x = torch.cat((x,torch.tensor(extra_x,device=device)))
            e = torch.cat((e,torch.tensor(extra_e,device=device)),dim=1)
            y = torch.cat((y,torch.zeros(len(extra_x),dtype=torch.long,device=device)))
        return dict(x=x,edge=e,y=y)


def prepare(loader):
    train, val = [rows(ASSETS/f'{split}_NEGATIVE_POOL.csv') for split in ('TRAIN','VAL')]
    assert len(train)==32 and len(val)==24
    assert all(r['split']=='train' and r['optimizer_eligible']=='1' for r in train)
    assert all(r['split']=='val' and r['optimizer_eligible']=='0' for r in val)
    assert not {r['host'] for r in train} & {r['host'] for r in val}
    source = {r['view']:r for r in read(ASSETS/'MANIFEST.json')}
    proof = {r['view']:r for r in rows(ASSETS/'CEC_RESULTS.csv')}
    by_view = defaultdict(list)
    for r in train:
        by_view[r['view']].append(r)
    a = loader.arrays('orig','train')
    n = len(a['y'])
    offset = n
    extra_x, extra_e, candidates = [], [], defaultdict(list)
    for view, group in sorted(by_view.items()):
        path = ASSETS/'graphs'/f'{view}.npz'
        c = source[view]
        assert proof[view]['unproven']=='0' and proof[view]['target_sha']==c['target_sha256']
        assert digest(path) == group[0]['graph_sha'] and digest(ROOT/c['target'])==c['target_sha256']
        with np.load(path) as g:
            x, edge = g['x39'], g['edge_index']
            assert edge.min()>=0 and edge.max()<len(x)
            extra_x.append(normalized(x,loader.normalization))
            extra_e.append(edge+offset)
            for r in group:
                k = int(r['row'])
                assert r['label']=='0' and r['trusted']=='1' and r['netlist_sha']==c['target_sha256']
                assert r['graph_sha']==group[0]['graph_sha'] and c['split']=='train' and r['host']==c['host']
                assert g['physical_names'][k]==r['node'] and k in g['region_rows']
                candidates[r['host']].append((k+offset,r,x[k]))
            offset += len(x)
    assert sorted(map(len,candidates.values())) == [10,22]
    # Background donors are trusted physical negatives in original Trojan views of the same host.
    donor = {}
    for host in candidates:
        mask = np.zeros(n,dtype=bool)
        for v in loader.feature_contract['shared_inputs']['orig_train']['views']:
            if v['view'].split('__')[0] == host and '__inj' in v['view']:
                mask[v['start']:v['physical_stop']] = True
        donor[host] = mask & a['trusted'] & a['physical'] & (a['y']==0)
    steps = [loader.step('orig','G0',i) for i in range(200)]
    orig = np.stack([r.indices for r in steps])
    trans = np.stack([loader.step('trans','G0',i).indices for i in range(200)])
    swapped = orig.copy()
    rng = np.random.default_rng(42)
    exposure, removed, audit = Counter(), set(), []
    # 110 slots per host, at most one per host and step, no repeated donor.
    order = rng.permutation(200)
    for host, members in sorted(candidates.items()):
        taken = set()
        gate_ids = a['x39'][:,:25].argmax(axis=1)
        for k in range(110):
            rid,r,rx = members[k % len(members)]
            for step in map(int, np.roll(order, -k)):
                if step in taken:
                    continue
                start = len(steps[step].positive)
                stop = start + len(steps[step].common_negative)
                ids = orig[step,start:stop]
                slots = np.flatnonzero(donor[host][ids])
                slots = [i for i in slots if int(ids[i]) not in removed]
                if slots:
                    break
            else:
                raise ValueError((host,k,r['node']))
            taken.add(step)
            # Prefer the same gate type, then the nearest frozen context.
            features = a['x39'][ids[slots],25:]
            dist = np.square((features-rx[25:])/loader.normalization['std'][25:]).sum(axis=1)
            mismatch = gate_ids[ids[slots]]!=rx[:25].argmax()
            slot = start + int(slots[np.lexsort((dist,mismatch))[0]])
            did = int(orig[step,slot])
            assert swapped[step,slot]==did
            swapped[step,slot] = rid
            removed.add(did)
            exposure[rid] += 1
            audit.append(dict(step=step+1,host=host,view=r['view'],node=r['node'],row=rid,donor=did,slot=slot,
                              same_gate=int(gate_ids[did]==rx[:25].argmax())))
    assert len(exposure)==32 and sorted(Counter(exposure.values()).items())==[(5,22),(11,10)]
    for i,step in enumerate(steps):
        changes = np.flatnonzero(orig[i]!=swapped[i])
        assert len(changes) <= 2
        assert (changes >= len(step.positive)).all() and (swapped[i,changes]>=n).all()
        assert len(np.unique(swapped[i]))==len(swapped[i])
    with (OUT/'SWAPS.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(audit[0])); w.writeheader(); w.writerows(audit)
    np.savez_compressed(OUT/'SCHEDULE.npz',base=orig,swap=swapped,trans=trans)
    stats = dict(train_candidates=len(exposure), validation_candidates=len(val), replacements=len(audit),
                 orig_budget=orig.shape[1], trans_budget=trans.shape[1],
                 orig_positives=len(steps[0].positive),
                 trans_positives=len(loader.step('trans','G0',0).positive),
                 active_steps=int((orig!=swapped).any(axis=1).sum()),
                 host_exposure=dict(Counter(r['host'] for r in audit)), node_exposure=dict(Counter(exposure.values())),
                 graphs=len(by_view), appended_graph_nodes=offset-n, unique_donors=len(removed),
                 same_gate=sum(r['same_gate'] for r in audit),
                 schedule_sha=digest(OUT/'SCHEDULE.npz'))
    write_json(OUT/'PREFLIGHT.json',stats)
    print('PREFLIGHT',stats,flush=True)
    return (np.concatenate(extra_x),np.concatenate(extra_e,axis=1)), dict(base=orig,swap=swapped,trans=trans)


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    OUT.mkdir(exist_ok=True)
    loader = t.FiveGroupLoader()
    t.T.CONTRACT,t.T.NORM,t.T.arrays = loader.feature_contract,loader.normalization,loader.arrays
    additions,schedule = prepare(loader)
    if '--preflight' in sys.argv:
        return
    cones = t.CL.cone_tensors(t.CL.load_cones('train','D',trust=np.asarray(loader.arrays('trans')['trusted'])))
    for arm in ('base','swap'):
        t.OUT = OUT/arm
        t.OUT.mkdir(exist_ok=True)
        if (t.OUT/'RESULT.json').exists():
            assert read(t.OUT/'RESULT.json')['schedule_sha']==digest(OUT/'SCHEDULE.npz')
            continue
        print('START',arm,flush=True)
        result = t.run('NC',PairedLoader(loader,additions,schedule,arm),cones,seed=42)
        assert len(result['history'])==40
        assert np.isfinite([[r['orig'],r['trans'],r['val_ap']] for r in result['history']]).all()
        result['schedule_sha']=digest(OUT/'SCHEDULE.npz')
        write_json(t.OUT/'RESULT.json',result)
        print('DONE',arm,result['best_step'],result['seconds'],flush=True)


if __name__=='__main__':
    main()
