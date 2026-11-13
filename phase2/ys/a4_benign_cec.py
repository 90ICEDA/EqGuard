# -*- coding: utf-8 -*-
"""a4_benign_cec.py —— A4：对 **clean base** 做 CEC，形式验证「良性」。

期望：trojan → FAIL ✓（功能被改）；ctldead / ctlequiv → PASS ✓（等价 ✓）。
产物：10.15/01_数据与标签/A4_对照样本/tables/a4_benign_cec.csv
用法：py phase2/ys/a4_benign_cec.py --host rs232t1000
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CUR))
from phase2.ys.keep_ablation import WSL_ROOT, VALI_WSL, wsl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--root", type=Path, default=ROOT / "generate_trans" / "hosts_a4")
    ap.add_argument("--tables", type=Path,
                    default=ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "tables")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    hdir = a.root / a.host
    recs = json.loads((hdir / "provenance.json").read_text(encoding="utf-8"))
    base = hdir / "base" / f"{a.host}_clean.v"
    logs = a.tables.parent / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    sh = ["#!/bin/bash", "set +e", f"cd {WSL_ROOT}"]
    for r in recs:
        v = hdir / f"{r['view']}.v"
        out = logs / f"benign_{r['view']}.txt"
        sh.append(f"python3 generate_trans/cec/direct_cec.py --golden {wsl(base)} "
                  f"--candidate {wsl(v)} --vali-dir {VALI_WSL} --timeout {a.timeout} "
                  f"--log {wsl(logs / ('benign_' + r['view'] + '.log'))} > {wsl(out)} 2>&1")
    gen = logs / "_benign_cec.sh"
    gen.write_text("\n".join(sh) + "\n", encoding="utf-8", newline="\n")
    subprocess.run(["wsl", "-e", "bash", "-c", f"sed 's/\r$//' {wsl(gen)} | bash"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")

    rows = []
    for r in recs:
        t = (logs / f"benign_{r['view']}.txt")
        txt = t.read_text(encoding="utf-8", errors="replace") if t.exists() else ""
        m = re.search(r"(PASS|FAIL|ERROR|TIMEOUT)", txt, re.I)
        rows.append({"host": a.host, "view": r["view"], "a4_family": r.get("a4_family"),
                     "kind": r["kind"], "cec_vs_clean": (m.group(1).upper() if m else "?"),
                     "expected": ("FAIL" if r["kind"] == "trojan" else "PASS")})
    import pandas as pd
    d = pd.DataFrame(rows)
    d["ok"] = d.cec_vs_clean == d.expected
    a.tables.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.tables / f"a4_benign_cec_{a.host}.csv", index=False, encoding="utf-8-sig")
    parts = [pd.read_csv(f) for f in sorted(a.tables.glob("a4_benign_cec_*.csv"))]
    if parts:
        pd.concat(parts, ignore_index=True).drop_duplicates(
            subset=["host", "view"]).to_csv(a.tables / "a4_benign_cec.csv",
                                             index=False, encoding="utf-8-sig")
    print(d.to_string(index=False))

    # 回写 provenance：`label_usable = 0` = 「木马」实际上等价于 clean base ✗（假木马 ✓ 训练时应过滤 ✓）
    allr = pd.read_csv(a.tables / "a4_benign_cec.csv")
    for hp in sorted(a.root.glob("*/provenance.json")):
        recs2 = json.loads(hp.read_text(encoding="utf-8"))
        ch = 0
        for r2 in recs2:
            hit = allr[allr.view == r2["view"]]
            if hit.empty:
                continue
            row0 = hit.iloc[0]
            if r2.get("cec_benign") != str(row0.cec_vs_clean) or r2.get("label_usable") != int(bool(row0.ok)):
                r2["cec_benign"] = str(row0.cec_vs_clean)
                r2["label_usable"] = int(bool(row0.ok))
                ch += 1
        if ch:
            hp.write_text(json.dumps(recs2, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[provenance] {hp.parent.name}: 更新 {ch} 条（cec_benign / label_usable ✓）")
    print(f"\n[OK] {int(d.ok.sum())}/{len(d)} 符合预期；→ {a.tables / 'a4_benign_cec.csv'}")
    return 0 if d.ok.all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
