# -*- coding: utf-8 -*-
"""_probe_a1e.py —— 直接定位 aig 视图的那 1 个正节点，并算各 op 的"标签传输覆盖率"。

label_transport.json['trans_labels_from_orig'] 与 class_map_trans_transported.json 的键都是
**全局 trans 节点索引**；metadata_trans.json 的 file_ids 给出每个节点属于哪个视图。
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

FT = Path("generate_trans/folds/hosts_beta2/data/for_train")
OUT = Path("10.15/01_数据与标签/A1_变换统计/_probe_a1e.txt")
L = []


def sec(t):
    L.append("=" * 12 + " " + t + " " + "=" * 12)


mt = json.loads((FT / "metadata_trans.json").read_text(encoding="utf-8"))
L.append("metadata_trans 顶层键: " + ", ".join(list(mt)))
file_ids = list(mt["file_ids"])
n = len(file_ids)
L.append(f"节点数 {n}")
for k in list(mt):
    v = mt[k]
    if isinstance(v, (list, dict)):
        L.append(f"  {k}: {type(v).__name__} len={len(v)} 样例={json.dumps(v[:2] if isinstance(v, list) else list(v.items())[:2], ensure_ascii=False)[:200]}")
    else:
        L.append(f"  {k}: {v!r}")

cm = json.loads((FT / "class_map_trans_transported.json").read_text(encoding="utf-8"))
L.append(f"class_map_trans_transported 条目 {len(cm)}（键=全局索引）")

# 每个视图的正节点、被传输覆盖的节点
pos_by_view, cov_by_view, nodes_by_view = Counter(), Counter(), Counter()
for i, v in enumerate(file_ids):
    nodes_by_view[v] += 1
    if str(i) in cm:
        cov_by_view[v] += 1
        if int(cm[str(i)]) == 1:
            pos_by_view[v] += 1
L.append(f"视图数 {len(nodes_by_view)}")

sec("逐 op 汇总（标签传输覆盖率 = 被传输覆盖的节点/该视图节点）")
agg = defaultdict(lambda: [0, 0, 0, 0, 0])   # views, nodes, covered, pos, views_with_pos
for v in nodes_by_view:
    op = v.split("__")[-1]
    a = agg[op]
    a[0] += 1
    a[1] += nodes_by_view[v]
    a[2] += cov_by_view[v]
    a[3] += pos_by_view[v]
    a[4] += 1 if pos_by_view[v] else 0
L.append(f"{'op':<14}{'views':>6}{'nodes':>9}{'covered':>9}{'传输覆盖%':>10}{'pos':>6}{'有pos视图':>9}")
for op, a in sorted(agg.items()):
    L.append(f"{op:<14}{a[0]:>6}{a[1]:>9}{a[2]:>9}{100*a[2]/max(1,a[1]):>9.1f}%{a[3]:>6}{a[4]:>9}")

sec("aig 视图那个正节点是谁")
pfx = mt.get("prefixes") or []
for target in ("rs232t1000__injalpha_d1_s42__ys_aig", "rs232t1000__injalpha_d1_s42__rwdecomp3_d1_s42",
               "rs232t1000__injalpha_d1_s42__ys_rt"):
    idxs = [i for i, v in enumerate(file_ids) if v == target]
    if not idxs:
        L.append(f"{target}: 不在图里")
        continue
    pos = [i for i in idxs if str(i) in cm and int(cm[str(i)]) == 1]
    cov = [i for i in idxs if str(i) in cm]
    L.append(f"\n{target}")
    L.append(f"  节点 {len(idxs)}｜被传输覆盖 {len(cov)} ({100*len(cov)/len(idxs):.1f}%)｜正节点 {len(pos)}")
    for i in pos[:8]:
        p = pfx[i] if i < len(pfx) else None
        L.append(f"    正节点 idx={i} prefix={json.dumps(p, ensure_ascii=False)[:300]}")
    # 该视图前 3 个节点的 prefix 长什么样
    for i in idxs[:2]:
        L.append(f"    普通节点 idx={i} prefix={json.dumps(pfx[i] if i < len(pfx) else None, ensure_ascii=False)[:200]}")

OUT.write_text("\n".join(L), encoding="utf-8")
print("done")
