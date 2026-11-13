# -*- coding: utf-8 -*-
"""_probe_a1d.py —— 看 label_transport / provenance_stats，回答"aig 为什么只剩 1 个正节点"。"""
import json
from pathlib import Path

FT = Path("generate_trans/folds/hosts_beta2/data/for_train")
OUT = Path("10.15/01_数据与标签/A1_变换统计/_probe_a1d.txt")
L = []


def sec(t):
    L.append("=" * 12 + " " + t + " " + "=" * 12)


def load(n):
    return json.loads((FT / n).read_text(encoding="utf-8"))


for name in ("provenance_stats.json", "label_transport.json", "class_map_trans.json"):
    sec(name)
    try:
        j = load(name)
    except Exception as e:  # noqa: BLE001
        L.append(f"<失败 {type(e).__name__}: {e}>")
        continue
    if isinstance(j, dict):
        ks = list(j)
        L.append(f"dict len={len(ks)}；前 8 键: {ks[:8]}")
        k0 = ks[0]
        v0 = j[k0]
        L.append(f"样例 {k0!r} -> {json.dumps(v0, ensure_ascii=False)[:600]}")
    else:
        L.append(f"{type(j).__name__} len={len(j)}；[0]={json.dumps(j[0], ensure_ascii=False)[:400]}")

sec("aig 视图的标签传输明细")
lt = load("label_transport.json")
aig_keys = [k for k in lt if "__ys_aig" in k] if isinstance(lt, dict) else []
L.append(f"aig 视图键 {len(aig_keys)} 个；例：{aig_keys[:3]}")


def positive_entries(obj, path="", out=None, depth=0):
    """递归找值为 1 / 'trojan' 的条目。"""
    out = out if out is not None else []
    if depth > 4:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and int(v) == 1:
                out.append((f"{path}/{k}", v))
            elif str(v).lower() in ("trojan", "1.0", "true"):
                out.append((f"{path}/{k}", v))
            else:
                positive_entries(v, f"{path}/{k}", out, depth + 1)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:200]):
            positive_entries(v, f"{path}[{i}]", out, depth + 1)
    return out


if aig_keys:
    target = next((k for k in aig_keys if "injalpha" in k), aig_keys[0])
    v = lt[target]
    L.append(f"目标视图 {target}")
    L.append(f"  顶层类型 {type(v).__name__}；"
             f"{json.dumps(v, ensure_ascii=False)[:400] if not isinstance(v, dict) else list(v)[:12]}")
    pos = positive_entries(v)
    L.append(f"  正标签条目 {len(pos)} 个：")
    for p, val in pos[:25]:
        L.append(f"    {p} = {val}")

OUT.write_text("\n".join(L), encoding="utf-8")
print("done")
