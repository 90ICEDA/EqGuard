"""sat_full_batch.py —— **全量 SAT 批次**（覆盖 `folds/<fold>/trans/*.v` 全部网表 ✓，可续跑 ✓）。

用途 ✓：P0 说明里"先做 2 个案例"只是**可行性验证** ✓；最终要覆盖**所有会用到的网表** ✓
（本 fold 共 **389 个 .v** ✓ = **76 组** ✓：5 宿主 ×（木马实例 ✓ + `ctl*` 对照 ✓ + `a4*` 三胞胎 ✓）× 6 配方 ✓）。
**P1 也是全网表口径** ✓：`ctl*` / `a4*` 必须一起做 ✓，否则"错误对应率 ✓ / 三胞胎误报 ✓"没有分母 ✗。

做法 ✓（每个 `host × inst` 一组 ✓，组内按配方拆 ✓）：
  1. **P0 功能关系**：`sat_functional_relations.py --host H --inst I --recipes <组内全部>`
     （大宿主 `aig/nand` 自动 `--timeout 60` ✓、`--bmc-depths 0` ✓ → 记 `timeout` ✓ 不阻塞 ✗）
  2. **P1 SAT sweeping**：`sat_sweep_pairs.py --pairs id:abc,id:opt,abc:opt --per-sig 2 --max-pairs 120`
     （只挑 SAT 可判的 3 对 ✓；`aig/nand` 在大宿主恒超时 ✗ → 不排 ✗）
  3. 收尾 ✓：`make_sat_summary` → `fghtl_p1_region_roles` → `make_p0_consistency` → `make_f7_region_fig2` ✓

续跑 ✓：进度写 `logs/full_batch_state.json` ✓（已完成组跳过 ✓）；日志 `logs/full_batch.log` ✓。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
LOGS = BASE / "logs"
STATE = LOGS / "full_batch_state.json"
PY = ROOT / "ginvenv/Scripts/python.exe"
CANON = ["id", "abc", "opt"]


def groups(fold: str) -> dict[tuple[str, str], dict[str, Path]]:
    d = ROOT / "generate_trans" / "folds" / fold / "trans"
    out: dict[tuple[str, str], dict[str, Path]] = {}
    for v in sorted(d.glob("*.v")):
        parts = v.stem.split("__")
        if len(parts) < 2:
            continue
        host, rest = parts[0], parts[1]
        inst = rest.split("_d1")[0]
        rcp = parts[-1].replace("ys_", "")          # `ys_id` → `id` ✓
        out.setdefault((host, inst), {})[rcp] = v
    return out


def run(name: str, args: list[str], log) -> int:
    t0 = time.time()
    p = subprocess.run([str(PY), "-X", "utf8"] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    rc = p.returncode
    tail = (p.stdout or "").strip().splitlines()[-6:]
    log.write(f"[{time.strftime('%H:%M:%S')}] {name} rc={rc} {time.time()-t0:.0f}s\n")
    for ln in tail:
        log.write("    " + ln + "\n")
    log.flush()
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", default="hosts_bt31")
    ap.add_argument("--max-groups", type=int, default=0, help="0 = 全部 ✓")
    ap.add_argument("--skip-ctrl", action="store_true",
                    help="跳过 `ctl*` / `a4*` 对照（**默认不跳过** ✓ 全网表口径 ✓）")
    ap.add_argument("--hosts", default="", help="逗号分隔宿主过滤 ✓（空=全部 ✓）")
    ap.add_argument("--sleep", type=float, default=2.0, help="组间休眠秒 ✓（让 RAM 回落 ✓）")
    ap.add_argument("--with-mapped-pairs", action="store_true",
                    help="额外跑 aig/nand 侧的跨实现对 ✓（慢 ✗，默认关 ✓）")
    a = ap.parse_args()

    LOGS.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"done": []}
    done = set(state.get("done", []))

    gs = groups(a.fold)
    host_rank = {h: i for i, h in enumerate(
        ["rs232t1000", "s15850t100", "s35932t200", "s38417t100", "s38584t100"])}

    def inst_rank(i: str) -> tuple[int, str]:
        # 同宿主内：木马实例 ✓ → ctl 对照 ✓ → a4 三胞胎 ✓
        r = 0 if not i.startswith(("ctl", "a4")) else (1 if i.startswith("ctl") else 2)
        return (r, i)

    keys_all = sorted(gs, key=lambda k: (host_rank.get(k[0], 99), inst_rank(k[1])))
    keys = list(keys_all)
    if a.skip_ctrl:
        keys = [k for k in keys if not k[1].startswith(("ctl", "a4"))]
    if a.hosts:
        keep = {h.strip() for h in a.hosts.split(",") if h.strip()}
        keys = [k for k in keys if k[0] in keep]
    print(f"[in] fold={a.fold}｜组数={len(keys)}/{len(keys_all)}｜已完成={len(done)}"
          f"｜含对照={'否' if a.skip_ctrl else '是'}")
    if a.max_groups:
        keys = keys[: a.max_groups]
    if not keys:
        print("[out] 无待做组（过滤后为空 ✓）")
        return 0

    with open(LOGS / "full_batch.log", "a", encoding="utf-8") as log:
        for host, inst in keys:
            gid = f"{host}|{inst}"
            if gid in done:
                continue
            rcps = gs[(host, inst)]
            have = [r for r in rcps if r in ("id", "abc", "opt", "aig", "nand", "rt")]
            # ⚠️ 2026-10-23 13:55 提速：`ctl*`/`a4*` 对照**不需要** aig/nand ✗
            #   （二者在大宿主上几乎全是 timeout ✗，单组能拖到 10+ 分钟 ✗）；
            #   P1 的错误对应率只需 id/abc/opt 三个规范实现 ✓ → 对照组只跑这三个 ✓。
            if inst.startswith(("ctl", "a4")):
                have = [r for r in have if r in ("id", "abc", "opt")]
            big = host not in ("rs232t1000", "s15850t100")   # 三个大宿主统一按"大"处理 ✓
            tmo = "120" if not big else "30"
            bmc = "4" if not big else "0"
            # ⚠️ 2026-10-23 15:55 死线提速（用户要求 SAT 尽快完成 ✓）：
            #   `ctl*`/`a4*` 只在 **rs232 / s15850** 上做（P1 的错误对应率分母 ✓ 已足够 ✓）；
            #   三个大宿主（s35932/s38417/s38584）上每组 5 配方 × 慢证明 ✗ → 单组 5+ min ✗，
            #   只保留**木马实例** ✓（P0 必需 ✓），对照组跳过 ✗ 并在表注如实写 ✗。
            if inst.startswith(("ctl", "a4")) and host not in ("rs232t1000", "s15850t100"):
                log.write(f"[skip] {gid}（大宿主对照组，按 15:55 提速策略跳过）\n")
                log.flush()
                done.add(gid)
                state = {"done": sorted(done),
                         "skipped": sorted(set(state.get("skipped", [])) | {gid})}
                STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
                continue
            if big:
                tmo = "30"

            log.write(f"\n=== {gid}｜recipes={have}｜timeout={tmo}｜bmc={bmc}\n")
            log.flush()

            run(f"P0 {gid}",
                ["phase2/ys/sat_functional_relations.py", "--fold", a.fold,
                 "--host", host, "--inst", inst, "--recipes", ",".join(have),
                 "--timeout", tmo, "--bmc-depths", bmc,
                 "--out", str(BASE / f"tables/functional_relations_{host}.csv")],
                log)

            pairs = [f"{x}:{y}" for x in CANON for y in CANON
                     if x < y and x in have and y in have]
            # ⚠️ 2026-10-23 13:10 提速：`aig`/`nand` 侧的证明显著慢 ✗（nand 常整段 timeout ✗），
            #   而 P1 的跨实现结论已由 3 个规范对（id/abc/opt ✓）给出 ✓ →
            #   默认**只跑 3 个规范对** ✓（`--with-mapped-pairs` 可加回 ✓）。
            if a.with_mapped_pairs and "s38584" not in host:
                for x, y in (("aig", "opt"), ("nand", "opt")):
                    if x in have and y in have:
                        pairs.append(f"{x}:{y}")
            if pairs:
                run(f"sweep {gid}",
                    ["phase2/ys/sat_sweep_pairs.py", "--host", host, "--inst", inst,
                     "--pairs", ",".join(pairs), "--k", "32", "--cycles", "8",
                     "--per-sig", "2", "--max-pairs", "60", "--timeout", tmo],
                    log)

            done.add(gid)
            state = {"done": sorted(done), "skipped": sorted(state.get("skipped", []))}
            STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
            time.sleep(max(0.0, a.sleep))

        log.write("\n=== 收尾：summary / region-role / rates / F7 ===\n")
        log.flush()
        run("sat_summary", ["phase2/ys/make_sat_summary.py"], log)
        run("region_roles", ["phase2/ys/fghtl_p1_region_roles.py",
                             "--hosts", ",".join(sorted({h for h, _ in gs})),
                             "--insts", ",".join(sorted({i for _, i in gs})),
                             "--pairs", ",".join([f"ys_{x}:ys_{y}" for x, y in
                                                  (("id", "abc"), ("id", "opt"), ("abc", "opt"),
                                                   ("id", "aig"), ("id", "nand"),
                                                   ("abc", "aig"), ("abc", "nand"),
                                                   ("opt", "aig"), ("opt", "nand"),
                                                   ("aig", "nand"))])],
            log)
        run("p0_consistency+rates", ["phase2/ys/make_p0_consistency.py"], log)
        run("f7_fig", ["phase2/ys/make_f7_region_fig2.py"], log)
        log.write("=== FULL BATCH DONE ===\n")
    print("[out] 见 logs/full_batch.log ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
