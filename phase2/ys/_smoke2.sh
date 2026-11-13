#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# yosys 生成等价网表 v2：加 rename（CEC 要求 golden/candidate 模块名不同）
R="${EQGUARD_ROOT}"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
SRC=$R/generate_trans/hosts/rs232t1000/base/rs232t1000_clean.v
MOD=$(grep -m1 '^module' "$SRC" | awk '{print $2}')
OUT=$R/generate_trans/ys_smoke
mkdir -p "$OUT"
echo "MOD=$MOD"

run_variant () {
  name=$1; passes=$2
  NEW=${MOD}__ys_${name}
  cat > /tmp/$name.ys <<EOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv $SRC
hierarchy -top $MOD
proc
opt -full
$passes
opt_clean
rename $MOD $NEW
write_verilog -noattr $OUT/${NEW}.v
EOF
  yosys -q -s /tmp/$name.ys -l $OUT/${name}.log > /dev/null 2>&1
  rc=$?
  f=$OUT/${NEW}.v
  echo "--- [$name] rc=$rc bytes=$(wc -c < $f 2>/dev/null) always=$(grep -c 'always' $f) ---"
  grep -oE '^  [A-Za-z_\\][A-Za-z0-9_\\]* ' "$f" 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -rn | head -6 | sed 's/^/    cell: /'
}

run_variant opt "flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX"
run_variant aig "techmap
opt -full
aigmap"
run_variant lite "opt_expr
opt_merge"

echo "=== CEC ==="
cd $R
for n in opt aig lite; do
  python3 generate_trans/cec/direct_cec.py --golden "$SRC" --candidate "$OUT/${MOD}__ys_${n}.v" \
     --vali-dir "$V" --timeout 900 --log /tmp/cec_$n.log > /tmp/cec_$n.txt 2>&1
  echo "[$n] $(grep -a 'CEC' /tmp/cec_$n.txt | tail -1)"
done
