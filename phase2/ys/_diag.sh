#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
R="${EQGUARD_ROOT}"
OUT=$R/generate_trans/ys_smoke
echo "=== variant modules ==="
grep -n '^module' "$OUT/rs232t1000_clean__opt.v"
echo "=== variant internal cells 样例 ==="
grep -oE '\$_[A-Z]+_' "$OUT/rs232t1000_clean__opt.v" | sort | uniq -c | head
echo "=== variant always blocks ==="
grep -c 'always' "$OUT/rs232t1000_clean__opt.v"
echo "=== cec log tail (opt) ==="
tail -25 /tmp/cec_opt.log
echo "=== cec stdout (opt) ==="
tail -12 /tmp/cec_opt.txt
