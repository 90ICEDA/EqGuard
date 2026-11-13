#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
OUT="${EQGUARD_ROOT}/generate_trans/yosys_netlists_beta"
V="${EQGUARD_VALI_DIR:?Set EQGUARD_VALI_DIR to the functional cell library directory}"
echo 'host,kind,stem,recipe,rc,bytes,always,cells,cec,secs' > $OUT/ys_manifest.csv
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000_clean__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v"
hierarchy -top rs232t1000_clean
proc
opt -full
flatten
opt_clean
rename -top rs232t1000_clean__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000_clean__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000_clean__ys_id.ys -l $OUT/logs/rs232t1000_clean__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000_clean__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000_clean__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000_clean__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000_clean__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v" --candidate $OUT/rs232t1000/rs232t1000_clean__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000_clean__ys_id.log > $OUT/logs/cec_rs232t1000_clean__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000_clean__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,clean,rs232t1000_clean,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000_clean id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000_clean__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v"
hierarchy -top rs232t1000_clean
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000_clean__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000_clean__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000_clean__ys_opt.ys -l $OUT/logs/rs232t1000_clean__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000_clean__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000_clean__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000_clean__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000_clean__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v" --candidate $OUT/rs232t1000/rs232t1000_clean__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000_clean__ys_opt.log > $OUT/logs/cec_rs232t1000_clean__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000_clean__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,clean,rs232t1000_clean,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000_clean opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000_clean__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v" --candidate $OUT/rs232t1000/rs232t1000_clean__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000_clean__ys_abc.log > $OUT/logs/cec_rs232t1000_clean__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000_clean__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,clean,rs232t1000_clean,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000_clean abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000_clean__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v"
hierarchy -top rs232t1000_clean
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000_clean__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000_clean__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000_clean__ys_aig.ys -l $OUT/logs/rs232t1000_clean__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000_clean__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000_clean__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000_clean__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000_clean__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v" --candidate $OUT/rs232t1000/rs232t1000_clean__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000_clean__ys_aig.log > $OUT/logs/cec_rs232t1000_clean__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000_clean__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,clean,rs232t1000_clean,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000_clean aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000_clean__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v"
hierarchy -top rs232t1000_clean
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000_clean__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000_clean__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000_clean__ys_nand.ys -l $OUT/logs/rs232t1000_clean__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000_clean__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000_clean__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000_clean__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000_clean__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/base/rs232t1000_clean.v" --candidate $OUT/rs232t1000/rs232t1000_clean__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000_clean__ys_nand.log > $OUT/logs/cec_rs232t1000_clean__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000_clean__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,clean,rs232t1000_clean,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000_clean nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctldup_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v"
hierarchy -top rs232t1000__ctldup_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctldup_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctldup_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctldup_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctldup_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctldup_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctldup_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v"
hierarchy -top rs232t1000__ctldup_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctldup_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctldup_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctldup_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctldup_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctldup_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctldup_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctldup_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctldup_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctldup_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v"
hierarchy -top rs232t1000__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctldup_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctldup_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctldup_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctldup_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctldup_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctldup_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v"
hierarchy -top rs232t1000__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctldup_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctldup_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctldup_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctldup_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctldup_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctldup_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctldup_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctldup_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v"
hierarchy -top rs232t1000__ctlmatcha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctlmatcha_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctlmatcha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatcha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatcha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v"
hierarchy -top rs232t1000__ctlmatcha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctlmatcha_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctlmatcha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatcha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatcha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatcha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatcha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v"
hierarchy -top rs232t1000__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctlmatcha_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctlmatcha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatcha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatcha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v"
hierarchy -top rs232t1000__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctlmatcha_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatcha_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctlmatcha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatcha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatcha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatcha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatcha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatcha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchb_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctlmatchb_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctlmatchb_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchb_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchb_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchb_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctlmatchb_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctlmatchb_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchb_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchb_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchb_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchb_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctlmatchb_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctlmatchb_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchb_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchb_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctlmatchb_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchb_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctlmatchb_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchb_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchb_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchb_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchb_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchb_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchc_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctlmatchc_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctlmatchc_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchc_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchc_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchc_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctlmatchc_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctlmatchc_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchc_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchc_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchc_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchc_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctlmatchc_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctlmatchc_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchc_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchc_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctlmatchc_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchc_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctlmatchc_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchc_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchc_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchc_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchc_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchc_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchd_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctlmatchd_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctlmatchd_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchd_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchd_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchd_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctlmatchd_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctlmatchd_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchd_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchd_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchd_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchd_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctlmatchd_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctlmatchd_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchd_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchd_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctlmatchd_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchd_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctlmatchd_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchd_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchd_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchd_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchd_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchd_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v"
hierarchy -top rs232t1000__ctlmatche_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctlmatche_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctlmatche_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatche_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatche_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v"
hierarchy -top rs232t1000__ctlmatche_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctlmatche_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctlmatche_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatche_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatche_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatche_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatche_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v"
hierarchy -top rs232t1000__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctlmatche_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctlmatche_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatche_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatche_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v"
hierarchy -top rs232t1000__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctlmatche_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatche_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctlmatche_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatche_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatche_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatche_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatche_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatche_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchf_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctlmatchf_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctlmatchf_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchf_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchf_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchf_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctlmatchf_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctlmatchf_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchf_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchf_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchf_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchf_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctlmatchf_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctlmatchf_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchf_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchf_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v"
hierarchy -top rs232t1000__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctlmatchf_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlmatchf_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctlmatchf_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlmatchf_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlmatchf_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlmatchf_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlmatchf_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlmatchf_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v"
hierarchy -top rs232t1000__ctlxor_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__ctlxor_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__ctlxor_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlxor_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlxor_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v"
hierarchy -top rs232t1000__ctlxor_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__ctlxor_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__ctlxor_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlxor_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlxor_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlxor_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlxor_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v"
hierarchy -top rs232t1000__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__ctlxor_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__ctlxor_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlxor_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlxor_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v"
hierarchy -top rs232t1000__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__ctlxor_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__ctlxor_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__ctlxor_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__ctlxor_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__ctlxor_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__ctlxor_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,control,rs232t1000__ctlxor_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__ctlxor_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injalpha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v"
hierarchy -top rs232t1000__injalpha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__injalpha_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injalpha_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__injalpha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injalpha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injalpha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injalpha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v"
hierarchy -top rs232t1000__injalpha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__injalpha_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injalpha_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__injalpha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injalpha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injalpha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injalpha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injalpha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injalpha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injalpha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v"
hierarchy -top rs232t1000__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__injalpha_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injalpha_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__injalpha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injalpha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injalpha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injalpha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v"
hierarchy -top rs232t1000__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__injalpha_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injalpha_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__injalpha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injalpha_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injalpha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injalpha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injalpha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injalpha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injbeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v"
hierarchy -top rs232t1000__injbeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__injbeta_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injbeta_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__injbeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injbeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injbeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injbeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v"
hierarchy -top rs232t1000__injbeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__injbeta_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injbeta_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__injbeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injbeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injbeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injbeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injbeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injbeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injbeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v"
hierarchy -top rs232t1000__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__injbeta_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injbeta_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__injbeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injbeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injbeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injbeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v"
hierarchy -top rs232t1000__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__injbeta_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injbeta_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__injbeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injbeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injbeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injbeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injbeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injbeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injdelta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v"
hierarchy -top rs232t1000__injdelta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__injdelta_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injdelta_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__injdelta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injdelta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injdelta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injdelta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v"
hierarchy -top rs232t1000__injdelta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__injdelta_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injdelta_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__injdelta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injdelta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injdelta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injdelta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injdelta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injdelta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injdelta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v"
hierarchy -top rs232t1000__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__injdelta_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injdelta_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__injdelta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injdelta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injdelta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injdelta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v"
hierarchy -top rs232t1000__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__injdelta_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injdelta_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__injdelta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injdelta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injdelta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injdelta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injdelta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injdelta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v"
hierarchy -top rs232t1000__injepsilon_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__injepsilon_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__injepsilon_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injepsilon_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injepsilon_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v"
hierarchy -top rs232t1000__injepsilon_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__injepsilon_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__injepsilon_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injepsilon_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injepsilon_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injepsilon_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injepsilon_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v"
hierarchy -top rs232t1000__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__injepsilon_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__injepsilon_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injepsilon_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injepsilon_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v"
hierarchy -top rs232t1000__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__injepsilon_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injepsilon_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__injepsilon_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injepsilon_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injepsilon_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injepsilon_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injepsilon_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injepsilon_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injgamma_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v"
hierarchy -top rs232t1000__injgamma_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__injgamma_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injgamma_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__injgamma_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injgamma_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injgamma_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injgamma_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v"
hierarchy -top rs232t1000__injgamma_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__injgamma_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injgamma_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__injgamma_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injgamma_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injgamma_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injgamma_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injgamma_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injgamma_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injgamma_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v"
hierarchy -top rs232t1000__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__injgamma_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injgamma_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__injgamma_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injgamma_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injgamma_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injgamma_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v"
hierarchy -top rs232t1000__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__injgamma_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injgamma_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__injgamma_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injgamma_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injgamma_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injgamma_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injgamma_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injgamma_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injzeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v"
hierarchy -top rs232t1000__injzeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top rs232t1000__injzeta_d1_s42__ys_id
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injzeta_d1_s42__ys_id.ys -l $OUT/logs/rs232t1000__injzeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_id.log > $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injzeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injzeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injzeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v"
hierarchy -top rs232t1000__injzeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top rs232t1000__injzeta_d1_s42__ys_opt
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injzeta_d1_s42__ys_opt.ys -l $OUT/logs/rs232t1000__injzeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_opt.log > $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injzeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injzeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injzeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_abc.log > $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injzeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injzeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injzeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v"
hierarchy -top rs232t1000__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top rs232t1000__injzeta_d1_s42__ys_aig
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injzeta_d1_s42__ys_aig.ys -l $OUT/logs/rs232t1000__injzeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_aig.log > $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injzeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injzeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/rs232t1000
cat > /tmp/ys_rs232t1000__injzeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v"
hierarchy -top rs232t1000__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top rs232t1000__injzeta_d1_s42__ys_nand
write_verilog -noattr $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_rs232t1000__injzeta_d1_s42__ys_nand.ys -l $OUT/logs/rs232t1000__injzeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/rs232t1000/rs232t1000__injzeta_d1_s42.v" --candidate $OUT/rs232t1000/rs232t1000__injzeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_nand.log > $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_rs232t1000__injzeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "rs232t1000,trojan,rs232t1000__injzeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[rs232t1000 rs232t1000__injzeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100_clean__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v"
hierarchy -top s15850t100_clean
proc
opt -full
flatten
opt_clean
rename -top s15850t100_clean__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100_clean__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100_clean__ys_id.ys -l $OUT/logs/s15850t100_clean__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100_clean__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100_clean__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100_clean__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100_clean__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v" --candidate $OUT/s15850t100/s15850t100_clean__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100_clean__ys_id.log > $OUT/logs/cec_s15850t100_clean__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100_clean__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,clean,s15850t100_clean,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100_clean id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100_clean__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v"
hierarchy -top s15850t100_clean
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100_clean__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100_clean__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100_clean__ys_opt.ys -l $OUT/logs/s15850t100_clean__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100_clean__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100_clean__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100_clean__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100_clean__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v" --candidate $OUT/s15850t100/s15850t100_clean__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100_clean__ys_opt.log > $OUT/logs/cec_s15850t100_clean__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100_clean__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,clean,s15850t100_clean,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100_clean opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100_clean__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v"
hierarchy -top s15850t100_clean
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100_clean__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100_clean__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100_clean__ys_abc.ys -l $OUT/logs/s15850t100_clean__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100_clean__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100_clean__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100_clean__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100_clean__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v" --candidate $OUT/s15850t100/s15850t100_clean__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100_clean__ys_abc.log > $OUT/logs/cec_s15850t100_clean__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100_clean__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,clean,s15850t100_clean,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100_clean abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100_clean__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v"
hierarchy -top s15850t100_clean
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100_clean__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100_clean__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100_clean__ys_aig.ys -l $OUT/logs/s15850t100_clean__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100_clean__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100_clean__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100_clean__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100_clean__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v" --candidate $OUT/s15850t100/s15850t100_clean__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100_clean__ys_aig.log > $OUT/logs/cec_s15850t100_clean__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100_clean__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,clean,s15850t100_clean,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100_clean aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100_clean__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v"
hierarchy -top s15850t100_clean
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100_clean__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100_clean__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100_clean__ys_nand.ys -l $OUT/logs/s15850t100_clean__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100_clean__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100_clean__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100_clean__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100_clean__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/base/s15850t100_clean.v" --candidate $OUT/s15850t100/s15850t100_clean__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100_clean__ys_nand.log > $OUT/logs/cec_s15850t100_clean__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100_clean__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,clean,s15850t100_clean,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100_clean nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctldup_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v"
hierarchy -top s15850t100__ctldup_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctldup_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctldup_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctldup_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctldup_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctldup_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctldup_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v"
hierarchy -top s15850t100__ctldup_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctldup_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctldup_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctldup_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctldup_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctldup_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctldup_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v"
hierarchy -top s15850t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctldup_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctldup_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctldup_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctldup_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctldup_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctldup_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v"
hierarchy -top s15850t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctldup_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctldup_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctldup_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctldup_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctldup_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctldup_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v"
hierarchy -top s15850t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctldup_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctldup_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctldup_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctldup_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctldup_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctldup_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctldup_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctldup_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v"
hierarchy -top s15850t100__ctlmatcha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctlmatcha_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctlmatcha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatcha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatcha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v"
hierarchy -top s15850t100__ctlmatcha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctlmatcha_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctlmatcha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatcha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatcha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v"
hierarchy -top s15850t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctlmatcha_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctlmatcha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatcha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatcha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v"
hierarchy -top s15850t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctlmatcha_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctlmatcha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatcha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatcha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v"
hierarchy -top s15850t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctlmatcha_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatcha_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctlmatcha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatcha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatcha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatcha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatcha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatcha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v"
hierarchy -top s15850t100__ctlmatchb_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctlmatchb_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctlmatchb_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchb_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchb_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v"
hierarchy -top s15850t100__ctlmatchb_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctlmatchb_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctlmatchb_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchb_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchb_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v"
hierarchy -top s15850t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctlmatchb_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctlmatchb_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchb_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchb_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v"
hierarchy -top s15850t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctlmatchb_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctlmatchb_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchb_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchb_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v"
hierarchy -top s15850t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctlmatchb_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchb_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctlmatchb_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchb_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchb_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchb_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchb_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchb_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v"
hierarchy -top s15850t100__ctlmatchc_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctlmatchc_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctlmatchc_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchc_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchc_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v"
hierarchy -top s15850t100__ctlmatchc_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctlmatchc_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctlmatchc_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchc_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchc_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v"
hierarchy -top s15850t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctlmatchc_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctlmatchc_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchc_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchc_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v"
hierarchy -top s15850t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctlmatchc_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctlmatchc_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchc_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchc_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v"
hierarchy -top s15850t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctlmatchc_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchc_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctlmatchc_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchc_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchc_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchc_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchc_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchc_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v"
hierarchy -top s15850t100__ctlmatchd_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctlmatchd_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctlmatchd_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchd_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchd_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v"
hierarchy -top s15850t100__ctlmatchd_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctlmatchd_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctlmatchd_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchd_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchd_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v"
hierarchy -top s15850t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctlmatchd_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctlmatchd_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchd_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchd_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v"
hierarchy -top s15850t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctlmatchd_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctlmatchd_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchd_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchd_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v"
hierarchy -top s15850t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctlmatchd_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchd_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctlmatchd_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchd_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchd_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchd_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchd_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchd_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v"
hierarchy -top s15850t100__ctlmatche_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctlmatche_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctlmatche_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatche_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatche_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v"
hierarchy -top s15850t100__ctlmatche_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctlmatche_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctlmatche_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatche_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatche_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v"
hierarchy -top s15850t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctlmatche_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctlmatche_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatche_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatche_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v"
hierarchy -top s15850t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctlmatche_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctlmatche_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatche_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatche_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v"
hierarchy -top s15850t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctlmatche_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatche_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctlmatche_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatche_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatche_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatche_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatche_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatche_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v"
hierarchy -top s15850t100__ctlmatchf_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctlmatchf_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctlmatchf_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchf_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchf_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v"
hierarchy -top s15850t100__ctlmatchf_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctlmatchf_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctlmatchf_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchf_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchf_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v"
hierarchy -top s15850t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctlmatchf_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctlmatchf_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchf_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchf_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v"
hierarchy -top s15850t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctlmatchf_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctlmatchf_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchf_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchf_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v"
hierarchy -top s15850t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctlmatchf_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlmatchf_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctlmatchf_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlmatchf_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlmatchf_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlmatchf_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlmatchf_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlmatchf_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlxor_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v"
hierarchy -top s15850t100__ctlxor_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__ctlxor_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlxor_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__ctlxor_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlxor_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlxor_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlxor_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v"
hierarchy -top s15850t100__ctlxor_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__ctlxor_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlxor_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__ctlxor_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlxor_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlxor_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlxor_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v"
hierarchy -top s15850t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s15850t100__ctlxor_d1_s42__ys_abc
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlxor_d1_s42__ys_abc.ys -l $OUT/logs/s15850t100__ctlxor_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlxor_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlxor_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlxor_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v"
hierarchy -top s15850t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__ctlxor_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlxor_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__ctlxor_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlxor_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlxor_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__ctlxor_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v"
hierarchy -top s15850t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__ctlxor_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__ctlxor_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__ctlxor_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__ctlxor_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__ctlxor_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__ctlxor_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,control,s15850t100__ctlxor_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__ctlxor_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injalpha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v"
hierarchy -top s15850t100__injalpha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__injalpha_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injalpha_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__injalpha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injalpha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injalpha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injalpha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v"
hierarchy -top s15850t100__injalpha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__injalpha_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injalpha_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__injalpha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injalpha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injalpha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injalpha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injalpha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injalpha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injalpha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v"
hierarchy -top s15850t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__injalpha_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injalpha_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__injalpha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injalpha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injalpha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injalpha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v"
hierarchy -top s15850t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__injalpha_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injalpha_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__injalpha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injalpha_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injalpha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injalpha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injalpha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injalpha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injbeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v"
hierarchy -top s15850t100__injbeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__injbeta_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injbeta_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__injbeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injbeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injbeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injbeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v"
hierarchy -top s15850t100__injbeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__injbeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injbeta_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__injbeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injbeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injbeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injbeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injbeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injbeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injbeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v"
hierarchy -top s15850t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__injbeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injbeta_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__injbeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injbeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injbeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injbeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v"
hierarchy -top s15850t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__injbeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injbeta_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__injbeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injbeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injbeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injbeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injbeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injbeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injdelta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v"
hierarchy -top s15850t100__injdelta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__injdelta_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injdelta_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__injdelta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injdelta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injdelta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injdelta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v"
hierarchy -top s15850t100__injdelta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__injdelta_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injdelta_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__injdelta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injdelta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injdelta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injdelta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injdelta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injdelta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injdelta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v"
hierarchy -top s15850t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__injdelta_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injdelta_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__injdelta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injdelta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injdelta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injdelta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v"
hierarchy -top s15850t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__injdelta_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injdelta_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__injdelta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injdelta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injdelta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injdelta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injdelta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injdelta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injepsilon_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v"
hierarchy -top s15850t100__injepsilon_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__injepsilon_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injepsilon_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__injepsilon_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injepsilon_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injepsilon_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injepsilon_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v"
hierarchy -top s15850t100__injepsilon_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__injepsilon_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injepsilon_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__injepsilon_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injepsilon_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injepsilon_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injepsilon_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injepsilon_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injepsilon_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injepsilon_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v"
hierarchy -top s15850t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__injepsilon_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injepsilon_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__injepsilon_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injepsilon_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injepsilon_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injepsilon_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v"
hierarchy -top s15850t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__injepsilon_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injepsilon_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__injepsilon_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injepsilon_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injepsilon_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injepsilon_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injepsilon_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injepsilon_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injgamma_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v"
hierarchy -top s15850t100__injgamma_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__injgamma_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injgamma_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__injgamma_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injgamma_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injgamma_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injgamma_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v"
hierarchy -top s15850t100__injgamma_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__injgamma_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injgamma_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__injgamma_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injgamma_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injgamma_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injgamma_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injgamma_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injgamma_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injgamma_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v"
hierarchy -top s15850t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__injgamma_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injgamma_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__injgamma_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injgamma_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injgamma_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injgamma_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v"
hierarchy -top s15850t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__injgamma_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injgamma_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__injgamma_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injgamma_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injgamma_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injgamma_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injgamma_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injgamma_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injzeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v"
hierarchy -top s15850t100__injzeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s15850t100__injzeta_d1_s42__ys_id
write_verilog -noattr $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injzeta_d1_s42__ys_id.ys -l $OUT/logs/s15850t100__injzeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_id.log > $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injzeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injzeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injzeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v"
hierarchy -top s15850t100__injzeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s15850t100__injzeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injzeta_d1_s42__ys_opt.ys -l $OUT/logs/s15850t100__injzeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_opt.log > $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injzeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injzeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injzeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v"
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
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_abc.log > $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injzeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injzeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injzeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v"
hierarchy -top s15850t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s15850t100__injzeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injzeta_d1_s42__ys_aig.ys -l $OUT/logs/s15850t100__injzeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_aig.log > $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injzeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injzeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s15850t100
cat > /tmp/ys_s15850t100__injzeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v"
hierarchy -top s15850t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s15850t100__injzeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s15850t100__injzeta_d1_s42__ys_nand.ys -l $OUT/logs/s15850t100__injzeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s15850t100/s15850t100__injzeta_d1_s42.v" --candidate $OUT/s15850t100/s15850t100__injzeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_nand.log > $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s15850t100__injzeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s15850t100,trojan,s15850t100__injzeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s15850t100 s15850t100__injzeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200_clean__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v"
hierarchy -top s35932t200_clean
proc
opt -full
flatten
opt_clean
rename -top s35932t200_clean__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200_clean__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200_clean__ys_id.ys -l $OUT/logs/s35932t200_clean__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200_clean__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200_clean__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200_clean__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200_clean__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v" --candidate $OUT/s35932t200/s35932t200_clean__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200_clean__ys_id.log > $OUT/logs/cec_s35932t200_clean__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200_clean__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,clean,s35932t200_clean,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200_clean id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200_clean__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v"
hierarchy -top s35932t200_clean
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200_clean__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200_clean__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200_clean__ys_opt.ys -l $OUT/logs/s35932t200_clean__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200_clean__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200_clean__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200_clean__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200_clean__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v" --candidate $OUT/s35932t200/s35932t200_clean__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200_clean__ys_opt.log > $OUT/logs/cec_s35932t200_clean__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200_clean__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,clean,s35932t200_clean,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200_clean opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200_clean__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v"
hierarchy -top s35932t200_clean
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200_clean__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200_clean__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200_clean__ys_abc.ys -l $OUT/logs/s35932t200_clean__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200_clean__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200_clean__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200_clean__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200_clean__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v" --candidate $OUT/s35932t200/s35932t200_clean__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200_clean__ys_abc.log > $OUT/logs/cec_s35932t200_clean__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200_clean__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,clean,s35932t200_clean,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200_clean abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200_clean__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v"
hierarchy -top s35932t200_clean
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200_clean__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200_clean__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200_clean__ys_aig.ys -l $OUT/logs/s35932t200_clean__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200_clean__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200_clean__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200_clean__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200_clean__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v" --candidate $OUT/s35932t200/s35932t200_clean__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200_clean__ys_aig.log > $OUT/logs/cec_s35932t200_clean__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200_clean__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,clean,s35932t200_clean,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200_clean aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200_clean__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v"
hierarchy -top s35932t200_clean
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200_clean__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200_clean__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200_clean__ys_nand.ys -l $OUT/logs/s35932t200_clean__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200_clean__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200_clean__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200_clean__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200_clean__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/base/s35932t200_clean.v" --candidate $OUT/s35932t200/s35932t200_clean__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200_clean__ys_nand.log > $OUT/logs/cec_s35932t200_clean__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200_clean__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,clean,s35932t200_clean,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200_clean nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctldup_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v"
hierarchy -top s35932t200__ctldup_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctldup_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctldup_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctldup_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctldup_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctldup_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctldup_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v"
hierarchy -top s35932t200__ctldup_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctldup_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctldup_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctldup_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctldup_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctldup_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctldup_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v"
hierarchy -top s35932t200__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctldup_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctldup_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctldup_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctldup_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctldup_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctldup_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v"
hierarchy -top s35932t200__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctldup_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctldup_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctldup_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctldup_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctldup_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctldup_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v"
hierarchy -top s35932t200__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctldup_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctldup_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctldup_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctldup_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctldup_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctldup_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctldup_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctldup_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v"
hierarchy -top s35932t200__ctlmatcha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctlmatcha_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctlmatcha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatcha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatcha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v"
hierarchy -top s35932t200__ctlmatcha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctlmatcha_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctlmatcha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatcha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatcha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v"
hierarchy -top s35932t200__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctlmatcha_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctlmatcha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatcha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatcha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v"
hierarchy -top s35932t200__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctlmatcha_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctlmatcha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatcha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatcha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v"
hierarchy -top s35932t200__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctlmatcha_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatcha_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctlmatcha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatcha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatcha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatcha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatcha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatcha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v"
hierarchy -top s35932t200__ctlmatchb_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctlmatchb_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctlmatchb_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchb_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchb_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v"
hierarchy -top s35932t200__ctlmatchb_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctlmatchb_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctlmatchb_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchb_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchb_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v"
hierarchy -top s35932t200__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctlmatchb_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctlmatchb_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchb_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchb_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v"
hierarchy -top s35932t200__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctlmatchb_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctlmatchb_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchb_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchb_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v"
hierarchy -top s35932t200__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctlmatchb_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchb_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctlmatchb_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchb_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchb_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchb_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchb_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchb_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v"
hierarchy -top s35932t200__ctlmatchc_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctlmatchc_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctlmatchc_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchc_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchc_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v"
hierarchy -top s35932t200__ctlmatchc_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctlmatchc_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctlmatchc_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchc_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchc_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v"
hierarchy -top s35932t200__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctlmatchc_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctlmatchc_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchc_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchc_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v"
hierarchy -top s35932t200__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctlmatchc_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctlmatchc_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchc_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchc_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v"
hierarchy -top s35932t200__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctlmatchc_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchc_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctlmatchc_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchc_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchc_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchc_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchc_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchc_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v"
hierarchy -top s35932t200__ctlmatchd_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctlmatchd_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctlmatchd_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchd_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchd_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v"
hierarchy -top s35932t200__ctlmatchd_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctlmatchd_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctlmatchd_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchd_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchd_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v"
hierarchy -top s35932t200__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctlmatchd_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctlmatchd_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchd_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchd_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v"
hierarchy -top s35932t200__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctlmatchd_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctlmatchd_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchd_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchd_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v"
hierarchy -top s35932t200__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctlmatchd_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchd_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctlmatchd_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchd_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchd_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchd_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchd_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchd_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v"
hierarchy -top s35932t200__ctlmatche_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctlmatche_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctlmatche_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatche_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatche_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v"
hierarchy -top s35932t200__ctlmatche_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctlmatche_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctlmatche_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatche_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatche_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v"
hierarchy -top s35932t200__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctlmatche_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctlmatche_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatche_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatche_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v"
hierarchy -top s35932t200__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctlmatche_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctlmatche_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatche_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatche_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v"
hierarchy -top s35932t200__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctlmatche_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatche_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctlmatche_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatche_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatche_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatche_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatche_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatche_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v"
hierarchy -top s35932t200__ctlmatchf_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctlmatchf_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctlmatchf_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchf_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchf_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v"
hierarchy -top s35932t200__ctlmatchf_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctlmatchf_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctlmatchf_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchf_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchf_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v"
hierarchy -top s35932t200__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctlmatchf_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctlmatchf_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchf_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchf_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v"
hierarchy -top s35932t200__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctlmatchf_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctlmatchf_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchf_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchf_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v"
hierarchy -top s35932t200__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctlmatchf_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlmatchf_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctlmatchf_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlmatchf_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlmatchf_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlmatchf_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlmatchf_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlmatchf_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlxor_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v"
hierarchy -top s35932t200__ctlxor_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__ctlxor_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlxor_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__ctlxor_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlxor_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlxor_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlxor_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v"
hierarchy -top s35932t200__ctlxor_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__ctlxor_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlxor_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__ctlxor_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlxor_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlxor_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlxor_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v"
hierarchy -top s35932t200__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__ctlxor_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlxor_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__ctlxor_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlxor_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlxor_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlxor_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v"
hierarchy -top s35932t200__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__ctlxor_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlxor_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__ctlxor_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlxor_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlxor_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__ctlxor_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v"
hierarchy -top s35932t200__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__ctlxor_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__ctlxor_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__ctlxor_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__ctlxor_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__ctlxor_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__ctlxor_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,control,s35932t200__ctlxor_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__ctlxor_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injalpha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v"
hierarchy -top s35932t200__injalpha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__injalpha_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injalpha_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__injalpha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injalpha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injalpha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injalpha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v"
hierarchy -top s35932t200__injalpha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__injalpha_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injalpha_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__injalpha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injalpha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injalpha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injalpha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v"
hierarchy -top s35932t200__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__injalpha_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injalpha_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__injalpha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injalpha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injalpha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injalpha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v"
hierarchy -top s35932t200__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__injalpha_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injalpha_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__injalpha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injalpha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injalpha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injalpha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v"
hierarchy -top s35932t200__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__injalpha_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injalpha_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__injalpha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injalpha_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injalpha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injalpha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injalpha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injalpha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injbeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v"
hierarchy -top s35932t200__injbeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__injbeta_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injbeta_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__injbeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injbeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injbeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injbeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v"
hierarchy -top s35932t200__injbeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__injbeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injbeta_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__injbeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injbeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injbeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injbeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v"
hierarchy -top s35932t200__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__injbeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injbeta_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__injbeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injbeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injbeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injbeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v"
hierarchy -top s35932t200__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__injbeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injbeta_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__injbeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injbeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injbeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injbeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v"
hierarchy -top s35932t200__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__injbeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injbeta_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__injbeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injbeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injbeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injbeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injbeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injbeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injdelta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v"
hierarchy -top s35932t200__injdelta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__injdelta_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injdelta_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__injdelta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injdelta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injdelta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injdelta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v"
hierarchy -top s35932t200__injdelta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__injdelta_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injdelta_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__injdelta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injdelta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injdelta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injdelta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v"
hierarchy -top s35932t200__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__injdelta_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injdelta_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__injdelta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injdelta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injdelta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injdelta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v"
hierarchy -top s35932t200__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__injdelta_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injdelta_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__injdelta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injdelta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injdelta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injdelta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v"
hierarchy -top s35932t200__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__injdelta_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injdelta_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__injdelta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injdelta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injdelta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injdelta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injdelta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injdelta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injepsilon_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v"
hierarchy -top s35932t200__injepsilon_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__injepsilon_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injepsilon_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__injepsilon_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injepsilon_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injepsilon_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injepsilon_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v"
hierarchy -top s35932t200__injepsilon_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__injepsilon_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injepsilon_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__injepsilon_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injepsilon_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injepsilon_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injepsilon_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v"
hierarchy -top s35932t200__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__injepsilon_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injepsilon_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__injepsilon_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injepsilon_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injepsilon_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injepsilon_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v"
hierarchy -top s35932t200__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__injepsilon_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injepsilon_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__injepsilon_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injepsilon_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injepsilon_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injepsilon_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v"
hierarchy -top s35932t200__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__injepsilon_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injepsilon_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__injepsilon_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injepsilon_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injepsilon_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injepsilon_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injepsilon_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injepsilon_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injgamma_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v"
hierarchy -top s35932t200__injgamma_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__injgamma_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injgamma_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__injgamma_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injgamma_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injgamma_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injgamma_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v"
hierarchy -top s35932t200__injgamma_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__injgamma_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injgamma_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__injgamma_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injgamma_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injgamma_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injgamma_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v"
hierarchy -top s35932t200__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__injgamma_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injgamma_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__injgamma_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injgamma_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injgamma_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injgamma_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v"
hierarchy -top s35932t200__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__injgamma_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injgamma_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__injgamma_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injgamma_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injgamma_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injgamma_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v"
hierarchy -top s35932t200__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__injgamma_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injgamma_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__injgamma_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injgamma_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injgamma_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injgamma_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injgamma_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injgamma_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injzeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v"
hierarchy -top s35932t200__injzeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s35932t200__injzeta_d1_s42__ys_id
write_verilog -noattr $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injzeta_d1_s42__ys_id.ys -l $OUT/logs/s35932t200__injzeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_id.log > $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injzeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injzeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injzeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v"
hierarchy -top s35932t200__injzeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s35932t200__injzeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injzeta_d1_s42__ys_opt.ys -l $OUT/logs/s35932t200__injzeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_opt.log > $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injzeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injzeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injzeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v"
hierarchy -top s35932t200__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s35932t200__injzeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injzeta_d1_s42__ys_abc.ys -l $OUT/logs/s35932t200__injzeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_abc.log > $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injzeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injzeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injzeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v"
hierarchy -top s35932t200__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s35932t200__injzeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injzeta_d1_s42__ys_aig.ys -l $OUT/logs/s35932t200__injzeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_aig.log > $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injzeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injzeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s35932t200
cat > /tmp/ys_s35932t200__injzeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v"
hierarchy -top s35932t200__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s35932t200__injzeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s35932t200__injzeta_d1_s42__ys_nand.ys -l $OUT/logs/s35932t200__injzeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s35932t200/s35932t200__injzeta_d1_s42.v" --candidate $OUT/s35932t200/s35932t200__injzeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_nand.log > $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s35932t200__injzeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s35932t200,trojan,s35932t200__injzeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s35932t200 s35932t200__injzeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100_clean__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v"
hierarchy -top s38417t100_clean
proc
opt -full
flatten
opt_clean
rename -top s38417t100_clean__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100_clean__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100_clean__ys_id.ys -l $OUT/logs/s38417t100_clean__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100_clean__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100_clean__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100_clean__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100_clean__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v" --candidate $OUT/s38417t100/s38417t100_clean__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100_clean__ys_id.log > $OUT/logs/cec_s38417t100_clean__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100_clean__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,clean,s38417t100_clean,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100_clean id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100_clean__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v"
hierarchy -top s38417t100_clean
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100_clean__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100_clean__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100_clean__ys_opt.ys -l $OUT/logs/s38417t100_clean__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100_clean__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100_clean__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100_clean__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100_clean__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v" --candidate $OUT/s38417t100/s38417t100_clean__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100_clean__ys_opt.log > $OUT/logs/cec_s38417t100_clean__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100_clean__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,clean,s38417t100_clean,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100_clean opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100_clean__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v"
hierarchy -top s38417t100_clean
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100_clean__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100_clean__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100_clean__ys_abc.ys -l $OUT/logs/s38417t100_clean__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100_clean__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100_clean__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100_clean__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100_clean__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v" --candidate $OUT/s38417t100/s38417t100_clean__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100_clean__ys_abc.log > $OUT/logs/cec_s38417t100_clean__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100_clean__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,clean,s38417t100_clean,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100_clean abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100_clean__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v"
hierarchy -top s38417t100_clean
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100_clean__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100_clean__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100_clean__ys_aig.ys -l $OUT/logs/s38417t100_clean__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100_clean__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100_clean__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100_clean__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100_clean__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v" --candidate $OUT/s38417t100/s38417t100_clean__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100_clean__ys_aig.log > $OUT/logs/cec_s38417t100_clean__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100_clean__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,clean,s38417t100_clean,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100_clean aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100_clean__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v"
hierarchy -top s38417t100_clean
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100_clean__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100_clean__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100_clean__ys_nand.ys -l $OUT/logs/s38417t100_clean__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100_clean__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100_clean__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100_clean__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100_clean__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/base/s38417t100_clean.v" --candidate $OUT/s38417t100/s38417t100_clean__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100_clean__ys_nand.log > $OUT/logs/cec_s38417t100_clean__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100_clean__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,clean,s38417t100_clean,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100_clean nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctldup_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v"
hierarchy -top s38417t100__ctldup_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctldup_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctldup_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctldup_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctldup_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctldup_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctldup_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v"
hierarchy -top s38417t100__ctldup_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctldup_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctldup_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctldup_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctldup_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctldup_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctldup_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v"
hierarchy -top s38417t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctldup_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctldup_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctldup_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctldup_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctldup_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctldup_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v"
hierarchy -top s38417t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctldup_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctldup_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctldup_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctldup_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctldup_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctldup_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v"
hierarchy -top s38417t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctldup_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctldup_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctldup_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctldup_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctldup_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctldup_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctldup_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctldup_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v"
hierarchy -top s38417t100__ctlmatcha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctlmatcha_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctlmatcha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatcha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatcha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v"
hierarchy -top s38417t100__ctlmatcha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctlmatcha_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctlmatcha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatcha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatcha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v"
hierarchy -top s38417t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctlmatcha_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctlmatcha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatcha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatcha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v"
hierarchy -top s38417t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctlmatcha_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctlmatcha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatcha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatcha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v"
hierarchy -top s38417t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctlmatcha_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatcha_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctlmatcha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatcha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatcha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatcha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatcha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v"
hierarchy -top s38417t100__ctlmatchb_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctlmatchb_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctlmatchb_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchb_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchb_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v"
hierarchy -top s38417t100__ctlmatchb_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctlmatchb_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctlmatchb_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchb_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchb_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v"
hierarchy -top s38417t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctlmatchb_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctlmatchb_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchb_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchb_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v"
hierarchy -top s38417t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctlmatchb_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctlmatchb_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchb_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchb_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v"
hierarchy -top s38417t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctlmatchb_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchb_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctlmatchb_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchb_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchb_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchb_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchb_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v"
hierarchy -top s38417t100__ctlmatchc_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctlmatchc_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctlmatchc_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchc_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchc_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v"
hierarchy -top s38417t100__ctlmatchc_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctlmatchc_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctlmatchc_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchc_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchc_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v"
hierarchy -top s38417t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctlmatchc_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctlmatchc_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchc_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchc_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v"
hierarchy -top s38417t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctlmatchc_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctlmatchc_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchc_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchc_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v"
hierarchy -top s38417t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctlmatchc_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchc_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctlmatchc_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchc_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchc_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchc_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchc_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v"
hierarchy -top s38417t100__ctlmatchd_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctlmatchd_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctlmatchd_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchd_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchd_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v"
hierarchy -top s38417t100__ctlmatchd_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctlmatchd_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctlmatchd_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchd_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchd_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v"
hierarchy -top s38417t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctlmatchd_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctlmatchd_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchd_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchd_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v"
hierarchy -top s38417t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctlmatchd_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctlmatchd_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchd_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchd_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v"
hierarchy -top s38417t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctlmatchd_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchd_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctlmatchd_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchd_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchd_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchd_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchd_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v"
hierarchy -top s38417t100__ctlmatche_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctlmatche_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctlmatche_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatche_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatche_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v"
hierarchy -top s38417t100__ctlmatche_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctlmatche_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctlmatche_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatche_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatche_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v"
hierarchy -top s38417t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctlmatche_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctlmatche_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatche_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatche_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v"
hierarchy -top s38417t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctlmatche_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctlmatche_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatche_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatche_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v"
hierarchy -top s38417t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctlmatche_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatche_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctlmatche_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatche_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatche_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatche_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatche_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatche_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v"
hierarchy -top s38417t100__ctlmatchf_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctlmatchf_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctlmatchf_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchf_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchf_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v"
hierarchy -top s38417t100__ctlmatchf_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctlmatchf_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctlmatchf_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchf_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchf_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v"
hierarchy -top s38417t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctlmatchf_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctlmatchf_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchf_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchf_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v"
hierarchy -top s38417t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctlmatchf_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctlmatchf_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchf_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchf_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v"
hierarchy -top s38417t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctlmatchf_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlmatchf_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctlmatchf_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlmatchf_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlmatchf_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlmatchf_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlmatchf_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlxor_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v"
hierarchy -top s38417t100__ctlxor_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__ctlxor_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlxor_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__ctlxor_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlxor_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlxor_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlxor_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v"
hierarchy -top s38417t100__ctlxor_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__ctlxor_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlxor_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__ctlxor_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlxor_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlxor_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlxor_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v"
hierarchy -top s38417t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__ctlxor_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlxor_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__ctlxor_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlxor_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlxor_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlxor_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v"
hierarchy -top s38417t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__ctlxor_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlxor_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__ctlxor_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlxor_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlxor_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__ctlxor_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v"
hierarchy -top s38417t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__ctlxor_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__ctlxor_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__ctlxor_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__ctlxor_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__ctlxor_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__ctlxor_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,control,s38417t100__ctlxor_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__ctlxor_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injalpha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v"
hierarchy -top s38417t100__injalpha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__injalpha_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injalpha_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__injalpha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injalpha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injalpha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injalpha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v"
hierarchy -top s38417t100__injalpha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__injalpha_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injalpha_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__injalpha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injalpha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injalpha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injalpha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v"
hierarchy -top s38417t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__injalpha_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injalpha_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__injalpha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injalpha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injalpha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injalpha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v"
hierarchy -top s38417t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__injalpha_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injalpha_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__injalpha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injalpha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injalpha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injalpha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v"
hierarchy -top s38417t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__injalpha_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injalpha_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__injalpha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injalpha_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injalpha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injalpha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injalpha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injalpha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injbeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v"
hierarchy -top s38417t100__injbeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__injbeta_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injbeta_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__injbeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injbeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injbeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injbeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v"
hierarchy -top s38417t100__injbeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__injbeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injbeta_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__injbeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injbeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injbeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injbeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v"
hierarchy -top s38417t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__injbeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injbeta_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__injbeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injbeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injbeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injbeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v"
hierarchy -top s38417t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__injbeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injbeta_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__injbeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injbeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injbeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injbeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v"
hierarchy -top s38417t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__injbeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injbeta_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__injbeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injbeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injbeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injbeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injbeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injbeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injdelta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v"
hierarchy -top s38417t100__injdelta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__injdelta_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injdelta_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__injdelta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injdelta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injdelta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injdelta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v"
hierarchy -top s38417t100__injdelta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__injdelta_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injdelta_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__injdelta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injdelta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injdelta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injdelta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v"
hierarchy -top s38417t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__injdelta_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injdelta_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__injdelta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injdelta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injdelta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injdelta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v"
hierarchy -top s38417t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__injdelta_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injdelta_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__injdelta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injdelta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injdelta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injdelta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v"
hierarchy -top s38417t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__injdelta_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injdelta_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__injdelta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injdelta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injdelta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injdelta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injdelta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injdelta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injepsilon_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v"
hierarchy -top s38417t100__injepsilon_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__injepsilon_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injepsilon_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__injepsilon_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injepsilon_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injepsilon_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injepsilon_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v"
hierarchy -top s38417t100__injepsilon_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__injepsilon_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injepsilon_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__injepsilon_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injepsilon_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injepsilon_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injepsilon_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v"
hierarchy -top s38417t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__injepsilon_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injepsilon_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__injepsilon_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injepsilon_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injepsilon_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injepsilon_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v"
hierarchy -top s38417t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__injepsilon_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injepsilon_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__injepsilon_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injepsilon_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injepsilon_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injepsilon_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v"
hierarchy -top s38417t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__injepsilon_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injepsilon_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__injepsilon_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injepsilon_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injepsilon_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injepsilon_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injepsilon_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injepsilon_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injgamma_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v"
hierarchy -top s38417t100__injgamma_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__injgamma_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injgamma_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__injgamma_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injgamma_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injgamma_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injgamma_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v"
hierarchy -top s38417t100__injgamma_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__injgamma_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injgamma_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__injgamma_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injgamma_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injgamma_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injgamma_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v"
hierarchy -top s38417t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__injgamma_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injgamma_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__injgamma_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injgamma_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injgamma_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injgamma_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v"
hierarchy -top s38417t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__injgamma_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injgamma_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__injgamma_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injgamma_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injgamma_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injgamma_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v"
hierarchy -top s38417t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__injgamma_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injgamma_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__injgamma_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injgamma_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injgamma_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injgamma_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injgamma_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injgamma_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injzeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v"
hierarchy -top s38417t100__injzeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38417t100__injzeta_d1_s42__ys_id
write_verilog -noattr $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injzeta_d1_s42__ys_id.ys -l $OUT/logs/s38417t100__injzeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_id.log > $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injzeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injzeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injzeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v"
hierarchy -top s38417t100__injzeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38417t100__injzeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injzeta_d1_s42__ys_opt.ys -l $OUT/logs/s38417t100__injzeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_opt.log > $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injzeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injzeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injzeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v"
hierarchy -top s38417t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38417t100__injzeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injzeta_d1_s42__ys_abc.ys -l $OUT/logs/s38417t100__injzeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_abc.log > $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injzeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injzeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injzeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v"
hierarchy -top s38417t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38417t100__injzeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injzeta_d1_s42__ys_aig.ys -l $OUT/logs/s38417t100__injzeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_aig.log > $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injzeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injzeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38417t100
cat > /tmp/ys_s38417t100__injzeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v"
hierarchy -top s38417t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38417t100__injzeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38417t100__injzeta_d1_s42__ys_nand.ys -l $OUT/logs/s38417t100__injzeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38417t100/s38417t100__injzeta_d1_s42.v" --candidate $OUT/s38417t100/s38417t100__injzeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_nand.log > $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38417t100__injzeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38417t100,trojan,s38417t100__injzeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38417t100 s38417t100__injzeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100_clean__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v"
hierarchy -top s38584t100_clean
proc
opt -full
flatten
opt_clean
rename -top s38584t100_clean__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100_clean__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100_clean__ys_id.ys -l $OUT/logs/s38584t100_clean__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100_clean__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100_clean__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100_clean__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100_clean__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v" --candidate $OUT/s38584t100/s38584t100_clean__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100_clean__ys_id.log > $OUT/logs/cec_s38584t100_clean__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100_clean__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,clean,s38584t100_clean,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100_clean id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100_clean__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v"
hierarchy -top s38584t100_clean
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100_clean__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100_clean__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100_clean__ys_opt.ys -l $OUT/logs/s38584t100_clean__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100_clean__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100_clean__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100_clean__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100_clean__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v" --candidate $OUT/s38584t100/s38584t100_clean__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100_clean__ys_opt.log > $OUT/logs/cec_s38584t100_clean__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100_clean__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,clean,s38584t100_clean,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100_clean opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100_clean__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v"
hierarchy -top s38584t100_clean
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100_clean__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100_clean__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100_clean__ys_abc.ys -l $OUT/logs/s38584t100_clean__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100_clean__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100_clean__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100_clean__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100_clean__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v" --candidate $OUT/s38584t100/s38584t100_clean__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100_clean__ys_abc.log > $OUT/logs/cec_s38584t100_clean__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100_clean__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,clean,s38584t100_clean,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100_clean abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100_clean__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v"
hierarchy -top s38584t100_clean
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100_clean__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100_clean__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100_clean__ys_aig.ys -l $OUT/logs/s38584t100_clean__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100_clean__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100_clean__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100_clean__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100_clean__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v" --candidate $OUT/s38584t100/s38584t100_clean__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100_clean__ys_aig.log > $OUT/logs/cec_s38584t100_clean__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100_clean__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,clean,s38584t100_clean,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100_clean aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100_clean__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v"
hierarchy -top s38584t100_clean
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100_clean__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100_clean__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100_clean__ys_nand.ys -l $OUT/logs/s38584t100_clean__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100_clean__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100_clean__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100_clean__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100_clean__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/base/s38584t100_clean.v" --candidate $OUT/s38584t100/s38584t100_clean__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100_clean__ys_nand.log > $OUT/logs/cec_s38584t100_clean__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100_clean__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,clean,s38584t100_clean,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100_clean nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctldup_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v"
hierarchy -top s38584t100__ctldup_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctldup_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctldup_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctldup_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctldup_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctldup_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctldup_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v"
hierarchy -top s38584t100__ctldup_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctldup_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctldup_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctldup_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctldup_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctldup_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctldup_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v"
hierarchy -top s38584t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctldup_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctldup_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctldup_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctldup_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctldup_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctldup_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v"
hierarchy -top s38584t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctldup_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctldup_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctldup_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctldup_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctldup_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctldup_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v"
hierarchy -top s38584t100__ctldup_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctldup_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctldup_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctldup_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctldup_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctldup_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctldup_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctldup_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctldup_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v"
hierarchy -top s38584t100__ctlmatcha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctlmatcha_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctlmatcha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatcha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatcha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v"
hierarchy -top s38584t100__ctlmatcha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctlmatcha_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctlmatcha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatcha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatcha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v"
hierarchy -top s38584t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctlmatcha_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctlmatcha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatcha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatcha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v"
hierarchy -top s38584t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctlmatcha_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctlmatcha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatcha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatcha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v"
hierarchy -top s38584t100__ctlmatcha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctlmatcha_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatcha_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctlmatcha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatcha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatcha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatcha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatcha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatcha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v"
hierarchy -top s38584t100__ctlmatchb_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctlmatchb_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctlmatchb_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchb_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchb_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v"
hierarchy -top s38584t100__ctlmatchb_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctlmatchb_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctlmatchb_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchb_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchb_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v"
hierarchy -top s38584t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctlmatchb_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctlmatchb_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchb_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchb_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v"
hierarchy -top s38584t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctlmatchb_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctlmatchb_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchb_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchb_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v"
hierarchy -top s38584t100__ctlmatchb_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctlmatchb_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchb_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctlmatchb_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchb_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchb_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchb_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchb_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchb_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v"
hierarchy -top s38584t100__ctlmatchc_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctlmatchc_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctlmatchc_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchc_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchc_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v"
hierarchy -top s38584t100__ctlmatchc_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctlmatchc_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctlmatchc_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchc_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchc_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v"
hierarchy -top s38584t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctlmatchc_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctlmatchc_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchc_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchc_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v"
hierarchy -top s38584t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctlmatchc_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctlmatchc_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchc_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchc_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v"
hierarchy -top s38584t100__ctlmatchc_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctlmatchc_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchc_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctlmatchc_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchc_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchc_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchc_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchc_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchc_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v"
hierarchy -top s38584t100__ctlmatchd_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctlmatchd_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctlmatchd_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchd_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchd_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v"
hierarchy -top s38584t100__ctlmatchd_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctlmatchd_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctlmatchd_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchd_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchd_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v"
hierarchy -top s38584t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctlmatchd_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctlmatchd_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchd_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchd_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v"
hierarchy -top s38584t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctlmatchd_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctlmatchd_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchd_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchd_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v"
hierarchy -top s38584t100__ctlmatchd_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctlmatchd_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchd_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctlmatchd_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchd_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchd_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchd_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchd_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchd_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v"
hierarchy -top s38584t100__ctlmatche_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctlmatche_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctlmatche_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatche_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatche_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v"
hierarchy -top s38584t100__ctlmatche_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctlmatche_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctlmatche_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatche_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatche_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v"
hierarchy -top s38584t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctlmatche_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctlmatche_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatche_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatche_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v"
hierarchy -top s38584t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctlmatche_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctlmatche_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatche_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatche_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v"
hierarchy -top s38584t100__ctlmatche_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctlmatche_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatche_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctlmatche_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatche_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatche_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatche_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatche_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatche_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v"
hierarchy -top s38584t100__ctlmatchf_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctlmatchf_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctlmatchf_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchf_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchf_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v"
hierarchy -top s38584t100__ctlmatchf_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctlmatchf_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctlmatchf_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchf_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchf_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v"
hierarchy -top s38584t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctlmatchf_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctlmatchf_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchf_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchf_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v"
hierarchy -top s38584t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctlmatchf_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctlmatchf_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchf_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchf_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v"
hierarchy -top s38584t100__ctlmatchf_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctlmatchf_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlmatchf_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctlmatchf_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlmatchf_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlmatchf_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlmatchf_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlmatchf_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlmatchf_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlxor_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v"
hierarchy -top s38584t100__ctlxor_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__ctlxor_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlxor_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__ctlxor_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlxor_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlxor_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlxor_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v"
hierarchy -top s38584t100__ctlxor_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__ctlxor_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlxor_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__ctlxor_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlxor_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlxor_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlxor_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v"
hierarchy -top s38584t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__ctlxor_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlxor_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__ctlxor_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlxor_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlxor_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlxor_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v"
hierarchy -top s38584t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__ctlxor_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlxor_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__ctlxor_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlxor_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlxor_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__ctlxor_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v"
hierarchy -top s38584t100__ctlxor_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__ctlxor_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__ctlxor_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__ctlxor_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__ctlxor_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__ctlxor_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__ctlxor_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,control,s38584t100__ctlxor_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__ctlxor_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injalpha_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v"
hierarchy -top s38584t100__injalpha_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__injalpha_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injalpha_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__injalpha_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injalpha_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injalpha_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injalpha_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v"
hierarchy -top s38584t100__injalpha_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__injalpha_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injalpha_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__injalpha_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injalpha_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injalpha_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injalpha_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v"
hierarchy -top s38584t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__injalpha_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injalpha_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__injalpha_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injalpha_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injalpha_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injalpha_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v"
hierarchy -top s38584t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__injalpha_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injalpha_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__injalpha_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injalpha_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injalpha_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injalpha_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v"
hierarchy -top s38584t100__injalpha_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__injalpha_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injalpha_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__injalpha_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injalpha_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injalpha_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injalpha_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injalpha_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injalpha_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injbeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v"
hierarchy -top s38584t100__injbeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__injbeta_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injbeta_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__injbeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injbeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injbeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injbeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v"
hierarchy -top s38584t100__injbeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__injbeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injbeta_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__injbeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injbeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injbeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injbeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v"
hierarchy -top s38584t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__injbeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injbeta_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__injbeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injbeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injbeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injbeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v"
hierarchy -top s38584t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__injbeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injbeta_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__injbeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injbeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injbeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injbeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v"
hierarchy -top s38584t100__injbeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__injbeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injbeta_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__injbeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injbeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injbeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injbeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injbeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injbeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injdelta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v"
hierarchy -top s38584t100__injdelta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__injdelta_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injdelta_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__injdelta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injdelta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injdelta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injdelta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v"
hierarchy -top s38584t100__injdelta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__injdelta_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injdelta_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__injdelta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injdelta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injdelta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injdelta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v"
hierarchy -top s38584t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__injdelta_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injdelta_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__injdelta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injdelta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injdelta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injdelta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v"
hierarchy -top s38584t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__injdelta_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injdelta_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__injdelta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injdelta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injdelta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injdelta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v"
hierarchy -top s38584t100__injdelta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__injdelta_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injdelta_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__injdelta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injdelta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injdelta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injdelta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injdelta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injdelta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injepsilon_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v"
hierarchy -top s38584t100__injepsilon_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__injepsilon_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injepsilon_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__injepsilon_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injepsilon_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injepsilon_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injepsilon_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v"
hierarchy -top s38584t100__injepsilon_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__injepsilon_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injepsilon_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__injepsilon_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injepsilon_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injepsilon_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injepsilon_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v"
hierarchy -top s38584t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__injepsilon_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injepsilon_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__injepsilon_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injepsilon_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injepsilon_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injepsilon_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v"
hierarchy -top s38584t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__injepsilon_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injepsilon_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__injepsilon_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injepsilon_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injepsilon_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injepsilon_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v"
hierarchy -top s38584t100__injepsilon_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__injepsilon_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injepsilon_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__injepsilon_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injepsilon_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injepsilon_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injepsilon_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injepsilon_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injepsilon_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injgamma_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v"
hierarchy -top s38584t100__injgamma_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__injgamma_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injgamma_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__injgamma_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injgamma_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injgamma_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injgamma_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v"
hierarchy -top s38584t100__injgamma_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__injgamma_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injgamma_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__injgamma_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injgamma_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injgamma_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injgamma_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v"
hierarchy -top s38584t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__injgamma_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injgamma_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__injgamma_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injgamma_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injgamma_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injgamma_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v"
hierarchy -top s38584t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__injgamma_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injgamma_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__injgamma_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injgamma_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injgamma_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injgamma_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v"
hierarchy -top s38584t100__injgamma_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__injgamma_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injgamma_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__injgamma_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injgamma_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injgamma_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injgamma_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injgamma_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injgamma_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injzeta_d1_s42__ys_id.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v"
hierarchy -top s38584t100__injzeta_d1_s42
proc
opt -full
flatten
opt_clean
rename -top s38584t100__injzeta_d1_s42__ys_id
write_verilog -noattr $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_id.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injzeta_d1_s42__ys_id.ys -l $OUT/logs/s38584t100__injzeta_d1_s42__ys_id.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_id.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_id.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_id.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_id.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_id.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_id.log > $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_id.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_id.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injzeta_d1_s42,id,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injzeta_d1_s42 id] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injzeta_d1_s42__ys_opt.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v"
hierarchy -top s38584t100__injzeta_d1_s42
proc
opt -full
flatten
opt -full
opt_clean
rename -top s38584t100__injzeta_d1_s42__ys_opt
write_verilog -noattr $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_opt.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injzeta_d1_s42__ys_opt.ys -l $OUT/logs/s38584t100__injzeta_d1_s42__ys_opt.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_opt.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_opt.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_opt.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_opt.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_opt.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_opt.log > $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_opt.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_opt.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injzeta_d1_s42,opt,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injzeta_d1_s42 opt] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injzeta_d1_s42__ys_abc.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v"
hierarchy -top s38584t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g AND,OR,XOR,XNOR,MUX
opt_clean
rename -top s38584t100__injzeta_d1_s42__ys_abc
write_verilog -noattr $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_abc.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injzeta_d1_s42__ys_abc.ys -l $OUT/logs/s38584t100__injzeta_d1_s42__ys_abc.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_abc.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_abc.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_abc.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_abc.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_abc.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_abc.log > $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_abc.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_abc.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injzeta_d1_s42,abc,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injzeta_d1_s42 abc] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injzeta_d1_s42__ys_aig.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v"
hierarchy -top s38584t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
aigmap
opt_clean
opt_clean
rename -top s38584t100__injzeta_d1_s42__ys_aig
write_verilog -noattr $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_aig.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injzeta_d1_s42__ys_aig.ys -l $OUT/logs/s38584t100__injzeta_d1_s42__ys_aig.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_aig.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_aig.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_aig.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_aig.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_aig.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_aig.log > $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_aig.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_aig.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injzeta_d1_s42,aig,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injzeta_d1_s42 aig] rc=$rc cec=$cec secs=$secs"
mkdir -p $OUT/s38584t100
cat > /tmp/ys_s38584t100__injzeta_d1_s42__ys_nand.ys <<YSEOF
read_verilog -sv $V/verilog_lib.v
read_verilog -sv "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v"
hierarchy -top s38584t100__injzeta_d1_s42
proc
opt -full
flatten
techmap
opt -full
abc -g NAND,NOR
opt_clean
rename -top s38584t100__injzeta_d1_s42__ys_nand
write_verilog -noattr $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_nand.v
YSEOF
t0=$(date +%s)
timeout 900 yosys -q -s /tmp/ys_s38584t100__injzeta_d1_s42__ys_nand.ys -l $OUT/logs/s38584t100__injzeta_d1_s42__ys_nand.log > /dev/null 2>&1
rc=$?; t1=$(date +%s); secs=$((t1-t0))
if [ -f $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_nand.v ]; then bytes=$(wc -c < $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_nand.v); alw=$(grep -c always $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_nand.v); cells=$(grep -cE "^  [A-Za-z_\\][A-Za-z0-9_\\]* " $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_nand.v); else bytes=0; alw=0; cells=0; fi
cd "${EQGUARD_ROOT}"
python3 generate_trans/cec/direct_cec.py --golden "${EQGUARD_ROOT}/generate_trans/hosts_bt/s38584t100/s38584t100__injzeta_d1_s42.v" --candidate $OUT/s38584t100/s38584t100__injzeta_d1_s42__ys_nand.v --vali-dir $V --timeout 900 --log $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_nand.log > $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_nand.txt 2>&1
cec=$(grep -a "CEC" $OUT/logs/cec_s38584t100__injzeta_d1_s42__ys_nand.txt | tail -1 | sed "s/,/;/g")
echo "s38584t100,trojan,s38584t100__injzeta_d1_s42,nand,$rc,$bytes,$alw,$cells,$cec,$secs" >> $OUT/ys_manifest.csv
echo "[s38584t100 s38584t100__injzeta_d1_s42 nand] rc=$rc cec=$cec secs=$secs"
