#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "${EQGUARD_ROOT}"
bash phase2/ys/_cec_tolib.sh > /dev/null 2>&1
echo "=== 转换回库单元之后的 CEC（golden = B 型源网表）==="
echo "PASS : $(grep -c PASS /tmp/cec_tolib.csv)"
echo "FAIL : $(grep -c FAIL /tmp/cec_tolib.csv)"
echo "TOTAL: $(tail -n +2 /tmp/cec_tolib.csv | wc -l)"
echo "--- FAIL 的样例 ---"
grep FAIL /tmp/cec_tolib.csv | head -5
echo "--- 按配方统计 ---"
tail -n +2 /tmp/cec_tolib.csv | awk -F, '{print $2}' | sort | uniq -c
