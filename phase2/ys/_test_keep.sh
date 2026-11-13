#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# 验证 keep 属性能否让木马网名扛过 yosys 重综合（abc 配方）
R="${EQGUARD_ROOT}"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
SRC=$R/generate_trans/ysk_test/rs232t1000/rs232t1000__injalpha_d1_s42__keep.v
MOD=rs232t1000__injalpha_d1_s42
NEW=${MOD}__keepabc
OUT=$R/generate_trans/ysk_test
mkdir -p "$OUT"

cat > /tmp/keep.ys <<EOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv $SRC
hierarchy -top $MOD
proc
opt -full
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
rename -top $NEW
write_verilog -noattr $OUT/$NEW.v
EOF
yosys -q -s /tmp/keep.ys -l $OUT/keep.log > /dev/null 2>&1
echo "yosys rc=$?"
Y=$OUT/$NEW.v
echo "=== yosys 输出里还有没有 TrojanA 相关名字 ==="
grep -oc 'TrojanA' "$Y" 2>/dev/null
grep -oE '[\\A-Za-z0-9_.]*TrojanA[A-Za-z0-9_.]*' "$Y" 2>/dev/null | sort -u | head -8
echo "=== 输出规模 ==="
echo -n "  assign 数: "; grep -c 'assign' "$Y"
echo -n "  wire 声明数: "; grep -cE '^\s+wire' "$Y"

echo "=== CEC（golden = 源网表 vs keep 变体）==="
cd $R
python3 generate_trans/cec/direct_cec.py --golden "$R/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v" \
    --candidate "$Y" --vali-dir "$V" --timeout 600 --log /tmp/keep_cec.log > /tmp/keep_cec.txt 2>&1
echo "[keep+abc] $(grep -a 'CEC' /tmp/keep_cec.txt | tail -1)"
