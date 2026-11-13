"""sat_role_status.py —— B07：给**已 SAT 证明的节点对**打角色标签 ✓（`role_status.csv` ✓）。

角色定义 ✓（可机器判定 ✓，来源 = **插入记录** + **结构锥** ✓）：
  · `trusted_trojan`  ✓ 网名属木马子电路（`Trojan*` ✓）**且**该对 SAT `proved` ✓
      ⇒ 可进 `L_eq`（等价一致性）✓
  · `trusted_benign`  ✓ 非木马网 ✓ **且其扇入锥不含任何木马网** ✓ **且**该对 `proved` ✓
      ⇒ 可进 `L_eq`（等价一致性）✓（**不是**"可当负样本" ✗ —— 负样本另有 A4 对照 ✓）
  · `mixed`           ⚠️ 非木马网，但扇入锥里**含**木马网 ⇒ **不**进 `L_eq` ✗（标签会打架 ✗）
  · `unknown`         ⚠️ 对未证明（`differ`/超时 ✓）或网不在图里 ✗ ⇒ **一律不进损失** ✗

⚠️ 与 A6 的关系 ✓：**训练用标签**来自 A6（`trust` 掩码 ✓，30.68% ✓）；
本表只回答"**这对网能不能拿来做一致性**"✓，**不**改训练标签 ✗。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
LOGS = BASE / "logs"


def load_graph(js: Path):
    """读 yosys JSON ✓（结构探针用 ✓，与 sat_functional_relations.py 同源 ✓）。"""
    d = json.loads(js.read_text(encoding="utf-8"))
    mod = d["modules"][list(d["modules"])[0]]
    names: dict[int, str] = {}
    for nm, info in mod.get("netnames", {}).items():
        for b in info.get("bits", []):
            if isinstance(b, int) and (b not in names or names[b].startswith("$")):
                names[b] = nm
    drv: dict[int, str] = {}
    for cname, cell in mod.get("cells", {}).items():
        for port, bits in cell.get("connections", {}).items():
            if port in ("Y", "Q", "QN"):
                for b in bits:
                    if isinstance(b, int):
                        drv.setdefault(b, cname)
    cells = mod["cells"]
    return names, drv, cells


def trojan_cone_sets(names, drv, cells, depth: int = 10, cap: int = 20000):
    """对每个 net 算"扇入锥里是否含木马网" ✓（反向 BFS ✓，带缓存 ✓）。"""
    bit_of = {}
    for b, n in names.items():
        bit_of.setdefault(n, b)

    memo: dict[int, bool] = {}

    def has_trojan(bit: int) -> bool:
        if bit in memo:
            return memo[bit]
        stack, local = [bit], set()
        found = False
        while stack and len(local) < cap:
            b = stack.pop()
            if b in local:
                continue
            local.add(b)
            cname = drv.get(b)
            if cname is None:
                continue
            for port, bits in cells[cname].get("connections", {}).items():
                if port in ("Y", "Q", "QN"):
                    continue
                for nb in bits:
                    if not isinstance(nb, int):
                        continue
                    nm = names.get(nb, "")
                    if "trojan" in nm.lower():
                        found = True
                        stack = []
                        break
                    stack.append(nb)
                if found:
                    break
        memo[bit] = found
        return found

    return bit_of, has_trojan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(BASE / "tables/node_pairs.csv"))
    ap.add_argument("--out", default=str(BASE / "tables/role_status.csv"))
    a = ap.parse_args()

    df = pd.read_csv(a.pairs, encoding="utf-8-sig").fillna("")
    df = df[df["net"].astype(str).str.len() > 0]
    cache: dict[tuple[str, str], tuple] = {}
    rows = []
    for (host, inst), g in df.groupby(["host", "inst"]):
        cand = sorted(LOGS.glob(f"{host}__{inst}_d1_s42__*ys_id.json"))
        js = cand[0] if cand else LOGS / f"{host}__{inst}_d1_s42__ys_id.json"
        if not js.exists():
            print(f"[warn] 缺 {js.name} ✗ → {host}/{inst} 全记 unknown")
            for r in g.itertuples():
                rows.append(dict(host=host, inst=inst, pair=r.pair, net=r.net,
                                 sat_status=r.status, role="unknown",
                                 reason="no_graph"))
            continue
        key = (host, inst)
        if key not in cache:
            cache[key] = load_graph(js)
        names, drv, cells = cache[key]
        bit_of, has_trojan = trojan_cone_sets(names, drv, cells)
        for r in g.itertuples():
            net, st = str(r.net), str(r.status)
            is_tj = "trojan" in net.lower()
            bit = bit_of.get(net)
            if st != "proved":
                role, why = "unknown", f"sat_{st}"
            elif bit is None:
                role, why = "unknown", "net_not_in_graph"
            elif is_tj:
                role, why = "trusted_trojan", "trojan_name+proved"
            elif has_trojan(bit):
                role, why = "mixed", "cone_contains_trojan"
            else:
                role, why = "trusted_benign", "clean_cone+proved"
            rows.append(dict(host=host, inst=inst, pair=r.pair, net=net,
                             sat_status=st, role=role, reason=why))
    out = pd.DataFrame(rows)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"[out] {a.out}（{len(out)} 行 ✓）")
    print(out["role"].value_counts().to_string())
    print("\n按 host/inst/pair 的可用于 L_eq 的对数（trusted_* ✓）：")
    ok = out[out["role"].isin(["trusted_trojan", "trusted_benign"])]
    print(ok.groupby(["host", "inst", "pair"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
