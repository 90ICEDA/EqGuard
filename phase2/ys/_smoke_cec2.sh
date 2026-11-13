#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "${EQGUARD_ROOT}"
VALI=${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}
F=rs232t1000__injalpha_d1_s42
for d in sm_base sm_final sm_flat sm_both; do
  f=generate_trans/$d/rs232t1000/${F}__ys_rt.v
  out=$(python3 generate_trans/cec/direct_cec.py --golden generate_trans/hosts_bt2/rs232t1000/$F.v --candidate $f --vali-dir $VALI --timeout 900 --log /tmp/cec_$d.log 2>&1 | grep -E '^\[CEC\]' | tail -1)
  echo "$d  rt : $out"
done