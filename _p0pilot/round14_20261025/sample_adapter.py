"""Minimal read-only adapter for the 11-relation sample contract."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

ROOT = Path(_eqguard_path(''))
MANIFEST = (ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/"
            "sat_pair_round14/pair_sample_manifest.json")


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_records(role: str | None = None) -> list[dict]:
    rows = load_manifest()
    return [r for r in rows if role is None or r["role"] == role]


def record_nodes(record: dict) -> list[int]:
    return [int(n) for n in record["valid_graph_landing"]]


def feature_pair(record: dict):
    return record["feature_18d"]["source"], record["feature_18d"]["partner"]


def main() -> int:
    rows = load_manifest()
    print(dict(records=len(rows), train=len(iter_records("train")),
               val=len(iter_records("val")),
               units=sorted({r["sample_unit"] for r in rows}),
               training_allowed=sum(bool(r["training_pair_allowed"]) for r in rows),
               nodes=sum(len(record_nodes(r)) for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())