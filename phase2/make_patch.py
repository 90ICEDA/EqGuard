# -*- coding: utf-8 -*-
"""
make_patch.py —— 生成「本轮对主流水线改动」的 unified diff。

背景：GIN_train/ 不在 git 跟踪范围内，没有可用基线，因此这里用**已知的追加块**反向重建
原始文件（只做删除，不改动其它内容），再用 difflib 产出标准 unified diff。

用法：
  python phase2/make_patch.py --out-dir 10.5/code/diffs
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent

# train_test2.3.py 的本轮改动（均为「新增块」，按出现顺序）
T23_ADDITIONS = [
    # 1) CLI: --save-ckpt
    '''    ap.add_argument("--save-ckpt", action="store_true",
                    help="把每个外层划分的最优 state_dict 存到结果目录（best_model_<split>.pt）——"
                         "供 phase2 的表征 audit / 反事实评测复用，不改变训练本身")
''',
    # 2) CLI: view-policy 增加 inspection_hard
    '''    ap.add_argument("--view-policy", choices=["all", "random", "pred_hard", "inspection_hard"],
                    default="all")
''',
    # 3) epoch loop: inspection_hard 难度
    '''        elif args.view_policy == "inspection_hard" and (epoch % max(1, args.hard_buffer) == 0):
            hardness = view_inspection_hardness(model, trans, vidx_t, train_views, amp=amp)
''',
]
# 被「替换」的行（原 → 新），用于反向还原
T23_REPLACEMENTS = [
    ('        else:  # pred_hard / inspection_hard：按当前模型的视图难度从大到小取（难样本优先）\n',
     '        else:  # pred_hard：按当前模型的视图损失从大到小取（失去难样本优先）\n'),
    ('    ap.add_argument("--view-policy", choices=["all", "random", "pred_hard", "inspection_hard"],\n                    default="all")\n',
     '    ap.add_argument("--view-policy", choices=["all", "random", "pred_hard"], default="all")\n'),
]

# 新增函数：从 def view_inspection_hardness( 到其 return hard + 空行
T23_FUNC_START = 'def view_inspection_hardness(model, trans, vidx_t, views, amp=False, budget_ratio=0.05):'
T23_FUNC_END = '    model.train()\n    return hard\n\n\n'

# main 里的 ckpt 保存块
T23_CKPT_START = '        if args.save_ckpt:\n'
T23_CKPT_END = '        print(f"    阈值={thr:.4f}｜最优 val AP='

# run_fold_groups.py 的两处追加
RFG_ADDITIONS = [
    '''    ap.add_argument("--save-ckpt", action="store_true",
                    help="透传给 train_test2.3.py：把每组最优 state_dict 存到结果目录，供 phase2 复用")
''',
    '''        if args.save_ckpt:
            cmd.append("--save-ckpt")
''',
]


def _cut(src: str, start_marker: str, end_marker: str, keep_end: bool = False) -> str:
    i = src.index(start_marker)
    j = src.index(end_marker, i)
    tail = end_marker if keep_end else ""
    return src[:i] + tail + src[j + (0 if keep_end else len(end_marker)):]


def reconstruct_t23(text: str) -> str:
    out = text
    for new, old in T23_REPLACEMENTS:
        out = out.replace(new, old, 1)
    # 删除新增函数（连同前面的两个空行）
    i = out.index(T23_FUNC_START) - 2
    j = out.index(T23_FUNC_END, i) + len(T23_FUNC_END)
    out = out[:i] + out[j:]
    # 删除 CLI 追加
    for a in T23_ADDITIONS[:2]:
        out = out.replace(a, "", 1)
    # 删除 epoch loop 的 elif 分支
    out = out.replace(T23_ADDITIONS[2], "", 1)
    # 删除 ckpt 保存块（保留结尾的 print）
    i = out.index(T23_CKPT_START)
    j = out.index(T23_CKPT_END, i)
    out = out[:i] + out[j:]
    return out


def reconstruct_rfg(text: str) -> str:
    out = text
    for a in RFG_ADDITIONS:
        out = out.replace(a, "", 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成本轮主流水线改动的 unified diff")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.5" / "code" / "diffs")
    ap.add_argument("--orig-dir", type=Path, default=ROOT / "10.5" / "code" / "orig_reconstructed",
                    help="把反推出来的原始文件也留一份，便于复核")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.orig_dir.mkdir(parents=True, exist_ok=True)

    for fn, recon in (("train_test2.3.py", reconstruct_t23),
                      ("run_fold_groups.py", reconstruct_rfg)):
        cur = (ROOT / fn).read_text(encoding="utf-8").splitlines(keepends=True)
        orig_text = recon("".join(cur))
        (args.orig_dir / fn).write_text(orig_text, encoding="utf-8")
        orig = orig_text.splitlines(keepends=True)
        diff = list(difflib.unified_diff(orig, cur, fromfile=f"a/{fn}", tofile=f"b/{fn}", n=3))
        (args.out_dir / f"{fn}.diff").write_text("".join(diff), encoding="utf-8")
        print(f"[OK] {fn}: diff {len(diff)} 行 -> {args.out_dir / (fn + '.diff')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
