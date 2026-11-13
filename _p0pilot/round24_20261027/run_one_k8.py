"""Run one view of the k=8 rs232 panel extraction in a separate process."""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
view = sys.argv[1]
os.environ['SAT_T'] = str(ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k8_rs232_round24/views' / view)
runpy.run_path(str(Path(__file__).with_name('extract_rs232_k8.py')), run_name='__main__')
