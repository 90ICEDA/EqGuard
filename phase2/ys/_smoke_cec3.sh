#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "${EQGUARD_ROOT}"
VALI=${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}
for v in rs232t1000__injalpha_d1_s42 rs232t1000__ctlmatcha_d1_s42; do
  for r in rt abc aig; do
    f=generate_trans/stamp/out/${v}__ys_${r}.v
    out=$(python3 generate_trans/cec/direct_cec.py --golden generate_trans/hosts_bt2/rs232t1000/$v.v --candidate $f --vali-dir $VALI --timeout 900 --log /tmp/cec_stamp_$r.log 2>&1 | grep -E '^\[CEC\]' | tail -1)
    echo "$v  $r : $out"
  done
done