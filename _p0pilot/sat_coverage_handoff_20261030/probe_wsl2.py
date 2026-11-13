
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import subprocess, pathlib, sys, shutil, os
out = pathlib.Path(_eqguard_path('_p0pilot/sat_coverage_handoff_20261030/probe_py2.txt'))
lines = [f'exe={sys.executable}', f'which={shutil.which("wsl")}', f'PATH={os.environ.get("PATH","")[:400]}']
def run(label, **kw):
    try:
        p = subprocess.run(**kw)
        lines.append(f'{label}: rc={p.returncode} stdout={p.stdout!r} stderr={p.stderr!r}')
    except Exception as e:
        lines.append(f'{label}: EXC {e!r}')
run('inherit', args=['wsl', '-e', 'bash', '-lc', 'echo hi'])
run('capture_replace', args=['wsl', '-e', 'bash', '-lc', 'echo hi'], capture_output=True)
run('explicit_exe', args=[r'C:\Windows\System32\wsl.exe', '-e', 'bash', '-lc', 'echo hi'], capture_output=True)
run('status', args=['wsl', '--status'], capture_output=True)
run('shell_true', args='wsl -e bash -lc "echo hi"', shell=True, capture_output=True)
out.write_text('\n'.join(lines), encoding='utf-8')
print('\n'.join(lines))
