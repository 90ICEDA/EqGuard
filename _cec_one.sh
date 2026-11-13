#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/." && pwd -P)"
cd "${EQGUARD_ROOT}"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
G=generate_trans/folds/hosts_bt3/orig/s15850t100__a4ctlequiv_s0_d1_s42.v
C=generate_trans/folds/hosts_bt3/trans/s15850t100__a4ctlequiv_s0_d1_s42__keepcur__ys_abc.v
echo "--- plain ---"
python3 generate_trans/cec/direct_cec.py --golden $G --candidate $C --vali-dir $V --timeout 300 --log /tmp/f1.log 2>&1 | tail -2
echo "--- fast ---"
python3 generate_trans/cec/direct_cec.py --golden $G --candidate $C --vali-dir $V --timeout 300 --fast --log /tmp/f2.log 2>&1 | tail -2
echo "--- unproven cells (plain) ---"
grep -i -m5 "unproven\|equiv_cell\|\$equiv" /tmp/f1.log | head -8
