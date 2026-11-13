#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "${EQGUARD_ROOT}"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
G=generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v
C=generate_trans/yslib_test/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v
echo "=== golden 头 3 行 ==="; head -3 "$G"
echo "=== candidate 头 3 行 ==="; head -3 "$C"
echo "=== candidate 里的 assign 数 ==="; grep -c 'assign' "$C"
echo "=== 跑 CEC ==="
python3 generate_trans/cec/direct_cec.py --golden "$G" --candidate "$C" \
    --vali-dir "$V" --timeout 600 --log /tmp/one.log > /tmp/one.txt 2>&1
echo "rc=$?"
tail -4 /tmp/one.txt
echo "=== log 里的报错 ==="
grep -aiE "error|re-definition" /tmp/one.log | head -6
