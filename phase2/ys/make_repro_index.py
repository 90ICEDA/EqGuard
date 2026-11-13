"""make_repro_index.py —— N5：复现包索引（`99_共用资产/repro/` ✓）。

做法 ✓（全部只读扫描 ✓）：
  · `_devcfg/*.npz`            → 分数 dump（每行一个 ✓）
  · `results/*/run_config.json` → 训练运行（tag / seed / epochs ✓）
  · `10.15/**/tables/*.csv`     → 汇总表
输出：`repro/index.csv` ✓ + `repro/env.md` ✓（环境与关键开关 ✓）。
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _probe(py: Path) -> str:
    """探测某个解释器的 torch / cuda ✓（子进程 ✓，避免 import 污染 ✗）。"""
    import subprocess

    if not py.exists():
        return f"- {py.parent.parent.name}: ✗ 不存在"
    code = ("import sys, torch;"
            "print(sys.version.split()[0], '|', torch.__version__, '|', torch.version.cuda,"
            " '|', torch.cuda.is_available(),"
            " '|', (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'n/a'))")
    try:
        out = subprocess.run([str(py), "-c", code], capture_output=True, text=True,
                             timeout=120, encoding="utf-8", errors="replace")
        s = (out.stdout or "").strip().splitlines()
        return f"- {py.parent.parent.name}: " + (s[-1] if s else "✗ 探测失败")
    except Exception as e:      # noqa: BLE001
        return f"- {py.parent.parent.name}: ✗ {e}"


def env_text() -> str:
    lines = ["# 复盘环境（自动生成 ✓）", "",
             "> **两个解释器必须区分** ⚠️：`ginvenv_gpu` 跑**训练** ✓（CUDA ✓）；`ginvenv` 跑**分析/画图** ✓（CPU ✓）。",
             "> 格式 ✓：python | torch | cuda | is_available | device", "",
             _probe(ROOT / "ginvenv_gpu" / "Scripts" / "python.exe"),
             _probe(ROOT / "ginvenv" / "Scripts" / "python.exe"),
             f"- 平台: {platform.platform()} ✓", "",
             "## 训练关键开关 ✓", "",
             "- `GNN_GRAD_CKPT=1` ✓（梯度检查点；v3.1 3.22M 节点必需 ✓）",
             "- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` ✓（防碎片 ✗）",
             "- `--extra-feats cone5` ✓ / `--label-mask trust` ✓ / `--region-loss 10 --region-mode dff` ✓",
             "- runner 里的 `$gpy` = `ginvenv_gpu\\Scripts\\python.exe` ✓（**训练必须用它** ✓，`$py` 只做汇总 ✓）",
             "- yosys 0.51 ✓（WSL ✓；`abc -script` 见 T10 ✓）", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "10.15" / "99_共用资产" / "repro")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in sorted((ROOT / "_devcfg").glob("*.npz")):
        rows.append(dict(kind="scores", id=f.stem, path=str(f.relative_to(ROOT)),
                         seed="", config="", note=f"{f.stat().st_size/1e6:.1f} MB"))
    for d in sorted((ROOT / "results").glob("*")):
        if not d.is_dir():
            continue
        cfg = d / "run_config.json"
        if not cfg.exists():
            continue
        try:
            j = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:   # noqa: BLE001
            j = {}
        rows.append(dict(kind="run", id=d.name,
                         path=str(d.relative_to(ROOT)),
                         seed=str(j.get("seed", j.get("seed_id", ""))),
                         config=str(j.get("config", "")),
                         note=f"epochs={j.get('epochs', '')}"))
    for f in sorted((ROOT / "10.15").rglob("tables/*.csv")):
        rows.append(dict(kind="table", id=f.stem, path=str(f.relative_to(ROOT)),
                         seed="", config="", note=f"{f.stat().st_size/1024:.1f} KB"))
    df = pd.DataFrame(rows)
    df.to_csv(a.out / "index.csv", index=False, encoding="utf-8-sig")
    (a.out / "env.md").write_text(env_text(), encoding="utf-8")
    print(df.groupby("kind").size().to_string())
    print(f"\n[out] {a.out / 'index.csv'}（{len(df)} 行 ✓）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
