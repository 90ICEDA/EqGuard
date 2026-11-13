"""Round-5 runner: unique execution_id, batch + per-query scripts/logs/hashes.

Reuses the round-4 yosys script builder; every run writes under exec/<execution_id>/.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "_p0pilot/round4_20261025"))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r4_runner import (build_script, digest, parse_blocks, split_blocks,
                       text_sha, CELLMAP, _WITNESS)  # noqa: E402

R5_SCRIPT = "r5.1"


def query_key(design: Path, cut: list[str], cut_bits: list[int], target: str,
              pattern: str, prove: int, timeout: int, seq: int = 1) -> str:
    payload = json.dumps(dict(design=digest(design), cellmap=digest(CELLMAP),
                              script=R5_SCRIPT, cut=cut, cut_bits=cut_bits,
                              target=target, pattern=pattern, prove=prove,
                              timeout=timeout, seq=seq), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def run_batch(v: Path, top: str, cases: list[dict], execution_id: str,
              out_root: Path, timeout: int = 5, force: bool = False) -> dict:
    cache_path = out_root / "cache" / f"{v.stem}.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    retryable = {"timeout", "error", "no_result"}
    emit, hits, retries = [], 0, 0
    for c in cases:
        ent = cache.get(c["query_key"])
        if ent and not force and ent.get("status") not in retryable:
            hits += 1
            continue
        if ent and ent.get("status") in retryable:
            retries += 1
        emit.append(c)
    exec_dir = out_root / "exec" / execution_id
    batch_dir = exec_dir / "batch"
    batch_dir.mkdir(parents=True, exist_ok=True)
    if not emit:
        return dict(statuses={c["query_key"]: cache[c["query_key"]]["status"]
                              for c in cases}, hits=hits, new=0, retries=retries,
                    timeouts=0, errors=0, execution_id=execution_id,
                    batch_log="", batch_script="", emitted=[])
    ports = cases[0].get("_ports", set())
    dump_dir = exec_dir / "models"
    dump_dir.mkdir(parents=True, exist_ok=True)
    batch_script, emitted = build_script(v, top, emit, timeout, ports, dump_dir)
    batch_ys = batch_dir / "batch.ys"
    batch_log = batch_dir / "batch.log"
    batch_ys.write_text(batch_script, encoding="utf-8")
    t0 = time.perf_counter()
    out = P0.run_yosys(batch_script, batch_log, timeout=1800)
    status, _ = parse_blocks(out)
    blocks = split_blocks(out)
    return _write_queries(v, top, emitted, status, blocks, execution_id, exec_dir,
                          out_root, text_sha(batch_script), text_sha(out), cache,
                          cache_path, batch_dir, batch_log, batch_ys, ports,
                          timeout, hits, retries, t0, cases)


def _write_queries(v, top, emitted, status, blocks, execution_id, exec_dir,
                   out_root, batch_sha, batch_log_sha, cache, cache_path,
                   batch_dir, batch_log, batch_ys, ports, timeout,
                   hits, retries, t0, cases):
    retryable = {"timeout", "error", "no_result"}
    n_to = n_err = 0
    for qid, c in enumerate(emitted, 1):
        key = c["query_key"]
        st = status.get(qid, "no_result")
        n_to += int(st == "timeout")
        n_err += int(st in ("error", "no_result"))
        qdir = exec_dir / "queries" / key
        qdir.mkdir(parents=True, exist_ok=True)
        one_script, _ = build_script(v, top, [dict(c)], timeout, ports,
                                     qdir / "models")
        (qdir / "query.ys").write_text(one_script, encoding="utf-8")
        qlog = qdir / "query.log"
        header = (f"# execution_id={execution_id}\n# query_key={key}\n"
                  f"# design={v.name}\n# cut={';'.join(c['cut'])}\n"
                  f"# cut_bits={','.join(str(b) for b in c.get('cut_bits', []))}\n"
                  f"# target={c['target']}\n# pattern={c['pattern']}\n"
                  f"# prove={c['prove']}\n# seq=1\n# timeout={timeout}\n"
                  f"# source_sha={digest(v)}\n# cellmap_sha={digest(CELLMAP)}\n")
        qlog.write_text(header + "\n".join(blocks.get(qid, [])), encoding="utf-8")
        wrows = []
        for line in blocks.get(qid, []):
            m = _WITNESS.match(line)
            if m:
                wrows.append(dict(step=m.group(1), signal=m.group(2).lstrip("\\"),
                                  dec=int(m.group(3)), bin=m.group(5)))
        model = exec_dir / "models" / f"{key}.json"
        meta = dict(query_key=key, execution_id=execution_id, design=v.name,
                    cut=c["cut"], cut_bits=c.get("cut_bits", []),
                    target=c["target"], pattern=c["pattern"], prove=c["prove"],
                    seq=1, timeout=timeout, status=st,
                    source_sha=digest(v), cellmap_sha=digest(CELLMAP),
                    batch_script_sha=batch_sha, batch_log_sha=batch_log_sha,
                    query_script_sha=text_sha(one_script),
                    query_log_sha=text_sha(qlog.read_text(encoding="utf-8")),
                    model_json=str(model.relative_to(exec_dir)) if model.exists() else "",
                    rows=wrows)
        (qdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
        cache[key] = dict(status=st, execution_id=execution_id,
                          query_dir=str(qdir.relative_to(out_root)),
                          batch_log=str(batch_log.relative_to(out_root)),
                          batch_script=str(batch_ys.relative_to(out_root)),
                          batch_script_sha=batch_sha, batch_log_sha=batch_log_sha,
                          query_script_sha=meta["query_script_sha"],
                          query_log_sha=meta["query_log_sha"],
                          retryable=st in retryable,
                          ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    (batch_dir / "keys.json").write_text(json.dumps(
        {str(i + 1): c["query_key"] for i, c in enumerate(emitted)}, indent=2),
        encoding="utf-8")
    (batch_dir / "meta.json").write_text(json.dumps(dict(
        execution_id=execution_id, design=v.name, design_sha=digest(v),
        cellmap_sha=digest(CELLMAP), script_sha=batch_sha, log_sha=batch_log_sha,
        n_queries=len(emitted), timeout=timeout, seq=1,
        query_keys=[c["query_key"] for c in emitted]), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return dict(statuses={c["query_key"]: cache[c["query_key"]]["status"]
                          for c in cases}, hits=hits, new=len(emitted),
                retries=retries, timeouts=n_to, errors=n_err,
                execution_id=execution_id,
                batch_log=str(batch_log.relative_to(out_root)),
                batch_script=str(batch_ys.relative_to(out_root)),
                emitted=[c["query_key"] for c in emitted],
                wall_s=round(time.perf_counter() - t0, 2))
