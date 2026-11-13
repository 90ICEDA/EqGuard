"""Round-6 query binding: new semantic version, reuse round-5 batch writer."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(_eqguard_path('_p0pilot/round4_20261025'))))
from r4_runner import CELLMAP, digest  # noqa: E402
from r5_runner import run_batch  # noqa: F401

R6_SCRIPT = "r6.1"


def query_key(design, cut: list[str], cut_bits: list[int], target: str,
              pattern: str, prove: int, timeout: int, seq: int = 1) -> str:
    payload = json.dumps(dict(design=digest(design), cellmap=digest(CELLMAP),
                              script=R6_SCRIPT, cut=cut, cut_bits=cut_bits,
                              target=target, pattern=pattern, prove=prove,
                              timeout=timeout, seq=seq), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
