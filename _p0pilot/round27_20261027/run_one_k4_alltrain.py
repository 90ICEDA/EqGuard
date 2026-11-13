"""Run one full k4 view for the remaining s15850/s35932 train set."""
import os
import runpy
import sys
from pathlib import Path
from k4_runtime import PANEL, exclusive_lock, read_plan, validate_complete

ROOT = Path(__file__).resolve().parents[2]
view = sys.argv[1]
if view not in {v['view'] for v in read_plan(PANEL/'plan.json')['views']}:
    raise ValueError('View is not in frozen round27 plan')
os.environ['SAT_T'] = str(PANEL / 'views' / view)
with exclusive_lock(PANEL/'views'/view/'worker.lock'):
    if validate_complete(PANEL/'views'/view)[0]:
        print('Verified complete; no extraction or output changes')
    else:
        runpy.run_path(str(Path(__file__).with_name('extract_k4_alltrain.py')), run_name='__main__')
