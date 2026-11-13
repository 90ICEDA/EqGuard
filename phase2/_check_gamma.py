# -*- coding: utf-8 -*-
"""核对 hosts_gamma fold：按视图统计 alignment 覆盖率 / label1 / 未覆盖节点的名字前缀。"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2.name_index import build_name_index  # noqa: E402

W = Path("generate_trans/folds/hosts_gamma")
FT = W / "data" / "for_train"

meta = json.loads((W / "data" / "processed" / "dataset_meta.json").read_text(encoding="utf-8"))
fids = json.loads((FT / "metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
align = json.loads((FT / "alignment.json").read_text(encoding="utf-8"))
lab = json.loads((FT / "class_map_trans_transported.json").read_text(encoding="utf-8"))
try:
    idx = build_name_index(W)
except Exception as exc:  # noqa: BLE001
    print("[WARN] name_index 失败：", exc)
    idx = {"trans": {}}

n_node = Counter(fids)
t_cov = defaultdict(set)
for o, t in align:
    t_cov[fids[t]].add(t)
lab1 = defaultdict(int)
for t_str, v in lab.items():
    if int(v) == 1:
        lab1[fids[int(t_str)]] += 1

rows = []
for v in sorted(n_node):
    cov = len(t_cov.get(v, ()))
    rows.append((v, n_node[v], cov, n_node[v] - cov, lab1.get(v, 0)))
tot_n = sum(r[1] for r in rows); tot_c = sum(r[2] for r in rows); tot_l = sum(r[4] for r in rows)
print("视图数 %d｜节点 %d｜被血缘覆盖 %d（%.1f%%）｜label1 合计 %d"
      % (len(rows), tot_n, tot_c, 100 * tot_c / tot_n, tot_l))
print()
print("--- 按视图类型汇总 ---")
import re
def kind(v):
    if "__rwbubble" in v: return "rw_bubble(改写)"
    if "__rwdecomp3" in v: return "rw_decomp3(改写)"
    if "ctlmatch" in v: return "ctl_matched(对照)"
    if "ctlxor" in v or "ctldup" in v: return "ctl_nontrig(对照)"
    return "other"
agg = defaultdict(lambda: [0, 0, 0, 0])
for v, n, c, u, l in rows:
    a = agg[kind(v)]; a[0] += 1; a[1] += n; a[2] += c; a[3] += l
for k, (nv, n, c, l) in sorted(agg.items()):
    print("  %-18s 视图%3d｜节点%8d｜覆盖%8d(%5.1f%%)｜label1=%5d"
          % (k, nv, n, c, 100 * c / max(n, 1), l))
print()
print("--- 未覆盖节点的名字前缀（Top12）---")
pref = Counter()
for v, n, c, u, l in rows:
    nm = idx["trans"].get(v)
    if not nm:
        continue
    covered = t_cov.get(v, set())
    for name, i in nm.items():
        if i not in covered:
            pref[re.sub(r"\d+$", "#", name)[:14]] += 1
for p, c in pref.most_common(12):
    print("   %-16s %d" % (p, c))
print()
print("--- label1 明细（非零的视图）---")
for v, n, c, u, l in rows:
    if l:
        print("   %-52s n=%6d label1=%4d covered=%6d uncovered=%6d" % (v, n, l, c, u))
