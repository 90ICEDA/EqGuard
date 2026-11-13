"""Separate raw-byte and normalized-text hashes for the 348 legacy ledger rows."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"
LOG = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4/logs"


def norm_sha(p: Path) -> str:
    return hashlib.sha256(p.read_text(encoding="utf-8", errors="replace")
                          .encode()).hexdigest()


def main() -> int:
    d = pd.read_csv(TAB5 / "r5_legacy_ledger_audit.csv", encoding="utf-8-sig")
    cache = {}
    rows = []
    for _, r in d.iterrows():
        design = str(r.design)
        run = str(r.run_id)
        p = LOG / run / design / "batch.sat.log"
        if not p.exists():
            hits = list((LOG / run / design).glob("batch*.log")) if (LOG / run / design).exists() else []
            p = hits[0] if hits else None
        key = str(p)
        if key not in cache:
            if p and p.exists():
                raw = hashlib.sha256(p.read_bytes()).hexdigest()
                norm = norm_sha(p)
            else:
                raw = norm = ""
            cache[key] = (raw, norm)
        raw, norm = cache[key]
        rec = str(r.recorded_batch_sha)
        if not p:
            cls = "batch_log_missing"
        elif raw == rec:
            cls = "raw_match"
        elif norm == rec:
            cls = "raw_mismatch_text_match"
        else:
            cls = "raw_mismatch_text_mismatch"
        rows.append(dict(query_key=r.query_key, design=design, run_id=run,
                         recorded_batch_sha=rec, raw_sha256=raw,
                         normalized_text_sha256=norm, batch_log=str(p) if p else "",
                         classification=cls))
    out = pd.DataFrame(rows)
    out.to_csv(TAB6 / "r6_legacy_hash_audit.csv", index=False, encoding="utf-8-sig")
    info = dict(rows=len(out), counts=out.classification.value_counts().to_dict(),
                raw_mismatch=int((out.raw_sha256 != out.recorded_batch_sha).sum()),
                text_match=int((out.normalized_text_sha256 ==
                                out.recorded_batch_sha).sum()),
                note=("newline-only differences are classified separately; "
                      "no file is treated as overwritten solely from a raw hash"))
    (TAB6 / "r6_legacy_hash_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())