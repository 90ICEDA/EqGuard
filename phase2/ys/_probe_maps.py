"""_probe_maps.py（临时）—— 验证 `*.map.json` 的 inst_prov 能否把 `.pt` 节点名反推回原始 RTL 名。"""

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import json
import sys
from pathlib import Path

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "generate_trans/folds/hosts_bt31"

# 1) 索引所有 map.json：stem -> path
maps = {}
for p in (ROOT / "generate_trans").rglob("*.map.json"):
    maps.setdefault(p.name[:-len(".map.json")], []).append(p)
print("map.json 总数", sum(len(v) for v in maps.values()), "唯一视图", len(maps))

names = (BASE / "data/processed/node_names_trans.txt").read_text(encoding="utf-8").split("\n")
meta = json.loads((BASE / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
fid = meta["file_ids"]
views = sorted(set(fid))
miss = [v for v in views if v not in maps]
print(f"视图 {len(views)}｜有 map.json {len(views) - len(miss)}｜缺 {len(miss)}")
print("缺的前 5 个:", miss[:5])

import pandas as pd
sw = pd.read_csv(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/node_pairs_sweep.csv",
                 encoding="utf-8-sig")

# 2) 抽三个组算 hit rate
for host, inst, pair in (("rs232t1000", "injalpha", "ys_id:ys_abc"),
                         ("rs232t1000", "injepsilon", "ys_id:ys_opt"),
                         ("s15850t100", "injalpha", "ys_id:ys_abc")):
    g = sw[(sw.host == host) & (sw.inst == inst) & (sw.pair == pair)]
    if g.empty:
        print(f"[skip] {host}|{inst}|{pair} 无行")
        continue
    ra, rb = [x.strip() for x in pair.split(":")]
    for rcp, col in ((ra, "net_a"), (rb, "net_b")):
        cand = [v for v in views if v.startswith(f"{host}__{inst}_d1_s42__") and v.endswith(f"__{rcp}")]
        if not cand:
            print(f"[skip] 无视图 {host}|{inst}|{rcp}")
            continue
        v = cand[0]
        mp = maps.get(v, [])
        inst_prov = {}
        for p in mp:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:   # noqa: BLE001
                continue
            if d.get("inst_prov"):
                inst_prov = d["inst_prov"]
                break
        inv = {str(k): str(vv).lstrip("\\") for k, vv in inst_prov.items()}
        nodes = [names[i] for i, f in enumerate(fid) if f == v]
        orig = {inv[n] for n in nodes if n in inv}
        want = set(g[col].astype(str))
        print(f"{v}\n   nodes={len(nodes)} mapped={len(orig)} pairs={len(want)} "
              f"hit={len(want & orig)} map_json={len(mp)}")
