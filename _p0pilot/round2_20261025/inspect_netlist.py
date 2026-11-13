"""Find what makes yosys `proc` fail with Object `\\0' not found."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import re
from pathlib import Path

P = Path(_eqguard_path('generate_trans/folds/hosts_bt31/trans/s15850t100__injalpha_d1_s42__ys_id.v'))


def main() -> int:
    t = P.read_text(encoding="utf-8", errors="replace")
    lines = t.splitlines()
    print("lines", len(lines), "bytes", len(t))
    print("contains backslash-zero:", "\\0" in t)
    print("contains '\\0 ':", "\\0 " in t)
    # escaped identifiers
    ids = re.findall(r"\\[^\s;,()]+", t)
    from collections import Counter
    c = Counter(ids)
    weird = [(k, v) for k, v in c.items() if not re.fullmatch(r"\\[A-Za-z_][\w.$\[\]]*", k)]
    print("escaped ids", len(c), "weird", len(weird))
    for k, v in weird[:20]:
        print(repr(k), v)
    # lines that mention 0 as an instance/wire token
    hits = [(i + 1, ln) for i, ln in enumerate(lines) if re.search(r"(^|\s)0(\s|$)", ln)]
    print("lines with bare 0 token", len(hits))
    for i, ln in hits[:10]:
        print(i, ln[:200])
    print("\nfirst 20 lines:")
    for i, ln in enumerate(lines[:20]):
        print(i + 1, ln[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
