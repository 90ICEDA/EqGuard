"""Run one view of the k=6 s15850 panel extraction in a separate process."""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
view = sys.argv[1]
os.environ['SAT_T'] = str(ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_s15850_round26/views' / view)
runpy.run_path(str(Path(__file__).with_name('extract_s15850_k6.py')), run_name='__main__')
