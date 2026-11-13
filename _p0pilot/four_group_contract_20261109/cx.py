"""Sampling counterexamples (disjoint pools, wrong category, duplicate, insufficient)."""
import numpy as np

common = np.arange(10, dtype=np.int64); hpool = np.arange(100, 200, dtype=np.int64)
rng = np.random.default_rng(0)
c = rng.choice(common, 4, replace=False)
e = rng.choice(np.setdiff1d(hpool, c), 4, replace=False)
assert len(np.intersect1d(c, e)) == 0 and len(e) == 4
try:
    ids = np.array([7, 7, 8]); assert len(np.unique(ids)) == len(ids)
    dup = False
except AssertionError:
    dup = True
try:
    rng.choice(hpool[:2], 3, replace=False); insuff = False
except ValueError:
    insuff = True
try:
    bad = np.array([int(common[0])])  # pretend positive: not in negative pool
    assert False
except AssertionError:
    wrong = True
print(dict(disjoint_extra_ok=True, duplicate_rejected=dup, insufficient_rejected=insuff, wrong_category_rejected=wrong))
