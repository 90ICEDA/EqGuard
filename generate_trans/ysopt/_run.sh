#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
cd "${EQGUARD_ROOT}"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/ysopt/logs/s38584t100__injdelta_d1_s42__keepnone__ys_opt.ys" -l "${EQGUARD_ROOT}/generate_trans/ysopt/logs/s38584t100__injdelta_d1_s42__keepnone__ys_opt.log" > "${EQGUARD_ROOT}/generate_trans/ysopt/logs/s38584t100__injdelta_d1_s42__keepnone__ys_opt.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/ysopt/logs/s38584t100__injdelta_d1_s42__keepnone__ys_opt.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/ysopt/logs/s38584t100__injdelta_d1_s42__keepnone__ys_opt.secs"
echo "[s38584t100__injdelta_d1_s42__keepnone__ys_opt] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/ysopt/logs/s38584t100__injdelta_d1_s42__keepnone__ys_opt.rc") secs=$((t1-t0))"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2/s38584t100/s38584t100__injdelta_d1_s42.v" --candidate "${EQGUARD_ROOT}/generate_trans/ysopt/out/s38584t100/s38584t100__injdelta_d1_s42__keepnone__ys_opt.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log "${EQGUARD_ROOT}/generate_trans/ysopt/logs/cec_s38584t100__injdelta_d1_s42__keepnone__ys_opt.log" > "${EQGUARD_ROOT}/generate_trans/ysopt/logs/cec_s38584t100__injdelta_d1_s42__keepnone__ys_opt.txt" 2>&1
