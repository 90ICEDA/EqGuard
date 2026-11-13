"""Independent simulation replay of the 12 refuted witnesses (no SAT)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
T13 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round13"
WSL = _eqguard_path('', wsl=True)


def main() -> int:
    q = pd.read_csv(T12 / "queries.csv", encoding="utf-8-sig")
    rows = []
    for i, r in enumerate(q[q.status == "refuted"].itertuples()):
        folder = ROOT / r.folder
        mj = json.loads((folder / "0.model.json").read_text(encoding="utf-8"))
        sig = {s["name"]: s for s in mj["signal"]}
        env = "".join(sig["env"].get("data", []))
        target = "delta_inv" if r.kind == "polarity_check" else "delta"
        data = "".join(sig[target].get("data", [])).replace("x", "0").replace("z", "0")
        bit = int(r.args.split("[")[1].split("]")[0])
        width = len(env)
        tb = T13 / "replay" / f"{i:02d}"
        tb.mkdir(parents=True, exist_ok=True)
        if target == "delta_inv":
            decl = "wire [4:0] delta; wire [4:0] delta_inv; wire observation_diff;\ncheck u(env,delta,delta_inv,observation_diff);"
            disp = '$display("RESULT %b", delta_inv);'
        else:
            decl = "wire [4:0] delta; wire observation_diff;\ncheck u(env,delta,observation_diff);"
            disp = '$display("RESULT %b", delta);'
        (tb / "tb.v").write_text(f"""module tb;
reg [{width-1}:0] env;
{decl}
initial begin
  env = {width}'b{env};
  #1; {disp} $finish;
end
endmodule
""", encoding="utf-8")
        model = folder / "model.v"
        model_rel = str(r.folder).replace("\\", "/")
        cmd = (f'cd "{WSL}/10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round13/replay/{i:02d}" '
               f'&& iverilog -g2012 -o sim tb.v "{WSL}/{model_rel}/model.v" && vvp sim')
        p = subprocess.run(["wsl", "-e", "bash", "-lc", cmd], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=180)
        m = re.search(r"RESULT ([01]+)", p.stdout or "")
        sim = m.group(1) if m else ""
        # $display prints MSB first; bit j is at len-1-j.
        got = None
        if sim and len(sim) > bit:
            got = int(sim[len(sim) - 1 - bit])
        rows.append(dict(folder=r.folder, kind=r.kind, target=target, bit=bit,
                         witness=f"{r.folder}/0.model.json", env_sha=hashlib.sha256(
                             env.encode()).hexdigest(), model_sha=r.model_sha,
                         expected=1, simulated=got,
                         pass_=int(got == 1), sim_output=sim,
                         stderr=(p.stderr or "")[-200:]))
    out = pd.DataFrame(rows)
    out.to_csv(T13 / "replay_refutations.csv", index=False, encoding="utf-8-sig")
    info = dict(refuted=len(out), simulated_pass=int(out.pass_.sum()),
                failed=int((1 - out.pass_).sum()), note="iverilog/vvp simulation, no SAT")
    (T13 / "replay_refutations_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())