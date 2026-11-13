"""dump_node_names.py —— **反推 `.pt` 的节点名（net/instance 名）** ✓（P0/P1 的 SAT 结果要贴到节点上必须这一步）。

背景 ✗：`parser2.save_domain_output()` 只把 `prefixes`（电路名）和 `file_ids`（视图名）写进
`metadata_{suffix}.json` ✓ —— **节点名没落地** ✗ → `.pt` 里没有 `node_names` ✗。
但节点顺序 = `parser2.parse_lines()` 按 `sorted(glob('*.v'))` 的**文件顺序** + 文件内**语句顺序** ✓，
所以用**同一套 parser2 函数**重放一遍（只解析 ✓ 不算特征 ✗）就能**逐行复原** ✓。

**自验证 ✓（关键）**：复原出的 `file_ids` 序列必须与 `<pt-dir>/../for_train/metadata_{suffix}.json`
里的 `file_ids` **逐元素相等** ✓ —— 相等即证明"节点 index → 名字"与 `.pt` 完全对齐 ✓；
不等则直接报错退出 ✗（绝不静默写出错位的表 ✗）。

输出（写到 `--out-dir` ✓）：
    node_names_trans.txt       每行一个名字 ✓（第 i 行 = `.pt` 的 trans 节点 i ✓）
    node_meta_trans.json       {"n": ..., "n_views": ..., "verified": true, ...}
    同名可选 `--split orig` 处理 orig 侧 ✓

用法（必须在 fold 目录下跑 ✓ 因为 parser2 用 `./trans`、`./orig` 相对路径 ✓）：
    cd generate_trans/folds/hosts_bt31
    python -X utf8 ../../../phase2/ys/dump_node_names.py --split trans
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "data" / "verilog_data"))
import parser2 as P  # noqa: E402


def parse_domain(files: list[str]):
    """复刻 `parser2.process_domain()` 的 A/B 段（读盘 + 预处理 + 解析 ✓ 不算特征 ✗）。"""
    lines = [P.readlogs(files)]                    # ← 扁平文件列表 ✓（readlogs 逐个 open ✓）
    P.getprimlist(lines)
    lines = P.fixassigns(lines)
    for split in lines:
        for l in split:
            P.clean_1(l)
            wi = P.getindices("wire", l)
            if wi:
                last = wi[-1]
                l[:] = l[last + 1:-1]
    gates, nodeslistlist, infolistlist, indexlistlist, indices = P.parse_lines(lines)
    return nodeslistlist


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["trans", "orig"], default="trans")
    ap.add_argument("--meta", type=Path, default=None,
                    help="默认 ./data/for_train/metadata_<split>.json ✓（用来逐元素校验 ✓）")
    ap.add_argument("--out-dir", type=Path, default=None, help="默认 ./data/processed ✓")
    ap.add_argument("--max-files", type=int, default=0, help=">0 时只跑前 N 个文件（自测用 ✓）")
    a = ap.parse_args()

    files = P.getverilogs("./", a.split)
    if a.max_files:
        files = files[: a.max_files]
    print(f"[in] {a.split}: {len(files)} 个 .v（cwd={os.getcwd()}）")
    if not files:
        raise SystemExit("[ERROR] 没有 .v ✗（必须在 fold 目录下跑 ✓）")

    nl = parse_domain(files)
    if len(nl) != len(files):
        raise SystemExit(f"[ERROR] parse_lines 文件数 {len(nl)} != {len(files)} ✗")

    names: list[str] = []
    file_ids: list[str] = []
    for fp, d in zip(files, nl):
        fid = os.path.basename(fp)[:-2]           # 去掉 `.v`
        for k in d.keys():
            names.append(str(k).lstrip("\\"))
            file_ids.append(fid)

    meta_p = a.meta or Path("data/for_train") / f"metadata_{a.split}.json"
    verified = False
    if meta_p.exists() and not a.max_files:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        n_meta = len(meta.get("file_ids", []))
        if len(names) != n_meta:
            raise SystemExit(f"[ERROR] 名字数 {len(names)} != metadata 节点数 {n_meta} ✗")
        bad = [i for i, (x, y) in enumerate(zip(file_ids, meta["file_ids"])) if x != y]
        if bad:
            i = bad[0]
            raise SystemExit(f"[ERROR] file_ids 对不齐 ✗ 首个不一致 i={i}: {file_ids[i]!r} vs "
                             f"{meta['file_ids'][i]!r}（共 {len(bad)} 处 ✗）")
        verified = True
        print(f"[OK] 与 {meta_p} 逐元素一致 ✓（{n_meta} 个节点 / "
              f"{len(set(file_ids))} 个视图 ✓）")
    else:
        print(f"[WARN] 跳过校验（meta 不存在或用了 --max-files）⚠️：{meta_p}")

    out = a.out_dir or Path("data/processed")
    out.mkdir(parents=True, exist_ok=True)
    txt = out / f"node_names_{a.split}.txt"
    txt.write_text("\n".join(names), encoding="utf-8")
    (out / f"node_meta_{a.split}.json").write_text(json.dumps({
        "split": a.split, "n": len(names), "n_views": len(set(file_ids)),
        "verified_against": str(meta_p) if verified else None,
        "verified": verified, "files": len(files),
        "note": "第 i 行 = trans/orig 图节点 i 的名字（与 .pt 的 file_ids 逐元素校验 ✓）",
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[out] {txt}（{len(names)} 行 ✓）")
    for k in list({f for f in file_ids})[:3]:
        idx = file_ids.index(k)
        print(f"   {k}: i={idx} → {names[idx]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
