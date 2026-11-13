"""Wait for all extraction schedulers before the original completion audit."""
import argparse
import runpy
import sys
from pathlib import Path
from finish_fullrun import wait_for_process

p=argparse.ArgumentParser();p.add_argument('--primary',type=int,required=True)
p.add_argument('--pool',type=int,required=True);p.add_argument('--tail',type=int)
a=p.parse_args()
for pid in (a.primary,a.pool,a.tail):
    if pid:
        print('Waiting for extraction scheduler',pid,flush=True)
        wait_for_process(pid)
print('All extraction schedulers exited; original retry/merge/audit follows',flush=True)
sys.argv=['finish_fullrun.py','--pid',str(a.primary)]
runpy.run_path(str(Path(__file__).with_name('finish_fullrun.py')),run_name='__main__')
