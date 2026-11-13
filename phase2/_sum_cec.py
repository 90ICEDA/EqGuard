# -*- coding: utf-8 -*-
"""汇总 rw_cec_all.csv（等价实现的 CEC 结果）。"""
import collections
import csv
from pathlib import Path

p = Path("rw_cec_all.csv")
rows = list(csv.DictReader(open(p, encoding="utf-8", errors="replace")))
print("total pairs:", len(rows))
by = collections.defaultdict(collections.Counter)
for r in rows:
    c = r.get("cecline") or ""
    st = "PASS" if "PASS" in c else ("FAIL" if "FAIL" in c else "EMPTY")
    by[(r["host"], r["mode"])][st] += 1
for k in sorted(by):
    print("   %-14s %-9s %s" % (k[0], k[1], dict(by[k])))
bad = [r for r in rows if "PASS" not in (r.get("cecline") or "")]
print("FAIL/EMPTY:", len(bad))
for r in bad[:8]:
    print("     ", r["host"], r["mode"], r["src_view"], "|", (r.get("cecline") or "")[:90])
