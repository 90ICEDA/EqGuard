# -*- coding: utf-8 -*-
"""_gen_cec_tolib.py —— 为"转换回库单元"的 yosys 变体生成 CEC 脚本（golden=源网表）。"""

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
VALI = "/mnt/c/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali"
WSL_ROOT = _eqguard_path('', wsl=True)


def wsl(p: Path) -> str:
    s = str(Path(p).resolve()).replace("\\", "/")
    return s.replace("C:/", "/mnt/c/", 1) if s[1:3] == ":/" else s


def main() -> int:
    hosts = sys.argv[1].split(",") if len(sys.argv) > 1 else []
    man = ROOT / "generate_trans" / "yslib_test" / "convert_manifest.csv"
    d = pd.read_csv(man)
    d = d[~d.file.astype(str).str.startswith("ERROR")]
    if hosts:
        d = d[d.host.isin(hosts)]
    out_csv = "/tmp/cec_tolib.csv"
    L = ["#!/bin/bash", "set +e", f"cd {WSL_ROOT}",
         f'echo "host,recipe,stem,cec" > {out_csv}']
    for r in d.itertuples():
        g = ROOT / "generate_trans" / "hosts_bt" / r.host / f"{r.stem}.v"
        c = Path(str(r.file))
        L.append(
            f"python3 generate_trans/cec/direct_cec.py --golden {wsl(g)} "
            f"--candidate {wsl(c)} --vali-dir {VALI} --timeout 900 "
            f"--log /tmp/tolib_{r.host}_{r.recipe}.log > /tmp/o.txt 2>&1; "
            f"C=$(grep -a CEC /tmp/o.txt | tail -1 | tr -d ','); "
            f'echo "{r.host},{r.recipe},{r.stem},$C" >> {out_csv}')
    sh = ROOT / "phase2" / "ys" / "_cec_tolib.sh"
    sh.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] {len(d)} 对 → {sh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
