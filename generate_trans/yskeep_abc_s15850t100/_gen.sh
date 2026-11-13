#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
OUT="${EQGUARD_ROOT}/generate_trans/yskeep_abc_s15850t100"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
echo 'host,kind,stem,recipe,rc,bytes,always,cells,cec,secs' > $OUT/ys_manifest.csv
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injalpha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injalpha_d1_s42.v"
hierarchy -top s15850t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__injalpha_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injalpha_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__injalpha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injalpha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injalpha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injalpha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injbeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injbeta_d1_s42.v"
hierarchy -top s15850t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__injbeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injbeta_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__injbeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injbeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injbeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injbeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injdelta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injdelta_d1_s42.v"
hierarchy -top s15850t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__injdelta_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injdelta_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__injdelta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injdelta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injdelta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injdelta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injepsilon_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injepsilon_d1_s42.v"
hierarchy -top s15850t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__injepsilon_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injepsilon_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__injepsilon_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injepsilon_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injepsilon_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injepsilon_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injgamma_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injgamma_d1_s42.v"
hierarchy -top s15850t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__injgamma_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injgamma_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__injgamma_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injgamma_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injgamma_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injgamma_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injzeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injzeta_d1_s42.v"
hierarchy -top s15850t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__injzeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injzeta_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__injzeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt_keep/s15850t100/s15850t100__injzeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injzeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injzeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
