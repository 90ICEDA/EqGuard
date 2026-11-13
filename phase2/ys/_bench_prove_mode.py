"""_bench_prove_mode.py —— 证明步骤 A/B 基准（`equiv_simple` vs `+ equiv_induct`）。

同一批候选（默认 s38417/injalpha `abc:aig` 前 300 对 ✓），分别用两种步骤跑，
输出 **proved 数 / 墙钟 / pair per second** ✓ —— 只用于选参数，不写主表 ✓。

用法：
    ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/_bench_prove_mode.py [--pairs 300] [--batch 200]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sat_node_pairs_batch as SB      # noqa: E402
import sat_sweep_pairs as SW           # noqa: E402

VDIR = Path(SW.ROOT) / "generate_trans/folds/hosts_bt31/trans"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="s38417t100")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--ra", default="ys_abc")
    ap.add_argument("--rb", default="ys_aig")
    ap.add_argument("--pairs", type=int, default=300)
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    va = VDIR / f"{a.host}__{a.inst}_d1_s42__{a.ra}.v"
    vb = VDIR / f"{a.host}__{a.inst}_d1_s42__{a.rb}.v"
    if not (va.exists() and vb.exists()):
        raise SystemExit(f"[ERROR] 缺视图 {va} / {vb}")
    topA, modA, nA = SW.load_json(SB.struct_iso(va))
    topB, modB, nB = SW.load_json(SB.struct_iso(vb))
    sigA, mask = SW.simulate_seq(modA, nA, 32, 42, 8)
    sigB, _ = SW.simulate_seq(modB, nB, 32, 42, 8)
    cand = SB.candidates(modA, nA, modB, nB, sigA, sigB, mask, va, vb,
                         "all", a.pairs, 20, 42)
    print(f"[in] {a.ra}:{a.rb} 候选 {len(cand)}｜batch={a.batch}")

    modes = (
        ("full(simple+induct)", ["equiv_simple -undef", "equiv_induct -undef -seq 4"]),
        ("simple_only", ["equiv_simple -undef"]),
    )
    for name, steps in modes:
        SB.PROVE_STEPS = list(steps)
        t0 = time.time()
        ok = amb = 0
        for bi in range(0, len(cand), a.batch):
            blk = cand[bi: bi + a.batch]
            st, _wall, _lp = SB.prove_batch(f"bench_{name}_{bi // a.batch}",
                                            va, vb, topA, topB, blk, a.timeout)
            ok += sum(1 for v in st.values() if v == "proved")
            amb += sum(1 for v in st.values() if v == "unknown")
        dt = max(1e-6, time.time() - t0)
        print(f"  {name:22s} proved {ok:4d}/{len(cand)}｜unknown {amb:3d}"
              f"｜{dt:6.1f}s｜{len(cand)/dt:6.1f} pair/s｜{ok/dt:6.1f} proved/s")
    SB.PROVE_STEPS = ["equiv_simple -undef", "equiv_induct -undef -seq 4"]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
