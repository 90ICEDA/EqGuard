
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import subprocess, pathlib, sys
out = pathlib.Path(_eqguard_path('_p0pilot/sat_coverage_handoff_20261030/probe_py.txt'))
p = subprocess.run(['wsl', '-e', 'bash', '-lc', 'yosys -V; date -Is'], capture_output=True, text=True)
out.write_text(f'rc={p.returncode}\nstdout={p.stdout}\nstderr={p.stderr}\nexe={sys.executable}\n', encoding='utf-8')
