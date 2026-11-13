#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# 验证：yosys 生成的等价网表 → 映射回设计库单元 → 仍是合法门级网表 + CEC 仍通过
R="${EQGUARD_ROOT}"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
SRC=$R/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v
MOD=rs232t1000__injalpha_d1_s42
OUT=$R/generate_trans/ys_tolib_test
mkdir -p "$OUT"

for spec in "opt:" "abc:abc -g AND,OR,XOR,XNOR,MUX" "aig:abc -g AND,INV"; do
  name=${spec%%:*}; passes=${spec#*:}
  NEW=${MOD}__ys${name}
  {
    echo "read_verilog -sv $V/verilog_lib.v"
    echo "read_verilog -sv $SRC"
    echo "hierarchy -top $MOD"
    echo "proc"
    echo "opt -full"
    echo "techmap"
    echo "opt -full"
    [ -n "$passes" ] && echo "$passes"
    echo "techmap -map $R/phase2/ys/to_lib_techmap.v"
    echo "opt_clean"
    echo "rename -top $NEW"
    echo "write_verilog -noattr $OUT/$NEW.v"
  } > /tmp/tolib_$name.ys
  yosys -q -s /tmp/tolib_$name.ys -l $OUT/$name.log > /dev/null 2>&1
  rc=$?
  f=$OUT/$NEW.v
  echo "--- [$name] yosys rc=$rc bytes=$(wc -c < $f 2>/dev/null) ---"
  echo -n "  库单元统计: "
  grep -oE '^  [A-Za-z_\\][A-Za-z0-9_\\]* ' "$f" 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -rn | head -8 | tr '\n' ' '
  echo
  echo -n "  assign 行数: "; grep -c 'assign' "$f" 2>/dev/null
  echo -n "  还有 yosys 内部单元吗: "; grep -coE '\$_' "$f" 2>/dev/null
done

echo "=== CEC（golden=源网表 vs candidate=映射回来的变体）==="
cd $R
for name in opt abc aig; do
  NEW=${MOD}__ys${name}
  python3 generate_trans/cec/direct_cec.py --golden "$SRC" --candidate "$OUT/$NEW.v" \
     --vali-dir "$V" --timeout 600 --log /tmp/tolib_cec_$name.log > /tmp/tolib_cec_$name.txt 2>&1
  echo "[$name] $(grep -a 'CEC' /tmp/tolib_cec_$name.txt | tail -1)"
done
