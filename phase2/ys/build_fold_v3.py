# -*- coding: utf-8 -*-
"""build_fold_v3.py —— **fold 重建（v3）**：修掉 A5 的 5 个缺口。

与老 `build_hosts_fold.py` 的差别（都是 A5 查出来的 ✗）：
  1) orig 放**全部**注入视图（74 ✓，含对照 ✓），不再只放木马 ✓
  2) trans 放**全部 418 个产物**（5 个配方全覆盖 ✓，含 id/nand/opt ✓）
  3) mappings 用 **make_inst_alignment 的实例级对齐** ✓（不是老的名字级 ✗）
  4) `view_manifest_cec.csv` 由 A5 manifest 生成 ✓ → `dataset_meta.cec_all_pass` 有据可查 ✓
  5) `orig_view_map.json` **按真实血缘**（src_verilog = 真实源视图 ✓，不做「对照→匹配木马」的 remap ✗）

两级：
  --stage prep   只铺文件（快 ✓）：orig / trans / mappings / views.json / views_meta.csv /
                 view_manifest_cec.csv / orig_view_map.json
  --stage graphs parser2 + process_pt2（慢 ✗，产出 processed/*.pt 与 dataset_meta.json）

用法：
  py phase2/ys/build_fold_v3.py --stage prep
  py phase2/ys/build_fold_v3.py --stage graphs
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CUR))
from phase2 import netlist_lib as NL          # noqa: E402
import make_inst_alignment as MIA             # noqa: E402

PARSER2 = ROOT / "data" / "verilog_data" / "parser2.py"
PROCESS_PT2 = ROOT / "process_pt2.py"
BATCHES = [
    ("yslib_test", ROOT / "generate_trans" / "yslib_test" / "convert_manifest.csv", "hosts_bt2"),
    ("keepab", ROOT / "generate_trans" / "keepab" / "conv" / "convert_manifest.csv", "hosts_bt2"),
    ("a4", ROOT / "generate_trans" / "a4" / "conv" / "convert_manifest.csv", "hosts_a4"),
    ("a4b", ROOT / "generate_trans" / "a4b" / "conv" / "convert_manifest.csv", "hosts_a4"),
]
TEST_HOSTS = {"s38584t100"}
VAL_HOSTS = {"s38417t100"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["prep", "graphs"], default="prep")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "generate_trans" / "folds" / "hosts_bt3")
    ap.add_argument("--lib", type=Path, default=MIA.LIB_DEFAULT)
    ap.add_argument("--val-every", type=int, default=0)
    a = ap.parse_args()
    W = a.out_dir.resolve()
    W.mkdir(parents=True, exist_ok=True)

    if a.stage == "graphs":
        return graphs(W, a)

    for d in ("orig", "trans", "mappings", "logs", "data/for_train", "data/not_for_train"):
        (W / d).mkdir(parents=True, exist_ok=True)
    lib = NL.load_library(a.lib)

    # 注入记录（两套 hosts-root ✓）
    prov = {}
    for r2 in ("hosts_bt2", "hosts_a4"):
        for f in sorted((ROOT / "generate_trans" / r2).glob("*/provenance.json")):
            for rec in json.loads(f.read_text(encoding="utf-8")):
                prov[(r2, rec["view"])] = rec

    rows, cec_rows, ovm = [], [], {}
    n_copy = 0
    for tag, man, srcroot in BATCHES:
        d = pd.read_csv(man)
        for r in d.itertuples():
            if str(r.file).startswith("ERROR"):
                continue
            stem, recipe = str(r.stem), str(r.recipe)
            view = MIA.re.sub(r"__keep\w+$", "", stem) if hasattr(MIA, "re") else stem.split("__keep")[0]
            host = str(r.host)
            viewer = f"{stem}__ys_{recipe}"
            cand = Path(str(r.file))
            src = ROOT / "generate_trans" / srcroot / host / f"{view}.v"
            if not (cand.exists() and src.exists()):
                continue
            rec = prov.get((srcroot, view), {})
            mp_p = cand.with_suffix(".map.json")
            ip = ({str(k): str(v) for k, v in
                   (json.loads(mp_p.read_text(encoding="utf-8")).get("inst_prov") or {}).items()}
                  if mp_p.exists() else {})
            srcf, candf = MIA.src_facts(src, lib), MIA.cand_facts(cand)
            align, _legacy, hits = MIA.build_align(srcf, candf, ip)
            mp = {"src_verilog": f"{view}.v", "src_view": view, "rw_view": viewer,
                  "operator_family": f"ys_{recipe}", "mode": f"ys_{recipe}",
                  "generator": "yosys+assign_to_gates",
                  "node_alignment": align, "n_rewritten": max(0, len(candf["gates"]) - len(align)),
                  "n_split_objects": 0, "skipped": {},
                  "hit_by_instprov": hits["instprov"], "hit_by_base": hits["base"],
                  "hit_by_port": hits["port"], "hit_by_net": hits["net"],
                  "hit_by_name": hits["name"], "batch": tag}
            (W / "mappings" / f"{viewer}.json").write_text(
                json.dumps(mp, ensure_ascii=False, indent=1), encoding="utf-8")
            shutil.copy2(cand, W / "trans" / f"{viewer}.v")
            shutil.copy2(src, W / "orig" / f"{view}.v")
            n_copy += 1
            cec_rows.append({"view": viewer, "cec_status": str(rec.get("cec_benign", "") or "UNKNOWN"),
                             "host": host, "batch": tag})
            ovm.setdefault(view, []).append(viewer)
            rows.append({"view": viewer, "host": host, "src_view": view,
                         "inst_id": view.split("__")[1].split("_d1")[0],
                         "kind": rec.get("kind", ""),
                         "family": (rec.get("a4_family") or rec.get("ctl_type") or ""),
                         "op": f"ys_{recipe}", "label1": int(rec.get("kind") == "trojan"),
                         "label_usable": rec.get("label_usable", 1), "batch": tag})

    views = sorted(p.stem for p in (W / "trans").glob("*.v"))
    test_v = [v for v in views if v.split("__")[0] in TEST_HOSTS]
    val_v = [v for v in views if v.split("__")[0] in VAL_HOSTS]
    train_v = [v for v in views if v not in set(test_v) | set(val_v)]
    (W / "views.json").write_text(json.dumps({
        "fold": W.name, "level": "controlled_cross_host",
        "train_views": train_v, "val_views": val_v, "test_views": test_v,
        "note": "v3：orig=全部 74 个注入视图；trans=全部 418 个产物（5 配方）；mappings=实例级对齐；"
                "test/val 按 host 切分（跨 host ✓）；CEC 见 view_manifest_cec.csv"},
        indent=2, ensure_ascii=False), encoding="utf-8")
    (W / "views.txt").write_text("\n".join(views) + "\n", encoding="utf-8")
    (W / "orig_view_map.json").write_text(json.dumps(ovm, indent=1, ensure_ascii=False),
                                         encoding="utf-8")
    pd.DataFrame(rows).to_csv(W / "views_meta.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(cec_rows).drop_duplicates("view").to_csv(
        W / "view_manifest_cec.csv", index=False, encoding="utf-8-sig")
    for asset in ("verilog_lib.v", "gatelookup_recommended.json",
                  "gate_full_to_simplified_mapping.json"):
        s = ROOT / "generate_trans" / "folds" / "single_to_composed_d2" / asset
        if s.exists():
            shutil.copy2(s, W / asset)
    print(f"[prep] trans={len(views)} orig={len(list((W / 'orig').glob('*.v')))} "
          f"mappings={len(list((W / 'mappings').glob('*.json')))} "
          f"train/val/test={len(train_v)}/{len(val_v)}/{len(test_v)}")
    print(pd.DataFrame(rows).groupby(["batch", "op"]).size().to_string())
    return 0


def graphs(W: Path, a) -> int:
    import os
    env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
    with open(W / "logs" / "parser2.log", "w", encoding="utf-8") as lf:
        rc = subprocess.call([sys.executable, "-X", "utf8", str(PARSER2),
                              "--out-root", "./data/for_train", "--skip-debug",
                              "--cycle-mode", "contract",
                              "--prov-root",
                              str(ROOT / "generate_trans" / "hosts_bt2") + ","
                              + str(ROOT / "generate_trans" / "hosts_a4")],
                             cwd=str(W), stdout=lf, stderr=subprocess.STDOUT, env=env)
    print(f"[parser2] rc={rc}")
    if rc != 0:
        return rc
    cmd = [sys.executable, str(PROCESS_PT2), "--work-dir", str(W),
           "--fold-json", str(W / "views.json"), "--matrix-root", str(W),
           "--trans-label", "transported"]
    if a.val_every:
        cmd += ["--val-every", str(a.val_every)]
    rc = subprocess.call(cmd, cwd=str(ROOT))
    print(f"[process_pt2] rc={rc}")
    mp = W / "data" / "processed" / "dataset_meta.json"
    if mp.exists():
        m = json.loads(mp.read_text(encoding="utf-8"))
        print(f"  orig={m.get('orig')} trans={m.get('trans')} n_views={m.get('n_views')} "
              f"(train {m.get('n_train_views')}/val {m.get('n_val_views')}/test {m.get('n_test_views')}) "
              f"cec_all_pass={m.get('cec_all_pass')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
