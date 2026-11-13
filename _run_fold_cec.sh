#!/bin/bash
EQGUARD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/." && pwd -P)"
set -u
cd "${EQGUARD_ROOT}"
python3 phase2/ys/make_fold_cec_manifest.py --fold generate_trans/folds/hosts_bt3
cd generate_trans/cec
python3 matrix_cec.py --matrix-root ../folds/hosts_bt3 --cand-dir ../folds/hosts_bt3/trans \
  --orig-dir ../folds/hosts_bt3/orig --vali-dir ../../../GraphSAINT-train/vali \
  --out ../folds/hosts_bt3/cec --jobs 8 --timeout 900 --resume --log-dir ~/cec_logs_foldv3
echo CEC_RC=$?
