# -*- coding: utf-8 -*-
"""
register_into_fold.py —— 把"转换回库单元"的 yosys 变体登记成 fold 的一种改写模式。

做的事：对每个 CEC 通过的变体
  1) 把转换后的 .v 复制到 <hosts-root>/<host>/rw/<rw_view>.v
  2) 照着同一 src 已有的 mapping 抄一份 schema，写 <host>/rw_mappings/<rw_view>.json
     （节点级对齐我们没有，所以那部分留空；但 src_verilog 必须写，fold 靠它建血缘）
  3) 往 <hosts-root>/rewrite_variants.csv 追加一行，mode 用 ys_<recipe>

这样 build_hosts_fold.py 就会把这些变体当成普通改写，一并建进 orig_view_map 与标签传输。
注意：角色划分随后要用 make_group_split.py 重做，因为 fold 自己只认 rwbubble/rwdecomp3 那两档。

用法：
    py phase2/ys/register_into_fold.py --hosts-root generate_trans/hosts_bt \
        --cec generate_trans/yslib_test/cec_tolib.csv
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))


def parse_args():
    ap = argparse.ArgumentParser(description="把 yosys 变体登记进 hosts-root，好让 fold 建进去")
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--cec", type=Path,
                    default=ROOT / "generate_trans" / "yslib_test" / "cec_tolib.csv")
    ap.add_argument("--converted", type=Path,
                    default=ROOT / "generate_trans" / "yslib_test")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def main() -> int:
    a = parse_args()
    H = a.hosts_root.resolve()
    cec = pd.read_csv(a.cec)
    cec.columns = [str(c).strip() for c in cec.columns]
    pass_rows = cec[cec.get("cec", pd.Series(dtype=str)).astype(str).str.contains("PASS", na=False)]
    # 干净基底没有对应的 golden 路径（它在 base/ 下），脚本这里按"非实例视图"排除
    pass_rows = pass_rows[pass_rows.stem.astype(str).str.contains("__")]
    print(f"[INFO] CEC 通过且可登记的变体 {len(pass_rows)} 个")

    rwv_path = H / "rewrite_variants.csv"
    rwv = pd.read_csv(rwv_path) if rwv_path.exists() else pd.DataFrame(
        columns=["host", "src_view", "rw_view", "mode", "n_rewritten",
                 "n_objects", "n_split_1toN", "skip_reasons", "rw_netlist"])

    n_copy = n_map = n_row = 0
    for r in pass_rows.itertuples():
        src, recipe, host = str(r.stem), str(r.recipe), str(r.host)
        rw_view = f"{src}__ys_{recipe}"
        src_file = a.converted / host / f"{rw_view}.v"
        if not src_file.exists():
            print(f"[WARN] 找不到转换产物 {src_file}")
            continue
        dst_dir = H / host / "rw"
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not a.dry_run:
            shutil.copy(src_file, dst_dir / f"{rw_view}.v")
        n_copy += 1
        # 抄一个同源已有 mapping 的 schema
        mp_dir = H / host / "rw_mappings"
        mp_dir.mkdir(parents=True, exist_ok=True)
        ref = next((p for p in mp_dir.glob(f"{src}__rw*.json")), None)
        m = json.loads(ref.read_text(encoding="utf-8")) if ref else {}
        m.update({"src_verilog": f"{host}/{src}.v", "rw_view": rw_view,
                  "mode": f"ys_{recipe}", "generator": "yosys+assign_to_gates",
                  "n_split_1toN": 0, "node_alignment": []})
        if not a.dry_run:
            (mp_dir / f"{rw_view}.json").write_text(
                json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        n_map += 1
        if rw_view not in set(rwv.rw_view.astype(str)):
            rwv.loc[len(rwv)] = {"host": host, "src_view": src, "rw_view": rw_view,
                                 "mode": f"ys_{recipe}",
                                 "n_rewritten": int(m.get("n_rewritten", 0) or 0),
                                 "n_objects": int(m.get("n_objects", 0) or 0),
                                 "n_split_1toN": 0, "skip_reasons": "",
                                 "rw_netlist": str(dst_dir / f"{rw_view}.v")}
            n_row += 1
    if not a.dry_run:
        rwv.to_csv(rwv_path, index=False, encoding="utf-8-sig")
    print(f"[OK] 复制 {n_copy} 个网表｜写 {n_map} 个 mapping｜追加 {n_row} 行 rewrite_variants"
          + ("（dry-run，未落盘）" if a.dry_run else ""))
    print("[下一步] py phase2\\build_hosts_fold.py --hosts-root "
          f"{a.hosts_root} --out-dir <新 fold 目录>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
