"""Console-interrupt-isolated runner; existing STOP/resource guards still apply."""
import os,sys,signal,runpy,ctypes
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
signal.signal(signal.SIGINT,signal.SIG_IGN)
if hasattr(signal,'SIGBREAK'):signal.signal(signal.SIGBREAK,signal.SIG_IGN)
ctypes.windll.kernel32.SetConsoleCtrlHandler(None,True)
script=sys.argv[1];sys.argv=sys.argv[1:];sys.path.insert(0,os.path.dirname(script))
runpy.run_path(script,run_name='__main__')
