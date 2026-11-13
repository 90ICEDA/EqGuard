#!/usr/bin/env bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# ---------------------------------------------------------------------------
# smoke_sby.sh — 用 sby + config_state_boundary.sby 对一个视图做 state-boundary CEC
#                （验证 vali 侧脚本路径，与 matrix_cec.py 的 yosys 直接调用互为交叉验证）
#
# 用法：bash smoke_sby.sh [view_name] [orig_stem] [workdir]
#   bash smoke_sby.sh rs232t1000__decomp_d1_s42 rs232t1000 /tmp/cbc_smoke
# ---------------------------------------------------------------------------
set -u

VALI="${VALI:-${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}}"
GEN="${GEN:-${EQGUARD_ROOT}/generate_trans}"
VIEW="${1:-rs232t1000__decomp_d1_s42}"
GOLD="${2:-rs232t1000}"
W="${3:-/tmp/cbc_smoke}"

mkdir -p "$W"
cp "$GEN/orig/$GOLD.v" "$W/golden.v" || exit 1
cp "$GEN/matrix/verilog/$VIEW.v" "$W/candidate.v" || exit 1
cp "$VALI/verilog_lib.v" "$VALI/sdff_formal_map.v" "$VALI/bitwuzla_wrap.sh" "$W/"

GOLD_MOD="$(grep -m1 -E '^[[:space:]]*module' "$W/golden.v" | awk '{print $2}' | tr -d '();')"
CAND_MOD="$(grep -m1 -E '^[[:space:]]*module' "$W/candidate.v" | awk '{print $2}' | tr -d '();')"
sed -e "s/GOLDEN_REAL_NAME/$GOLD_MOD/" -e "s/CANDIDATE_REAL_NAME/$CAND_MOD/" \
    "$VALI/config_state_boundary.sby" > "$W/run.sby"

cd "$W" || exit 1
timeout "${TIMEOUT:-600}" sby -f run.sby -d sby_out > sby_stdout.txt 2>&1
rc=$?
echo "golden=$GOLD_MOD  candidate=$CAND_MOD  workdir=$W"
echo "sby_rc=$rc"
grep -m1 -E 'Equivalence' sby_out/logfile.txt 2>/dev/null
grep -m1 -E 'equiv cells' sby_out/logfile.txt 2>/dev/null
grep -m1 -E 'unproven' sby_out/logfile.txt 2>/dev/null
