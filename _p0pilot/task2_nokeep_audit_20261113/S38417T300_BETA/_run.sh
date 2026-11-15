#!/bin/bash
set +e
cd "$(dirname "${BASH_SOURCE[0]}")/../../.." || exit 1
t0=$(date +%s)
timeout 900 yosys -q -s ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_abc.ys -l ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_abc.log > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_abc.stdout 2>&1
echo $? > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_abc.rc
t1=$(date +%s); echo $((t1-t0)) > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_abc.secs
echo "[s38417t300__injbeta_d1_s42__keepnone__ys_abc] yosys_rc=$(cat ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_abc.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_abc.ys -l ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_abc.log > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_abc.stdout 2>&1
echo $? > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_abc.rc
t1=$(date +%s); echo $((t1-t0)) > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_abc.secs
echo "[s38417t300__injbeta_d1_s42__keepcur__ys_abc] yosys_rc=$(cat ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_abc.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_nand.ys -l ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_nand.log > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_nand.stdout 2>&1
echo $? > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_nand.rc
t1=$(date +%s); echo $((t1-t0)) > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_nand.secs
echo "[s38417t300__injbeta_d1_s42__keepnone__ys_nand] yosys_rc=$(cat ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepnone__ys_nand.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_nand.ys -l ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_nand.log > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_nand.stdout 2>&1
echo $? > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_nand.rc
t1=$(date +%s); echo $((t1-t0)) > ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_nand.secs
echo "[s38417t300__injbeta_d1_s42__keepcur__ys_nand] yosys_rc=$(cat ./_p0pilot/task2_nokeep_audit_20261113/S38417T300_BETA/logs/s38417t300__injbeta_d1_s42__keepcur__ys_nand.rc) secs=$((t1-t0))"
