"""Pilot run for option C: pretrain Z/R/P on the node-pair-derived cone pool (no finetune)."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FROZEN = ROOT / '_p0pilot/cec_pretrain_ready_20261105'


def main():
    execute = '--execute' in sys.argv
    for name in ('RUN_CONTRACT.json',):
        if not (HERE / name).exists():
            shutil.copy2(FROZEN / name, HERE / name)
    spec = importlib.util.spec_from_file_location('cec_frozen_engine_c', FROZEN / 'engine.py')
    eng = importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)
    eng.O = HERE
    eng.J = HERE          # cones come from this pilot directory
    print('engine ready; cones in', HERE, flush=True)
    if not execute:
        print('pass --execute to run')
        return
    for arm in ['Z', 'R', 'P']:
        eng.pretrain('main', 42, arm)
        print('pretrain done', arm, flush=True)


if __name__ == '__main__':
    main()
