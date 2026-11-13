"""Round-4 SAT runner: stable query identity, per-query logs, full witnesses.

Identity is the same key as round 3 (source digest, cell-map digest, script
version, cut, target, pattern, prove, seq, timeout). Each execution additionally
stores run_id, batch/script/log hashes, witness path and model/CNF paths.
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
import time
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

CELLMAP = ROOT / "phase2/ys/sat_cells_map.v"
R3_SCRIPT = "r3.1"
_DIGEST = {}


def digest(path: Path) -> str:
    key = str(path)
    if key not in _DIGEST:
        _DIGEST[key] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""
    return _DIGEST[key]


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def query_key(design: Path, cut: list[str], target: str, pattern: str,
              prove: int, timeout: int, seq: int = 1) -> str:
    """Same payload as round 3, with pattern as a fixed-width string."""
    payload = json.dumps(dict(design=digest(design), cellmap=digest(CELLMAP),
                              script=R3_SCRIPT, cut=cut, target=target,
                              pattern=[int(c) for c in pattern], prove=prove,
                              timeout=timeout, seq=seq), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def build_script(v: Path, top: str, cases: list[dict], timeout: int,
                 ports: set[str], dump_dir: Path, cnf_dir: Path | None = None,
                 cnf_keys: set[str] | None = None) -> tuple[str, list[dict]]:
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
        c["_refs"] = [ref(nm) for nm in c["cut"]]
        c["_tref"] = ref(c["target"])
    lines += rlines
    if renamed:
        lines.append("setattr -set keep 1 " + " ".join(f"w:{x}" for x in renamed.values()))
    lines += ["techmap -autoproc -map phase2/ys/sat_cells_map.v", "opt -fast"]
    emitted = []
    for i, c in enumerate(cases, 1):
        shows = " ".join(f"-show {r}" for r in c["_refs"]) + f" -show {c['_tref']}"
        sets = " ".join(f"-set {r} {b}" for r, b in zip(c["_refs"], c["pattern"]))
        dump = f" -dump_json {P0.wsl(dump_dir / (c['query_key'] + '.json'))}"
        cnf = ""
        if cnf_dir is not None and cnf_keys and c["query_key"] in cnf_keys:
            cnf_dir.mkdir(parents=True, exist_ok=True)
            cnf = f" -dump_cnf {P0.wsl(cnf_dir / (c['query_key'] + '.cnf'))}"
        lines += [f"log QRY{i:05d}",
                  f"sat -seq 1 {sets} -prove {c['_tref']} {c['prove']} "
                  f"-timeout {timeout} {shows}{dump}{cnf}"]
        emitted.append(c)
    return "\n".join(lines) + "\n", emitted


_WITNESS = re.compile(r"^\s*(init|\d+)\s+(\\\S+)\s+(-?\d+)\s+(\S+)\s+([01xz]+)\s*$")


def parse_blocks(out: str) -> tuple[dict[int, str], dict[int, list[str]]]:
    blocks, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^QRY(\d{5})$", line.strip())
        if m:
            cur = int(m.group(1))
            blocks[cur] = []
            continue
        if cur is not None:
            blocks[cur].append(line)
    status, rows = {}, {}
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
        w = []
        for line in lines:
            m = _WITNESS.match(line)
            if m:
                w.append(f"{m.group(1)}:{m.group(2).lstrip(chr(92))}={m.group(5)}")
        rows[qid] = w
    return status, rows


def split_blocks(out: str) -> dict[int, list[str]]:
    blocks, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^QRY(\d{5})$", line.strip())
        if m:
            cur = int(m.group(1))
            blocks[cur] = [line]
            continue
        if cur is not None:
            blocks[cur].append(line)
    return blocks


def run_batch(v: Path, top: str, cases: list[dict], run_id: str, out_root: Path,
              force: bool = False, timeout: int = 5,
              cnf_keys: set[str] | None = None) -> dict:
    cache_path = out_root / "cache_v4" / f"{v.stem}.json"
    cache = (json.loads(cache_path.read_text(encoding="utf-8"))
             if cache_path.exists() else {})
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    retryable = {"timeout", "error", "no_result"}
    hits, emit, retries = 0, [], 0
    for c in cases:
        key = c["query_key"]
        ent = cache.get(key)
        if ent and not force and ent.get("status") not in retryable:
            hits += 1
            continue
        if ent and ent.get("status") in retryable:
            retries += 1
        emit.append(c)
    if not emit:
        return dict(statuses={c["query_key"]: cache[c["query_key"]]["status"]
                              for c in cases},
                    hits=hits, new=0, retries=retries, timeouts=0, errors=0,
                    log="", script="", emitted=[])

    dump_dir = out_root / "witness" / run_id / v.stem
    dump_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_root / "logs" / run_id / v.stem
    log_dir.mkdir(parents=True, exist_ok=True)
    # ports must be supplied by the caller through cases[0]["_ports"]
    ports = cases[0].get("_ports", set())
    cnf_dir = out_root / "cnf" / run_id / v.stem
    script, emitted = build_script(v, top, emit, timeout, ports, dump_dir,
                                   cnf_dir, cnf_keys)
    script_path = log_dir / "batch.sat.ys"
    script_path.write_text(script, encoding="utf-8")
    log_path = log_dir / "batch.sat.log"
    t0 = time.perf_counter()
    out = P0.run_yosys(script, log_path, timeout=1800)
    status, _ = parse_blocks(out)
    blocks = split_blocks(out)
    log_sha = text_sha(out)
    n_to = n_err = 0
    for qid, c in enumerate(emitted, 1):
        key = c["query_key"]
        st = status.get(qid, "no_result")
        n_to += int(st == "timeout")
        n_err += int(st in ("error", "no_result"))
        qlog = log_dir / f"{key}.sat.log"
        header = (f"# run_id={run_id}\n# design={v.name}\n# query_key={key}\n"
                  f"# cut={';'.join(c['cut'])}\n# target={c['target']}\n"
                  f"# pattern={c['pattern']}\n# prove={c['prove']}\n"
                  f"# timeout={timeout}\n# seq=1\n"
                  f"# source_sha={digest(v)}\n# cellmap_sha={digest(CELLMAP)}\n")
        qlog.write_text(header + "\n".join(blocks.get(qid, [])), encoding="utf-8")
        model = dump_dir / f"{key}.json"
        wrows = []
        for line in blocks.get(qid, []):
            m = _WITNESS.match(line)
            if m:
                wrows.append(dict(step=m.group(1), signal=m.group(2).lstrip("\\"),
                                  dec=int(m.group(3)), bin=m.group(5)))
        wit = dump_dir / f"{key}.witness.json"
        wit.write_text(json.dumps(dict(
            query_key=key, run_id=run_id, design=v.name, cut=c["cut"],
            target=c["target"], pattern=c["pattern"], prove=c["prove"],
            seq=1, timeout=timeout, status=st,
            source_sha=digest(v), cellmap_sha=digest(CELLMAP),
            script_sha=text_sha(script), log_sha=log_sha,
            model_json=str(model.relative_to(out_root)) if model.exists() else "",
            rows=wrows), ensure_ascii=False, indent=2), encoding="utf-8")
        cache[key] = dict(status=st, run_id=run_id,
                          log=str(qlog.relative_to(out_root)),
                          witness=str(wit.relative_to(out_root)),
                          model=str(model.relative_to(out_root)) if model.exists() else "",
                          log_sha=log_sha, script_sha=text_sha(script),
                          retryable=st in retryable,
                          ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    (log_dir / "batch.sat.keys.json").write_text(json.dumps(
        {str(i + 1): c["query_key"] for i, c in enumerate(emitted)}, indent=2),
        encoding="utf-8")
    return dict(statuses={c["query_key"]: cache[c["query_key"]]["status"]
                          for c in cases},
                hits=hits, new=len(emitted), retries=retries,
                timeouts=n_to, errors=n_err, log=str(log_path.relative_to(out_root)),
                script=str(script_path.relative_to(out_root)),
                emitted=[c["query_key"] for c in emitted],
                wall_s=round(time.perf_counter() - t0, 2))

