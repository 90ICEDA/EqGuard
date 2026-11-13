#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
set +e
cd "${EQGUARD_ROOT}"
yosys -q -s "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__injalpha_d1_s42__ys_rt.ys" -l "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__injalpha_d1_s42__ys_rt.log"
yosys -q -s "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__injalpha_d1_s42__ys_abc.ys" -l "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__injalpha_d1_s42__ys_abc.log"
yosys -q -s "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__injalpha_d1_s42__ys_aig.ys" -l "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__injalpha_d1_s42__ys_aig.log"
yosys -q -s "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__ctlmatcha_d1_s42__ys_rt.ys" -l "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__ctlmatcha_d1_s42__ys_rt.log"
yosys -q -s "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__ctlmatcha_d1_s42__ys_abc.ys" -l "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__ctlmatcha_d1_s42__ys_abc.log"
yosys -q -s "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__ctlmatcha_d1_s42__ys_aig.ys" -l "${EQGUARD_ROOT}/generate_trans/stamp/logs/rs232t1000__ctlmatcha_d1_s42__ys_aig.log"
