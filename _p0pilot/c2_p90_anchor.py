"""C2 compression loss with selectable historical or per-view anchors."""
import hashlib
import json

import numpy as np
import torch
import torch.nn.functional as F


def load_cones(c2_dir, fold, mode):
    original = c2_dir / f'{fold}_cones.npz'
    if mode == 'legacy':
        path = original
    elif mode == 'view-q25':
        repaired_dir = c2_dir.parent / 'c2_p90_view_repair_20261112'
        path = repaired_dir / original.name
        manifest = json.loads((repaired_dir / 'BUILD.json').read_text(encoding='utf-8'))['folds'][fold]
        for p, key in ((original, 'old_sha256'), (path, 'repaired_sha256')):
            with p.open('rb') as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() != manifest[key]:
                    raise ValueError(f'cone asset hash mismatch: {p}')
    else:
        raise ValueError(f'unknown anchor mode: {mode}')
    with np.load(path) as data:
        return {key: data[key] for key in ('rows', 'ptr', 'label', 'view')}


class CompressionLoss:
    def __init__(self, cones, train_views, anchor_mode, device, rank_mode='legacy'):
        if anchor_mode not in ('legacy', 'view-q25'):
            raise ValueError(f'unknown anchor mode: {anchor_mode}')
        if rank_mode not in ('legacy', 'exact'):
            raise ValueError(f'unknown rank mode: {rank_mode}')
        self.anchor_mode = anchor_mode
        self.rank_mode = rank_mode
        self.rows = torch.as_tensor(cones['rows'], device=device)
        self.labels = torch.as_tensor(cones['label'], dtype=torch.float32, device=device)
        counts = torch.as_tensor(np.diff(cones['ptr']), device=device)
        self.seg = torch.repeat_interleave(torch.arange(len(self.labels), device=device), counts)
        self.positions = torch.arange(len(self.rows), device=device)
        self.rank = torch.clamp(((counts - 1) * 0.1).long(), min=0)
        self.exact_positions = torch.as_tensor(cones['ptr'][:-1], device=device) + (counts - 1) // 10
        self.negative = self.labels == 0
        self.positive_by_view = []
        if anchor_mode == 'view-q25':
            views, indexes = np.unique(cones['view'], return_inverse=True)
            if not set(views) <= set(train_views):
                raise ValueError('cone view is not in the fold training graph')
            self.view_indexes = torch.as_tensor(indexes, device=device)
            self.positive_by_view = [torch.as_tensor(np.flatnonzero((indexes == i) & (cones['label'] == 1)),
                                                     device=device) for i in range(len(views))]

    def cone_scores(self, margin):
        values = margin.index_select(0, self.rows)
        maxima = margin.new_full((len(self.labels),), -1e9)
        maxima.scatter_reduce_(0, self.seg, values, reduce='amax')
        if self.rank_mode == 'exact':
            # Sort scores first, then preserve score order within each integer segment.
            score_order = torch.argsort(values, descending=True, stable=True)
            cone_order = torch.argsort(self.seg[score_order], stable=True)
            selected = score_order[cone_order[self.exact_positions]]
            return maxima, values[selected]
        # Retain the historical operator to reproduce earlier comparisons.
        order = torch.argsort(self.seg * 1e6 - values)
        segments = self.seg[order]
        starts = torch.full((len(self.labels),), len(self.rows), device=margin.device)
        starts.scatter_reduce_(0, segments, self.positions, reduce='amin')
        selected = self.positions - starts[segments] == self.rank[segments]
        p90 = margin.new_zeros(len(self.labels))
        p90[segments[selected]] = values[order[selected]]
        return maxima, p90

    def compression(self, p90):
        if self.anchor_mode == 'legacy':
            anchors = torch.zeros_like(p90)
        else:
            # No positive cone in this view: use the original constant zero.
            per_view = torch.stack([torch.quantile(p90[ids], 0.25) if ids.numel() else p90.new_zeros(())
                                    for ids in self.positive_by_view])
            anchors = per_view[self.view_indexes]
        selected = self.negative & (p90 > anchors)
        compression = (F.relu(p90[selected] - anchors[selected] + 0.5).square().mean()
                       if selected.any() else p90[:0].sum())
        return compression, anchors, selected

    def __call__(self, logits):
        margin = logits.float()[:, 1] - logits.float()[:, 0]
        maxima, p90 = self.cone_scores(margin)
        bce = F.binary_cross_entropy_with_logits(maxima, self.labels, pos_weight=margin.new_tensor(10.))
        compression, _, _ = self.compression(p90)
        return bce, compression
