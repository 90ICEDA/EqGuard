#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
cd "${EQGUARD_ROOT}"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.ys" -l "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.secs"
echo "[rs232t1000__injalpha_d1_s42__keepbnd__ys_abc] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.rc") secs=$((t1-t0))"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/out/rs232t1000/rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/cec_rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/cec_rs232t1000__injalpha_d1_s42__keepbnd__ys_abc.txt" 2>&1
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.ys" -l "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.secs"
echo "[rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.rc") secs=$((t1-t0))"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/out/rs232t1000/rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/cec_rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.log" > "${EQGUARD_ROOT}/generate_trans/keepab_s1_fraig/logs/cec_rs232t1000__ctlmatcha_d1_s42__keepbnd__ys_abc.txt" 2>&1
