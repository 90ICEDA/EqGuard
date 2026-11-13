#!/bin/bash
set +e
cd /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_abc.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_abc.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_abc.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_abc.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_abc.secs
echo "[rs232t1000__injalpha_d1_s42__keepnone__ys_abc] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_abc.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_abc.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_abc.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_abc.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_abc.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_abc.secs
echo "[rs232t1000__injalpha_d1_s42__keepcur__ys_abc] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_abc.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_aig.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_aig.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_aig.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_aig.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_aig.secs
echo "[rs232t1000__injalpha_d1_s42__keepnone__ys_aig] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_aig.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_aig.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_aig.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_aig.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_aig.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_aig.secs
echo "[rs232t1000__injalpha_d1_s42__keepcur__ys_aig] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_aig.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_nand.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_nand.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_nand.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_nand.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_nand.secs
echo "[rs232t1000__injalpha_d1_s42__keepnone__ys_nand] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepnone__ys_nand.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_nand.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_nand.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_nand.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_nand.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_nand.secs
echo "[rs232t1000__injalpha_d1_s42__keepcur__ys_nand] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injalpha_d1_s42__keepcur__ys_nand.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_abc.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_abc.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_abc.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_abc.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_abc.secs
echo "[rs232t1000__injdelta_d1_s42__keepnone__ys_abc] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_abc.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_abc.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_abc.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_abc.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_abc.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_abc.secs
echo "[rs232t1000__injdelta_d1_s42__keepcur__ys_abc] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_abc.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_aig.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_aig.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_aig.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_aig.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_aig.secs
echo "[rs232t1000__injdelta_d1_s42__keepnone__ys_aig] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_aig.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_aig.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_aig.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_aig.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_aig.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_aig.secs
echo "[rs232t1000__injdelta_d1_s42__keepcur__ys_aig] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_aig.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_nand.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_nand.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_nand.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_nand.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_nand.secs
echo "[rs232t1000__injdelta_d1_s42__keepnone__ys_nand] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepnone__ys_nand.rc) secs=$((t1-t0))"
t0=$(date +%s)
timeout 900 yosys -q -s /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_nand.ys -l /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_nand.log > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_nand.stdout 2>&1
echo $? > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_nand.rc
t1=$(date +%s); echo $((t1-t0)) > /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_nand.secs
echo "[rs232t1000__injdelta_d1_s42__keepcur__ys_nand] yosys_rc=$(cat /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/keepab_panel_stage1/logs/rs232t1000__injdelta_d1_s42__keepcur__ys_nand.rc) secs=$((t1-t0))"
