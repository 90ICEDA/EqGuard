#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
cd "${EQGUARD_ROOT}"
OUT="${EQGUARD_ROOT}/10.10/results/cec_ab.csv"
echo "host,view,pair,golden,candidate,proven,unproven,status" > $OUT
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts/rs232t1000/base/rs232t1000_clean.v" --candidate "${EQGUARD_ROOT}/generate_trans/hosts/rs232t1000/rs232t1000__injalpha_d1_s42.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log /tmp/cec_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_A.log > /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_A.txt 2>&1
P=$(grep -oE 'proven=[0-9]+' /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_A.txt | tail -1 | cut -d= -f2)
U=$(grep -oE 'unproven=[0-9]+' /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_A.txt | tail -1 | cut -d= -f2)
S=$(grep -aoE 'PASS|FAIL' /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_A.txt | tail -1)
echo "rs232t1000,rs232t1000__injalpha_d1_s42,clean_vs_A,rs232t1000_clean.v,rs232t1000__injalpha_d1_s42.v,${P:--},${U:--},${S:-rc?}" >> $OUT
echo "[clean_vs_A] rs232t1000/rs232t1000__injalpha_d1_s42 → ${S:-rc?}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts/rs232t1000/base/rs232t1000_clean.v" --candidate "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log /tmp/cec_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_B.log > /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_B.txt 2>&1
P=$(grep -oE 'proven=[0-9]+' /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_B.txt | tail -1 | cut -d= -f2)
U=$(grep -oE 'unproven=[0-9]+' /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_B.txt | tail -1 | cut -d= -f2)
S=$(grep -aoE 'PASS|FAIL' /tmp/o_rs232t1000_rs232t1000__injalpha_d1_s42_clean_vs_B.txt | tail -1)
echo "rs232t1000,rs232t1000__injalpha_d1_s42,clean_vs_B,rs232t1000_clean.v,rs232t1000__injalpha_d1_s42.v,${P:--},${U:--},${S:-rc?}" >> $OUT
echo "[clean_vs_B] rs232t1000/rs232t1000__injalpha_d1_s42 → ${S:-rc?}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts/s35932t200/base/s35932t200_clean.v" --candidate "${EQGUARD_ROOT}/generate_trans/hosts/s35932t200/s35932t200__injalpha_d1_s42.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log /tmp/cec_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_A.log > /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_A.txt 2>&1
P=$(grep -oE 'proven=[0-9]+' /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_A.txt | tail -1 | cut -d= -f2)
U=$(grep -oE 'unproven=[0-9]+' /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_A.txt | tail -1 | cut -d= -f2)
S=$(grep -aoE 'PASS|FAIL' /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_A.txt | tail -1)
echo "s35932t200,s35932t200__injalpha_d1_s42,clean_vs_A,s35932t200_clean.v,s35932t200__injalpha_d1_s42.v,${P:--},${U:--},${S:-rc?}" >> $OUT
echo "[clean_vs_A] s35932t200/s35932t200__injalpha_d1_s42 → ${S:-rc?}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts/s35932t200/base/s35932t200_clean.v" --candidate "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log /tmp/cec_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_B.log > /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_B.txt 2>&1
P=$(grep -oE 'proven=[0-9]+' /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_B.txt | tail -1 | cut -d= -f2)
U=$(grep -oE 'unproven=[0-9]+' /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_B.txt | tail -1 | cut -d= -f2)
S=$(grep -aoE 'PASS|FAIL' /tmp/o_s35932t200_s35932t200__injalpha_d1_s42_clean_vs_B.txt | tail -1)
echo "s35932t200,s35932t200__injalpha_d1_s42,clean_vs_B,s35932t200_clean.v,s35932t200__injalpha_d1_s42.v,${P:--},${U:--},${S:-rc?}" >> $OUT
echo "[clean_vs_B] s35932t200/s35932t200__injalpha_d1_s42 → ${S:-rc?}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts/s15850t100/base/s15850t100_clean.v" --candidate "${EQGUARD_ROOT}/generate_trans/hosts/s15850t100/s15850t100__injalpha_d1_s42.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log /tmp/cec_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_A.log > /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_A.txt 2>&1
P=$(grep -oE 'proven=[0-9]+' /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_A.txt | tail -1 | cut -d= -f2)
U=$(grep -oE 'unproven=[0-9]+' /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_A.txt | tail -1 | cut -d= -f2)
S=$(grep -aoE 'PASS|FAIL' /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_A.txt | tail -1)
echo "s15850t100,s15850t100__injalpha_d1_s42,clean_vs_A,s15850t100_clean.v,s15850t100__injalpha_d1_s42.v,${P:--},${U:--},${S:-rc?}" >> $OUT
echo "[clean_vs_A] s15850t100/s15850t100__injalpha_d1_s42 → ${S:-rc?}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts/s15850t100/base/s15850t100_clean.v" --candidate "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v" --vali-dir ${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory} --timeout 900 --log /tmp/cec_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_B.log > /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_B.txt 2>&1
P=$(grep -oE 'proven=[0-9]+' /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_B.txt | tail -1 | cut -d= -f2)
U=$(grep -oE 'unproven=[0-9]+' /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_B.txt | tail -1 | cut -d= -f2)
S=$(grep -aoE 'PASS|FAIL' /tmp/o_s15850t100_s15850t100__injalpha_d1_s42_clean_vs_B.txt | tail -1)
echo "s15850t100,s15850t100__injalpha_d1_s42,clean_vs_B,s15850t100_clean.v,s15850t100__injalpha_d1_s42.v,${P:--},${U:--},${S:-rc?}" >> $OUT
echo "[clean_vs_B] s15850t100/s15850t100__injalpha_d1_s42 → ${S:-rc?}"
