#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2/s38584t100/s38584t100__injdelta_d1_s42.v" --candidate "${EQGUARD_ROOT}/generate_trans/ysopt/conv/s38584t100/s38584t100__injdelta_d1_s42__keepnone__ys_opt.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log "${EQGUARD_ROOT}/generate_trans/ysopt/logs/cecconv_s38584t100__injdelta_d1_s42__keepnone__ys_opt.log" > "${EQGUARD_ROOT}/generate_trans/ysopt/logs/cecconv_s38584t100__injdelta_d1_s42__keepnone__ys_opt.txt" 2>&1
