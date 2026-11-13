#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
OUT="${EQGUARD_ROOT}/generate_trans/yskeep2b"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
echo 'host,kind,stem,recipe,rc,bytes,always,cells,cec,secs' > $OUT/ys_manifest.csv
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000_clean__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/base/rs232t1000_clean.v"
hierarchy -top rs232t1000_clean
proc
flatten
rename -top rs232t1000_clean__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000_clean__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000_clean__ys_rt.ys -l $OUT/logs/rs232t1000_clean__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000_clean__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000_clean__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000_clean__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000_clean__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/base/rs232t1000_clean.v" --candidate $OUT/rs232t1000/rs232t1000_clean__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000_clean__ys_rt.log > $OUT/logs/cec_rs232t1000_clean__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000_clean__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,clean,rs232t1000_clean,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000_clean rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000_clean__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/base/rs232t1000_clean.v"
hierarchy -top rs232t1000_clean
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000_clean__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000_clean__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000_clean__ys_abc.ys -l $OUT/logs/rs232t1000_clean__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000_clean__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000_clean__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000_clean__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000_clean__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/base/rs232t1000_clean.v" --candidate $OUT/rs232t1000/rs232t1000_clean__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000_clean__ys_abc.log > $OUT/logs/cec_rs232t1000_clean__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000_clean__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,clean,rs232t1000_clean,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000_clean abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctldup_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctldup_d1_s42.v"
hierarchy -top rs232t1000__ctldup_d1_s42
proc
flatten
rename -top rs232t1000__ctldup_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctldup_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctldup_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctldup_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctldup_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctldup_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctldup_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctldup_d1_s42.v"
hierarchy -top rs232t1000__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctldup_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctldup_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctldup_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctldup_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctldup_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctldup_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v"
hierarchy -top rs232t1000__ctlmatcha_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatcha_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatcha_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatcha_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatcha_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v"
hierarchy -top rs232t1000__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatcha_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatcha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatcha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatcha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchb_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatchb_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatchb_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchb_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchb_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatchb_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatchb_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchb_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchb_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchc_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatchc_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatchc_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchc_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchc_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatchc_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatchc_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchc_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchc_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchd_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatchd_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatchd_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchd_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchd_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatchd_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatchd_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchd_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchd_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatche_d1_s42.v"
hierarchy -top rs232t1000__ctlmatche_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatche_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatche_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatche_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatche_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatche_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatche_d1_s42.v"
hierarchy -top rs232t1000__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatche_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatche_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatche_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatche_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatche_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchf_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatchf_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatchf_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchf_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchf_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatchf_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatchf_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchf_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchf_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchg_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchg_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchg_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatchg_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchg_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatchg_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchg_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchg_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatchg_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchg_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchg_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchg_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchg_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchg_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchg_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatchg_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchg_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatchg_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchg_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchg_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchg_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchg_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchg_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchg_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchg_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchh_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchh_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchh_d1_s42
proc
flatten
rename -top rs232t1000__ctlmatchh_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchh_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlmatchh_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchh_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchh_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlmatchh_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchh_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchh_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchh_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchh_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchh_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchh_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlmatchh_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchh_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlmatchh_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlmatchh_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchh_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchh_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchh_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchh_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchh_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchh_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlxor_d1_s42.v"
hierarchy -top rs232t1000__ctlxor_d1_s42
proc
flatten
rename -top rs232t1000__ctlxor_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__ctlxor_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlxor_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlxor_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlxor_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlxor_d1_s42.v"
hierarchy -top rs232t1000__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__ctlxor_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__ctlxor_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__ctlxor_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlxor_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlxor_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injalpha_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injalpha_d1_s42.v"
hierarchy -top rs232t1000__injalpha_d1_s42
proc
flatten
rename -top rs232t1000__injalpha_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injalpha_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injalpha_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injalpha_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injalpha_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injalpha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injalpha_d1_s42.v"
hierarchy -top rs232t1000__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injalpha_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injalpha_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injalpha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injalpha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injalpha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injbeta_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injbeta_d1_s42.v"
hierarchy -top rs232t1000__injbeta_d1_s42
proc
flatten
rename -top rs232t1000__injbeta_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injbeta_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injbeta_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injbeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injbeta_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injbeta_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injbeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injbeta_d1_s42.v"
hierarchy -top rs232t1000__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injbeta_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injbeta_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injbeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injbeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injbeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injbeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injdelta_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injdelta_d1_s42.v"
hierarchy -top rs232t1000__injdelta_d1_s42
proc
flatten
rename -top rs232t1000__injdelta_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injdelta_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injdelta_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injdelta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injdelta_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injdelta_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injdelta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injdelta_d1_s42.v"
hierarchy -top rs232t1000__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injdelta_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injdelta_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injdelta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injdelta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injdelta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injdelta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injepsilon_d1_s42.v"
hierarchy -top rs232t1000__injepsilon_d1_s42
proc
flatten
rename -top rs232t1000__injepsilon_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injepsilon_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injepsilon_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injepsilon_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injepsilon_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injepsilon_d1_s42.v"
hierarchy -top rs232t1000__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injepsilon_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injepsilon_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injepsilon_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injepsilon_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injepsilon_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injeta_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injeta_d1_s42.v"
hierarchy -top rs232t1000__injeta_d1_s42
proc
flatten
rename -top rs232t1000__injeta_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injeta_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injeta_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injeta_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injeta_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injeta_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injeta_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injeta_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injeta_d1_s42.v"
hierarchy -top rs232t1000__injeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injeta_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injeta_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injeta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injgamma_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injgamma_d1_s42.v"
hierarchy -top rs232t1000__injgamma_d1_s42
proc
flatten
rename -top rs232t1000__injgamma_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injgamma_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injgamma_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injgamma_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injgamma_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injgamma_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injgamma_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injgamma_d1_s42.v"
hierarchy -top rs232t1000__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injgamma_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injgamma_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injgamma_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injgamma_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injgamma_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injgamma_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injtheta_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injtheta_d1_s42.v"
hierarchy -top rs232t1000__injtheta_d1_s42
proc
flatten
rename -top rs232t1000__injtheta_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injtheta_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injtheta_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injtheta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injtheta_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injtheta_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injtheta_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injtheta_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injtheta_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injtheta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injtheta_d1_s42.v"
hierarchy -top rs232t1000__injtheta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injtheta_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injtheta_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injtheta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injtheta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injtheta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injtheta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injtheta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injtheta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injtheta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injtheta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injzeta_d1_s42__ys_rt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injzeta_d1_s42.v"
hierarchy -top rs232t1000__injzeta_d1_s42
proc
flatten
rename -top rs232t1000__injzeta_d1_s42__ys_rt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_rt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injzeta_d1_s42__ys_rt.ys -l $OUT/logs/rs232t1000__injzeta_d1_s42__ys_rt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_rt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_rt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_rt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_rt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injzeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_rt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_rt.log > $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_rt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_rt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injzeta_d1_s42,rt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injzeta_d1_s42 rt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injzeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injzeta_d1_s42.v"
hierarchy -top rs232t1000__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top rs232t1000__injzeta_d1_s42__ys_abc
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injzeta_d1_s42__ys_abc.ys -l $OUT/logs/rs232t1000__injzeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt2_keep/rs232t1000/rs232t1000__injzeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injzeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injzeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
