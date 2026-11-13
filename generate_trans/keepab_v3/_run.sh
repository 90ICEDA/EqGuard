#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
cd "${EQGUARD_ROOT}"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.ys" -l "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.secs"
echo "[s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.rc") secs=$((t1-t0))"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_a4/s15850t100/s15850t100__a4trojan_s0_d1_s42.v" --candidate "${EQGUARD_ROOT}/generate_trans/keepab_v3/out/s15850t100/s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/cec_s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/cec_s15850t100__a4trojan_s0_d1_s42__keepnone__ys_abc.txt" 2>&1
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.ys" -l "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.secs"
echo "[s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.rc") secs=$((t1-t0))"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_a4/s15850t100/s15850t100__a4trojan_s0_d1_s42.v" --candidate "${EQGUARD_ROOT}/generate_trans/keepab_v3/out/s15850t100/s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/cec_s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/cec_s15850t100__a4trojan_s0_d1_s42__keepcur__ys_abc.txt" 2>&1
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.ys" -l "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.secs"
echo "[s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.rc") secs=$((t1-t0))"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_a4/s15850t100/s15850t100__a4trojan_s0_d1_s42.v" --candidate "${EQGUARD_ROOT}/generate_trans/keepab_v3/out/s15850t100/s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/cec_s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_v3/logs/cec_s15850t100__a4trojan_s0_d1_s42__keepfull__ys_abc.txt" 2>&1
