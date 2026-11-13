#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
cd "${EQGUARD_ROOT}"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepnone__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepnone__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepnone__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepnone__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepnone__ys_id.secs"
echo "[s38584t100__a4trojan_s0_d1_s42__keepnone__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepnone__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepcur__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepcur__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepcur__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepcur__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepcur__ys_id.secs"
echo "[s38584t100__a4trojan_s0_d1_s42__keepcur__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s0_d1_s42__keepcur__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepnone__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepnone__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepnone__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepnone__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepnone__ys_id.secs"
echo "[s38584t100__a4ctldead_s0_d1_s42__keepnone__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepnone__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepcur__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepcur__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepcur__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepcur__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepcur__ys_id.secs"
echo "[s38584t100__a4ctldead_s0_d1_s42__keepcur__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s0_d1_s42__keepcur__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepnone__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepnone__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepnone__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepnone__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepnone__ys_id.secs"
echo "[s38584t100__a4ctlequiv_s0_d1_s42__keepnone__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepnone__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id.secs"
echo "[s38584t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepnone__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepnone__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepnone__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepnone__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepnone__ys_id.secs"
echo "[s38584t100__a4trojan_s1_d1_s42__keepnone__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepnone__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepcur__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepcur__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepcur__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepcur__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepcur__ys_id.secs"
echo "[s38584t100__a4trojan_s1_d1_s42__keepcur__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4trojan_s1_d1_s42__keepcur__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepnone__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepnone__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepnone__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepnone__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepnone__ys_id.secs"
echo "[s38584t100__a4ctldead_s1_d1_s42__keepnone__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepnone__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepcur__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepcur__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepcur__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepcur__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepcur__ys_id.secs"
echo "[s38584t100__a4ctldead_s1_d1_s42__keepcur__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctldead_s1_d1_s42__keepcur__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepnone__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepnone__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepnone__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepnone__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepnone__ys_id.secs"
echo "[s38584t100__a4ctlequiv_s1_d1_s42__keepnone__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepnone__ys_id.rc") secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepcur__ys_id.ys" -l "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepcur__ys_id.log" > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepcur__ys_id.stdout" 2>&1
echo $? > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepcur__ys_id.rc"
t1=$(date +%s); echo $((t1-t0)) > "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepcur__ys_id.secs"
echo "[s38584t100__a4ctlequiv_s1_d1_s42__keepcur__ys_id] yosys_rc=$(cat "${EQGUARD_ROOT}/generate_trans/a4_s38584t100/logs/s38584t100__a4ctlequiv_s1_d1_s42__keepcur__ys_id.rc") secs=$((t1-t0))"
