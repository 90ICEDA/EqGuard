#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# yosys 生成等价网表的可行性冒烟：格式 + CEC
R="${EQGUARD_ROOT}"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
SRC=$R/generate_trans/hosts/rs232t1000/base/rs232t1000_clean.v
MOD=$(grep -m1 '^module' "$SRC" | awk '{print $2}')
OUT=$R/generate_trans/ys_smoke
mkdir -p "$OUT"
echo "MOD=$MOD"

echo "=== local_techmap.v head ==="
head -25 "$V/local_techmap.v"
echo "=== yosys_sdff_unmap.v head ==="
head -15 "$V/yosys_sdff_unmap.v"

run_variant () {
  name=$1; passes=$2
  cat > /tmp/$name.ys <<EOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv $SRC
hierarchy -top $MOD
proc
opt -full
$passes
opt_clean
write_verilog -noattr $OUT/${MOD}__${name}.v
EOF
  yosys -q -s /tmp/$name.ys -l $OUT/${name}.log > /dev/null 2>&1
  rc=$?
  f=$OUT/${MOD}__${name}.v
  echo "--- [$name] rc=$rc size=$(wc -c < $f 2>/dev/null) ---"
  grep -c 'assign' "$f" 2>/dev/null | sed 's/^/  assigns=/'
  grep -cE '^\s+[A-Za-z_\\][A-Za-z0-9_\\]*\s' "$f" 2>/dev/null | sed 's/^/  instlike=/'
  head -12 "$f" 2>/dev/null | tail -8
}

run_variant opt "opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX"
run_variant aig "techmap
opt -full
aigmap"

echo "=== CEC（golden=clean vs candidate=variant）==="
cd $R
for n in opt aig; do
  python3 generate_trans/cec/direct_cec.py --golden "$SRC" --candidate "$OUT/${MOD}__${n}.v" \
     --vali-dir "$V" --timeout 600 --log /tmp/cec_$n.log > /tmp/cec_$n.txt 2>&1
  echo "[$n] $(grep -a 'CEC' /tmp/cec_$n.txt | tail -1)"
done
