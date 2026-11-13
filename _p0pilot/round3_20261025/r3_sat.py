"""Shared bounded SAT runner for round 3.

Adds: stable query IDs, `-show` witness rows, `-dump_json` models, an explicit
per-query cache keyed by source digest + cell-map digest + constraints + timing.
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
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

CELLMAP = ROOT / "phase2/ys/sat_cells_map.v"
SCRIPT_VERSION = "r3.1"

_DIGEST = {}


def digest(path: Path) -> str:
    key = str(path)
    if key not in _DIGEST:
        _DIGEST[key] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""
    return _DIGEST[key]


def query_key(design: Path, cut: list[str], target: str, pattern: tuple,
              prove: int, timeout: int, seq: int = 1) -> str:
    payload = json.dumps(dict(design=digest(design), cellmap=digest(CELLMAP),
                              script=SCRIPT_VERSION, cut=cut, target=target,
                              pattern=list(pattern), prove=prove, timeout=timeout,
                              seq=seq), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def build_script(v: Path, top: str, cases: list[dict], timeout: int,
                 ports: set[str], dump_dir: Path | None = None,
                 emit: set[str] | None = None, flags: str = "",
                 cnf_dir: Path | None = None) -> list[str]:
    """Return the emitted query keys in marker order (qid = index + 1)."""
    lines = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten",
             "proc -noopt", f"select -module {top}"]
    renamed, rlines = {}, []

    def ref(nm: str) -> str:
        if nm in ports:
            return P0.sat_ref(nm)
        if nm in renamed:
            return renamed[nm]
        safe = f"fg_{len(renamed)}"
        renamed[nm] = safe
        rlines.append(f"rename {P0.sat_ref(nm)} {safe}")
        return safe

    for c in cases:
        c["_refs"] = {nm: ref(nm) for nm in c["cut"]}
        c["_tref"] = ref(c["target"])
    lines += rlines
    if renamed:
        lines.append("setattr -set keep 1 " + " ".join(f"w:{x}" for x in renamed.values()))
    lines += ["techmap -autoproc -map phase2/ys/sat_cells_map.v", "opt -fast"]
    emitted, qid = [], 0
    for c in cases:
        shows = " ".join(f"-show {r}" for r in c["_refs"].values()) + f" -show {c['_tref']}"
        for pat in c["patterns"]:
            sets = " ".join(f"-set {c['_refs'][nm]} {v}" for nm, v in zip(c["cut"], pat))
            for prove in (1, 0):
                key = query_key(v, c["cut"], c["target"], pat, prove, timeout)
                if emit is not None and key not in emit:
                    continue
                qid += 1
                emitted.append(key)
                dump = ""
                if dump_dir is not None:
                    dump = f" -dump_json {P0.wsl(dump_dir / f'q{qid:05d}.json')}"
                cnf = ""
                if cnf_dir is not None:
                    cnf_dir.mkdir(parents=True, exist_ok=True)
                    cnf = f" -dump_cnf {P0.wsl(cnf_dir / f'q{qid:05d}.cnf')}"
                lines += [f"log QRY{qid:05d}",
                          f"sat -seq 1 {sets} -prove {c['_tref']} {prove} "
                          f"-timeout {timeout} {shows}{dump}{cnf} {flags}".rstrip()]
    return "\n".join(lines) + "\n", emitted


_WITNESS = re.compile(r"^\s*(init|\d+)\s+(\\\S+)\s+(-?\d+)\s+(\S+)\s+([01xz]+)\s*$")


def parse_blocks(out: str) -> tuple[dict[int, str], dict[int, str]]:
    blocks: dict[int, list[str]] = {}
    cur = None
    for line in out.splitlines():
        m = re.match(r"^QRY(\d{5})$", line.strip())
        if m:
            cur = int(m.group(1))
            blocks[cur] = []
            continue
        if cur is not None:
            blocks[cur].append(line)
    status, witness = {}, {}
    for qid, lines in blocks.items():
        st = "no_result"
        for line in lines:
            if "no model found: SUCCESS" in line:
                st = "proved"
            elif "model found: FAIL" in line:
                st = "refuted"
            elif "TIMEOUT" in line:
                st = "timeout"
            elif line.startswith("ERROR"):
                st = "error"
        status[qid] = st
        rows = []
        for line in lines:
            m = _WITNESS.match(line)
            if m:
                rows.append(f"{m.group(1)}:{m.group(2).lstrip(chr(92))}={m.group(5)}")
        witness[qid] = ";".join(rows)
    return status, witness


def run_cases(v: Path, top: str, cases: list[dict], timeout: int,
              ports: set[str], log: Path, dump_dir: Path | None = None,
              cache_path: Path | None = None) -> dict:
    cache = {}
    if cache_path is not None and cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
    if dump_dir is not None:
        dump_dir.mkdir(parents=True, exist_ok=True)
    for c in cases:
        c["_keys"] = [query_key(v, c["cut"], c["target"], pat, prove, timeout)
                      for pat in c["patterns"] for prove in (1, 0)]
    emit = {k for c in cases for k in c["_keys"] if k not in cache}
    n_new = 0
    if emit:
        script, emitted = build_script(v, top, cases, timeout, ports, dump_dir, emit)
        log.parent.mkdir(parents=True, exist_ok=True)
        out = P0.run_yosys(script, log, timeout=1800)
        status, witness = parse_blocks(out)
        for qid, key in enumerate(emitted, 1):
            cache[key] = dict(status=status.get(qid, "no_result"),
                              witness=witness.get(qid, ""))
        n_new = len(emitted)
        if cache_path is not None:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        (log.with_suffix(".keys.json")).write_text(
            json.dumps({str(i + 1): k for i, k in enumerate(emitted)}, indent=2),
            encoding="utf-8")
    statuses = {k: cache[k]["status"] for c in cases for k in c["_keys"]}
    witnesses = {k: cache[k]["witness"] for c in cases for k in c["_keys"]}
    return dict(statuses=statuses, witnesses=witnesses, n_queries=len(statuses),
                n_new=n_new, n_cached=len(statuses) - n_new)
