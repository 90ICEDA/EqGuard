#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "${EQGUARD_ROOT}"
VALI=${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}
for f in generate_trans/yslibsmoke_rtabc/rs232t1000/*.v generate_trans/yslibsmoke_aig/rs232t1000/*.v; do
  b=$(basename "$f" .v)
  stem=${b%%__ys_*}
  out=$(python3 generate_trans/cec/direct_cec.py --golden generate_trans/hosts_bt2/rs232t1000/$stem.v --candidate "$f" --vali-dir $VALI --timeout 900 --log /tmp/cec_smoke.log 2>&1 | grep -E '^\[CEC\]' | tail -1)
  echo "$b : $out"
done