"""Real-data benchmark with byte equality; never rewrites historical variants."""
import importlib.machinery
import importlib.util
import json
import time
from pathlib import Path
import numpy as np
import build_p0clean4 as fast


def main():
    path=Path(__file__).with_name('build_p0clean4.py.bak_20261025_audit')
    loader=importlib.machinery.SourceFileLoader('slow_feature_builder',str(path))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    slow=importlib.util.module_from_spec(spec)
    loader.exec_module(slow)
    meta=fast.WORK/'data/for_train/metadata_trans.json'
    t=time.perf_counter()
    oldviews,oldvid=slow.view_blocks(meta)
    slow_view_s=time.perf_counter()-t
    t=time.perf_counter()
    views,vid=fast.view_blocks(meta)
    groups=fast.grouped_indices(vid,len(views))
    fast_view_s=time.perf_counter()-t
    assert views==oldviews and np.array_equal(vid,oldvid)
    x=np.load(fast.PT/'satrel_node_feats_sat_p0clean4_safe.npy',mmap_mode='r')
    # Use four actual count supports, including zeros and non-contiguous views.
    columns=[(x[:,j]*100).astype(np.int32) for j in range(7,11)]
    t=time.perf_counter()
    original=[slow.log_norm(c,oldvid,len(oldviews)) for c in columns]
    slow_norm_s=time.perf_counter()-t
    t=time.perf_counter()
    optimized=[fast.log_norm(c,vid,len(views),groups) for c in columns]
    fast_norm_s=time.perf_counter()-t
    assert all(a.tobytes()==b.tobytes() for a,b in zip(original,optimized))
    out=fast.T/'audit_20261025/feature_group_benchmark.json'
    out.write_text(json.dumps(dict(nodes=len(vid),views=len(views),columns=4,
                                   legacy_view_index_s=slow_view_s,fast_index_including_groups_s=fast_view_s,
                                   legacy_normalization_s=slow_norm_s,fast_normalization_s=fast_norm_s,
                                   normalization_speedup=slow_norm_s/fast_norm_s,
                                   byte_identical=True),indent=2))
    print(out.read_text())


if __name__=='__main__':
    main()
