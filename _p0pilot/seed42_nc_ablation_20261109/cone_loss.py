"""Frozen cone MIL loss: margin score, max over trusted physical members, BCEWithLogits."""
import csv
import hashlib
from pathlib import Path

import numpy as np
import torch

OUT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\seed42_supervised_prep_20261109')


def load_cones(split='train', kind='D', trust=None, min_phys=2):
    rows = []
    with (OUT / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != split or r['kind'] != kind or int(r['label']) < 0 or int(r['n_phys']) < min_phys:
                continue
            mem = [int(x) for x in r['phys_rows'].split('|')
                   if x and (trust is None or bool(trust[int(x)]))]
            if not mem:
                continue
            rows.append((r['cone_id'], int(r['label']), mem))
    return rows


def cone_tensors(rows, device='cuda'):
    labels = np.array([lab for _, lab, _ in rows], np.float32)
    flat, ptr = [], [0]
    for _, _, mem in rows:
        flat.extend(mem); ptr.append(len(flat))
    flat = np.array(flat, np.int64)
    idx = torch.as_tensor(flat, dtype=torch.long, device=device)
    lab = torch.as_tensor(labels, dtype=torch.float32, device=device)
    seg = torch.repeat_interleave(torch.arange(len(rows), device=device),
                                  torch.as_tensor(np.diff(ptr), dtype=torch.long, device=device))
    sha = hashlib.sha256(flat.tobytes()).hexdigest()
    return dict(rows=rows, labels=labels, flat=flat, idx=idx, lab=lab, seg=seg, sha=sha,
                pos=int(labels.sum()), neg=int((labels == 0).sum()), members=int(len(flat)))


def margin_of(logits):
    return logits.float()[:, 1] - logits.float()[:, 0]


def cone_score(margin, cones):
    cmax = torch.full((len(cones['rows']),), -1e9, device=margin.device)
    cmax.scatter_reduce_(0, cones['seg'], margin.index_select(0, cones['idx']), reduce='amax', include_self=True)
    return cmax


def cone_loss(logits, cones, pos_weight=10.0):
    return torch.nn.functional.binary_cross_entropy_with_logits(
        cone_score(margin_of(logits), cones), cones['lab'],
        pos_weight=torch.tensor(pos_weight, device=logits.device))
