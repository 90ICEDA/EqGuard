"""Offline audit of the 29 mapping blockers (no SAT queries).

Reads only existing snapshots, P1 locator rows and query logs. Same names or
old P1 proved are candidates, never correspondence proofs.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T10 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round10"
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def clean(x) -> str:
    return str(x).lstrip("\\")


def load_raw(view: str):
    for base in (T11, T10):
        p = base / "structures" / view
        if (p / "source.json").exists():
            info = json.loads((p / "source.json").read_text(encoding="utf-8"))
            src = WORK / "trans" / f"{view}.v"
            assert info["source_sha"] == sha(src), view
            assert info["raw_sha"] == sha(p / "raw.json"), view
            m = next(iter(json.loads((p / "raw.json").read_text(
                encoding="utf-8"))["modules"].values()))
            return m, info, p
    # Offline fallback: new snapshot under round12, never touching old evidence.
    src = WORK / "trans" / f"{view}.v"
    p = T12 / "structures" / view
    p.mkdir(parents=True, exist_ok=True)
    raw = p / "raw.json"
    if not raw.exists():
        top = P0.module_name(src)
        script = (f'read_verilog "{P0.wsl(src)}"\nhierarchy -top {top}\n'
                  f'flatten\nproc -noopt\nwrite_json "{P0.wsl(raw)}"\n')
        (p / "prepare.ys").write_text(script, encoding="utf-8")
        log = P0.run_yosys(script, T12 / "logs" / f"{view}.prepare.log", timeout=180)
        if not raw.exists():
            raise RuntimeError(f"prepare failed {view}: {log[-300:]}")
    info = dict(view=view, source_sha=sha(src), raw_sha=sha(raw))
    (p / "source.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    m = next(iter(json.loads(raw.read_text(encoding="utf-8"))["modules"].values()))
    return m, info, p


class NetIndex:
    def __init__(self, m: dict):
        self.m = m
        self.nets = {clean(n): v for n, v in m.get("netnames", {}).items()}
        for n, p in m.get("ports", {}).items():
            self.nets.setdefault(clean(n), p)
        self.drv = defaultdict(list)
        self.outnet = defaultdict(list)
        for cn, c in m.get("cells", {}).items():
            con = c.get("connections", {})
            dirs = c.get("port_directions", {})
            for pin, bs in con.items():
                if dirs.get(pin) == "output" or (not dirs and pin in ("Y", "Q", "QN")):
                    for b in bs:
                        if isinstance(b, int):
                            self.drv[b].append((cn, str(c.get("type", "")), pin))
                            self.outnet[cn].append(b)
        self.by_src = defaultdict(list)
        for n, v in self.nets.items():
            a = (v.get("attributes") or {}).get("src", "")
            mm = re.search(r":(\d+)\.\d+-(\d+)\.\d+$", a or "")
            if mm:
                self.by_src[(int(mm.group(1)), int(mm.group(2)))].append(n)

    def bits(self, n: str):
        v = self.nets.get(clean(n))
        return [b for b in v.get("bits", []) if isinstance(b, int)] if v else []

    def aliases(self, n: str):
        bs = self.bits(n)
        if len(bs) != 1:
            return []
        return sorted(k for k, v in self.nets.items()
                      if k != clean(n) and
                      [b for b in v.get("bits", []) if isinstance(b, int)] == bs)

    def driver(self, n: str):
        bs = self.bits(n)
        if len(bs) != 1:
            return ""
        d = self.drv.get(bs[0], [])
        return d[0][0] + "|" + d[0][1] if d else ""

    def kind(self, n: str):
        n = clean(n)
        if n in self.m.get("ports", {}):
            return self.m["ports"][n].get("direction", "port")
        return "internal"


def base_cell(cell: str) -> str:
    return re.sub(r"_\d+$", "", clean(cell))


def p1_index(needed):
    out = defaultdict(list)
    p = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/node_pairs_sat_node.csv"
    for ch in pd.read_csv(p, chunksize=100000):
        ch = ch[ch.status == "proved"]
        for r in ch.itertuples():
            for a, b, na, nb in ((r.recipe_a, r.recipe_b, r.net_a, r.net_b),
                                 (r.recipe_b, r.recipe_a, r.net_b, r.net_a)):
                key = (r.host, r.inst_a, str(a), str(b), clean(na))
                if key in needed:
                    out[key].append(dict(partner=clean(nb), status=r.status,
                                         sig=r.sig_hex, log=r.log))
    return out



def main() -> int:
    T12.mkdir(parents=True, exist_ok=True)
    block = pd.read_csv(T11 / "blocking_issues.csv", encoding="utf-8-sig")
    inv = pd.DataFrame(json.loads((T10 / "plan.json").read_text(
        encoding="utf-8"))["inventory"])
    d = block.merge(inv, on="relation_id", how="left", suffixes=("_b", ""))
    needed, views = set(), set()
    for r in d.itertuples():
        p = Path(r.relation_id.split("|")[1]).stem.split("__")
        host, inst, recipe = p[0], p[1].removesuffix("_d1_s42"), p[-1].removeprefix("ys_")
        if isinstance(r.partner, str):
            partner = r.partner.split("__")[-1].removeprefix("ys_")
            for net in list(r.source_nets):
                needed.add((host, inst, recipe, partner, clean(net)))
        views.add(r.source_view)
        if isinstance(r.partner, str):
            views.add(r.partner)
    p1 = p1_index(needed)
    cache = {}
    rows = []
    for r in d.itertuples():
        if r.source_view not in cache:
            cache[r.source_view] = load_raw(r.source_view)
        a, ainfo, apath = cache[r.source_view]
        if isinstance(r.partner, str):
            if r.partner not in cache:
                cache[r.partner] = load_raw(r.partner)
            b, binfo, bpath = cache[r.partner]
        else:
            b = binfo = bpath = None
        ai = NetIndex(a)
        bi = NetIndex(b) if b else None
        p = Path(r.relation_id.split("|")[1]).stem.split("__")
        host, inst, recipe = p[0], p[1].removesuffix("_d1_s42"), p[-1].removeprefix("ys_")
        partner_recipe = (r.partner.split("__")[-1].removeprefix("ys_")
                          if isinstance(r.partner, str) else "")
        slots = []
        for j, (s, cand) in enumerate(zip(r.source_nets, r.mapped_nets)):
            s = clean(s)
            cand = "" if pd.isna(cand) else clean(cand)
            sb = ai.bits(s)
            src_drv, src_kind = ai.driver(s), ai.kind(s)
            exists = bool(bi and cand and cand in bi.nets)
            cb = bi.bits(cand) if exists else []
            drv = bi.driver(cand) if exists else ""
            alts = set()
            if exists:
                alts.add(cand)
                alts |= set(bi.aliases(cand))
            if bi and s in bi.nets:
                alts.add(s)
            if bi and src_drv:
                cell = src_drv.split("|")[0]
                for cn in bi.m.get("cells", {}):
                    if base_cell(cn) == base_cell(cell):
                        for bb in bi.outnet.get(cn, []):
                            for n2, v in bi.nets.items():
                                if ([x for x in v.get("bits", []) if isinstance(x, int)]
                                        == [bb]):
                                    alts.add(n2)
            v = ai.nets.get(s, {})
            attr = (v.get("attributes") or {}).get("src", "") or ""
            mm = re.search(r":(\d+)\.\d+-(\d+)\.\d+$", attr)
            if bi and mm:
                alts |= set(bi.by_src.get((int(mm.group(1)), int(mm.group(2))), []))
            alt_info = []
            for x in sorted(alts):
                if x not in bi.nets:
                    continue
                dd = bi.driver(x)
                alt_info.append(dict(
                    net=x, driver=dd, kind=bi.kind(x), same_name=(x == s),
                    same_base=bool(src_drv and dd and
                                   base_cell(src_drv.split("|")[0]) ==
                                   base_cell(dd.split("|")[0])),
                    alias=bool(exists and x in bi.aliases(cand))))
            p1rows = p1.get((host, inst, recipe, partner_recipe, s), [])
            diag = []
            if not sb:
                diag.append("source_net_missing")
            if cand and not exists:
                diag.append("candidate_absent")
            if exists and src_drv and drv and src_drv.split("|")[1] != drv.split("|")[1]:
                diag.append("candidate_driver_type_diff")
            if any(x["same_base"] and not x["same_name"] for x in alt_info):
                diag.append("same_base_cell_candidate")
            if any(not x["same_name"] and not x["same_base"] for x in alt_info):
                diag.append("local_alias_or_src_line_candidate")
            if p1rows:
                diag.append("legacy_P1_candidates")
            if not diag:
                diag.append("no_local_candidate")
            slots.append(dict(
                slot=j, source=s, source_bits=sb, source_kind=src_kind,
                source_driver=src_drv, source_aliases=ai.aliases(s)[:8],
                candidate=cand, candidate_exists=exists, candidate_bits=cb,
                candidate_driver=drv,
                candidate_aliases=bi.aliases(cand)[:8] if exists else [],
                alternatives=alt_info[:12], n_alternatives=len(alt_info),
                p1_candidates=p1rows[:8], diagnosis=";".join(diag)))
        rows.append(dict(
            relation_id=r.relation_id, role=r.role, category=r.category,
            failed_slot=r.failed_slot, partner=r.partner,
            source_view=r.source_view, source_snapshot=str(apath.relative_to(ROOT)),
            partner_snapshot=str(bpath.relative_to(ROOT)) if bpath else "",
            source_sha=ainfo["source_sha"],
            partner_sha=binfo["source_sha"] if binfo else "",
            source_nets=list(r.source_nets), mapped_nets=[str(x) for x in r.mapped_nets],
            mapping_origins=list(r.mapping_origins), slots=slots))


    (T12 / "blocker_audit.json").write_text(json.dumps(rows, ensure_ascii=False,
                                                       indent=2), encoding="utf-8")
    flat = []
    for r in rows:
        for s in r["slots"]:
            flat.append(dict(
                relation_id=r["relation_id"], role=r["role"],
                category=r["category"], failed_slot=r["failed_slot"],
                partner=r["partner"], slot=s["slot"], source=s["source"],
                source_kind=s["source_kind"], source_driver=s["source_driver"],
                candidate=s["candidate"], candidate_exists=s["candidate_exists"],
                candidate_driver=s["candidate_driver"],
                n_alternatives=s["n_alternatives"],
                alternatives=";".join(x["net"] for x in s["alternatives"]),
                p1_candidates=";".join(x["partner"] for x in s["p1_candidates"]),
                diagnosis=s["diagnosis"]))
    pd.DataFrame(flat).to_csv(T12 / "blocker_slots.csv", index=False,
                              encoding="utf-8-sig")
    fs = pd.DataFrame(flat)
    summary = dict(
        blockers=len(rows), by_category=d.category.value_counts().to_dict(),
        slots=len(fs), slots_with_alt=int((fs.n_alternatives > 1).sum()),
        candidate_absent=int((~fs.candidate_exists).sum()),
        legacy_candidates=int(fs.p1_candidates.ne("").sum()),
        diagnosis=pd.Series([x for s in fs.diagnosis for x in s.split(";")])
        .value_counts().to_dict())
    (T12 / "blocker_audit_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())