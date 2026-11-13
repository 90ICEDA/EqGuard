"""Transparent NTFS compression for SAT text evidence; file bytes unchanged."""
import argparse,ctypes,json,sys,os,time
from pathlib import Path
S=Path(__file__).resolve().parent.parent/'round27_20261027';sys.path.insert(0,str(S));import k4_runtime as R
K=ctypes.WinDLL('kernel32',use_last_error=True)
K.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p];K.CreateFileW.restype=ctypes.c_void_p
K.DeviceIoControl.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.c_void_p];K.DeviceIoControl.restype=ctypes.c_int
K.CloseHandle.argtypes=[ctypes.c_void_p];K.GetCompressedFileSizeW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)];K.GetCompressedFileSizeW.restype=ctypes.c_ulong
K.GetFileAttributesW.argtypes=[ctypes.c_wchar_p];K.GetFileAttributesW.restype=ctypes.c_ulong
def longpath(p):return '\\\\?\\'+str(Path(p).absolute())
def allocated(p):
    high=ctypes.c_ulong();ctypes.set_last_error(0);low=K.GetCompressedFileSizeW(longpath(p),ctypes.byref(high))
    if low==0xffffffff and ctypes.get_last_error():raise ctypes.WinError(ctypes.get_last_error())
    return low+(high.value<<32)
def compress(p):
    p=Path(p);name=longpath(p)
    if K.GetFileAttributesW(name)&0x800:return False
    h=K.CreateFileW(name,0xc0000000,7,None,3,0x02000000,None)
    if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        mode=ctypes.c_ushort(1);n=ctypes.c_ulong()
        if not K.DeviceIoControl(h,0x9c040,ctypes.byref(mode),2,None,0,ctypes.byref(n),None):raise ctypes.WinError(ctypes.get_last_error())
    finally:K.CloseHandle(h)
    return True

def sample():
    out=R.fresh_dir(Path(__file__).parent/'compression_reviews','review');folder=R.PANEL/'views/s35932t200__ctldup_d1_s42__ys_aig/queries/s35932t200__ctldup_d1_s42__ys_aig/09536';attempt=next(folder.glob('attempt_*/results.json')).parent
    rows=[]
    for name in ['model.v','run.log','results.json']:
        p=attempt/name;before=allocated(p);digest=R.sha(p);t=time.perf_counter();changed=compress(p);elapsed=time.perf_counter()-t;after=allocated(p);assert R.sha(p)==digest
        rows.append(dict(path=str(p.relative_to(R.ROOT)),logical_bytes=p.stat().st_size,before_allocated=before,after_allocated=after,changed=changed,seconds=elapsed,sha_unchanged=True))
    R.write_new(out/'sample.json',dict(files=rows,new_sat_queries=0));print(json.dumps(dict(report=str(out),files=rows),ensure_ascii=False))

def prepare_directories():
    panels=[R.PANEL,R.TABLES/'sat_k4_validation_round29',R.TABLES/'sat_k4_test_round29']
    marked=[]
    for panel in panels:
        if not panel.exists():continue
        if compress(panel):marked.append(str(panel))
        paths=[panel/'views']+list((panel/'views').iterdir())
        for folder in paths:
            if folder.is_dir():
                if compress(folder):marked.append(str(folder))
        # Existing per-view query parent directories must also pass inheritance
        # on to new batch and attempt directories.
        for folder in (panel/'views').iterdir():
            for p in [folder/'structures',folder/'queries',folder/'queries'/folder.name]:
                if p.exists() and compress(p):marked.append(str(p))
    return marked

def backfill(out):
    # Process only completed, immutable view outputs. Skip current partial views.
    panels=[R.TABLES/'sat_k4_rs232_round23',R.TABLES/'sat_s15850_round22',R.PANEL,R.PANEL/'train_controls_complement']
    rows=[];fail=[];before=after=0;count=0
    for panel in panels:
        for view in sorted((panel/'views').iterdir()):
            if not (view/'coverage.json').exists():continue
            for root,dirs,files in os.walk(view):
                for name in files:
                    p=Path(root)/name
                    if p.suffix not in ['.v','.ys','.log','.json'] or p.stat().st_size<16384:continue
                    try:
                        prior=allocated(p);digest=R.sha(p);changed=compress(p);now=allocated(p);assert R.sha(p)==digest
                        before+=prior;after+=now;count+=1
                        if changed:rows.append(dict(path=str(p.relative_to(R.ROOT)),logical_bytes=p.stat().st_size,before=prior,after=now,sha256=digest))
                    except Exception as e:fail.append(dict(path=str(p),error=repr(e)))
                    if count%100==0:
                        (out/'progress.json').write_text(json.dumps(dict(files=count,saved_gib=(before-after)/2**30,errors=len(fail))),encoding='utf-8');time.sleep(.05)
    R.write_new(out/'complete.json',dict(files=count,before_allocated=before,after_allocated=after,saved_gib=(before-after)/2**30,compressed=rows,errors=fail,file_bytes_verified=True,files_deleted=0,files_moved=0))
    print('COMPLETE',count,(before-after)/2**30,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sample',action='store_true');p.add_argument('--mark',action='store_true');p.add_argument('--backfill',type=Path);a=p.parse_args()
    if a.sample:sample()
    elif a.mark:print(json.dumps(dict(marked=prepare_directories()),ensure_ascii=False))
    elif a.backfill:backfill(a.backfill)
