# -*- coding: utf-8 -*-
"""
p2common.py —— phase2 公共工具

职责：
  1) 视图名解析（电路 / 算子链 / 深度 / seed），与 process_pt2.parse_view_meta 语义一致；
  2) fold 数据读取 + checkpoint 载入 + 隐藏层嵌入导出（forward hook，不改模型）；
  3) 视图级「检查预算」指标：AP / Recall@K% / first-hit rank / AnyMiss / inspection cost；
  4) 视图级强度元数据（view_metadata.csv）读取与分箱；
  5) 配对一致性指标（复用 train_test2.2 的实现，保证与主流水线一致）。

所有函数只读，不写训练产物。
"""
from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent


def _load_t22():
    spec = importlib.util.spec_from_file_location("train_test2_2", str(ROOT / "train_test2.2.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T22 = _load_t22()

# --------------------------------------------------------------------------
# 1) 视图名解析
# --------------------------------------------------------------------------
_VIEW_RE = re.compile(r"^(?P<head>[^_]+)__(?P<ops>[a-z\-]+)_d(?P<depth>\d+)_s(?P<seed>\d+)$")


@dataclass(frozen=True)
class ViewInfo:
    view: str
    stem: str          # 网表 stem（含 t 后缀），如 rs232t1000
    circuit: str       # 短电路名，如 rs232
    operators: str     # 如 "balance" / "balance-decomp"
    op_chain: Tuple[str, ...]
    depth: int
    seed: int

    @property
    def first_op(self) -> str:
        return self.op_chain[0] if self.op_chain else ""

    @property
    def last_op(self) -> str:
        return self.op_chain[-1] if self.op_chain else ""


def short_circuit(stem: str) -> str:
    """rs232t1000 -> rs232；s15850t100 -> s15850。"""
    return stem.rsplit("t", 1)[0] if "t" in stem else stem


def parse_view(view: str) -> ViewInfo:
    m = _VIEW_RE.match(view)
    if m:
        head, ops, depth, seed = m["head"], m["ops"], int(m["depth"]), int(m["seed"])
    else:  # 容错：手工构造的视图名（如 <stem>__none_d0_s0）
        head, _, tail = view.partition("__")
        ops, depth, seed = tail.split("_")[0], 0, -1
        for b in tail.split("_"):
            if b.startswith("d") and b[1:].isdigit():
                depth = int(b[1:])
            elif b.startswith("s") and b[1:].isdigit():
                seed = int(b[1:])
    chain = tuple(x for x in ops.split("-") if x)
    return ViewInfo(view=view, stem=head, circuit=short_circuit(head),
                    operators=ops, op_chain=chain, depth=depth, seed=seed)


# --------------------------------------------------------------------------
# 2) fold 数据 / 模型 / 嵌入
# --------------------------------------------------------------------------
def load_fold(pt_dir: Path):
    orig = torch.load(pt_dir / "orig_graph.pt", weights_only=False)
    trans = torch.load(pt_dir / "trans_graph.pt", weights_only=False)
    meta = json.loads((pt_dir / "dataset_meta.json").read_text(encoding="utf-8"))
    return orig, trans, meta


def view_index(trans) -> Dict[str, torch.Tensor]:
    out: Dict[str, List[int]] = {}
    for i, v in enumerate(trans.file_ids):
        out.setdefault(v, []).append(i)
    return {v: torch.tensor(idx, dtype=torch.long) for v, idx in out.items()}


def build_model(in_channels: int, hidden: int = 64, layers: int = 4, out: int = 2):
    from models.gin_net import GINNodeClassifier
    return GINNodeClassifier(in_channels=in_channels, hidden_channels=hidden,
                             out_channels=out, num_layers=layers)


def build_model_kind(kind: str, in_channels: int, **kwargs):
    """按 ckpt 里记录的 model_kind 还原结构（M0='gin'；M1/M2='sec'）。"""
    if kind == "sec":
        from phase2.methods import SecGIN
        return SecGIN(in_channels=in_channels, **kwargs)
    return build_model(in_channels, **{k: v for k, v in kwargs.items()
                                       if k in ("hidden", "layers")})


def load_ckpt(ckpt_path: Path, device, kind: str = None):
    """从 best_model_*.pt / best_sec_*.pt 还原模型（与保存时同结构）。

    对 M1/M2 的 ckpt：`classifier` 与 M0 同名同形状，因此 Embedder / 探针脚本可原样复用。
    """
    blob = torch.load(ckpt_path, map_location=device, weights_only=False)
    kind = kind or blob.get("model_kind", "gin")
    model = build_model_kind(kind, int(blob["in_channels"]), **blob.get("model_kwargs", {}))
    model.load_state_dict(blob["state_dict"])
    model.to(device).eval()
    return model, blob


class Embedder:
    """给 GINNodeClassifier 挂 forward hook，取出 classifier 之前的隐藏表示 h（64 维）。

    不修改模型定义，纯推理；一次 forward 同时得到 (h, logits)。
    """

    def __init__(self, model):
        self.model = model
        self._buf: Dict[str, torch.Tensor] = {}
        self._handle = model.classifier.register_forward_hook(self._hook)

    def _hook(self, module, inputs, output):
        self._buf["h"] = inputs[0]

    def close(self):
        self._handle.remove()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @torch.no_grad()
    def forward(self, x, edge_index, amp=False):
        dev = next(self.model.parameters()).device
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=bool(amp) and dev.type == "cuda"):
            logits = self.model(x, edge_index)
        return self._buf["h"].float(), logits.float()


# --------------------------------------------------------------------------
# 3) 视图级「检查预算」指标
# --------------------------------------------------------------------------
def first_hit_rank(p: np.ndarray, y: np.ndarray) -> int:
    """Trojan 节点中分数最高者的 1-based 降序名次（1 = 最高分）。无正样本返回 -1。"""
    pos = np.where(y == 1)[0]
    if len(pos) == 0:
        return -1
    order = np.argsort(-p)
    rank_of = np.empty(len(p), dtype=np.int64)
    rank_of[order] = np.arange(1, len(p) + 1)
    return int(rank_of[pos].min())


def recall_at_ratio(p: np.ndarray, y: np.ndarray, ratio: float) -> float:
    n = len(p)
    pos = int(y.sum())
    if n == 0 or pos == 0:
        return 0.0
    k = max(1, int(n * ratio))
    topk = np.argsort(-p)[:k]
    return float(y[topk].sum()) / float(pos)


def average_precision(p: np.ndarray, y: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, p))


def view_budget_metrics(p: np.ndarray, y: np.ndarray, ratios=(0.01, 0.02, 0.05)) -> Dict[str, float]:
    """一个视图在有限检查预算下的全部指标（p = Trojan 概率，y = 0/1）。"""
    n = int(len(p))
    pos = int(y.sum())
    out: Dict[str, float] = {"N": n, "N_Trojan": pos, "AP_T": average_precision(p, y)}
    for r in ratios:
        out[f"Recall@{int(r * 100)}%"] = recall_at_ratio(p, y, r)
    fh = first_hit_rank(p, y)
    out["FirstHitRank"] = float(fh)
    out["FirstHitRank_Norm"] = (fh / n) if fh > 0 and n > 0 else float("nan")
    out["InspectionCost"] = (fh / n) if fh > 0 and n > 0 else float("nan")
    for r in ratios:
        k = max(1, int(n * r))
        out[f"AnyMiss@{int(r * 100)}%"] = float(fh > k) if fh > 0 else float("nan")
    return out


def paired_consistency(preds_o: torch.Tensor, preds_t: torch.Tensor,
                       alignment: torch.Tensor, labels_o: torch.Tensor,
                       threshold: float, top_k: int = 50) -> Dict[str, float]:
    """复用 2.2 的实现（逐对 + PerOrig）。"""
    return T22.calc_detailed_consistency(preds_o, preds_t, labels_o, alignment,
                                         threshold, top_k=top_k)


# --------------------------------------------------------------------------
# 4) 强度元数据
# --------------------------------------------------------------------------
def load_view_metadata(matrix_root: Path) -> pd.DataFrame:
    df = pd.read_csv(matrix_root / "view_metadata.csv")
    return df.rename(columns={"view_name": "view"}).set_index("view")


def strength_bins(df: pd.DataFrame, col: str = "edit_ratio", n_bins: int = 4) -> pd.Series:
    """在 (circuit, composition_depth) 组内按 col 分箱 → 0..n_bins-1（Int64，缺失可为 NA）。"""
    g = df.groupby(["circuit", "composition_depth"])[col]
    return g.transform(lambda s: pd.qcut(s.rank(method="first"), n_bins,
                                         labels=False, duplicates="drop")).astype("Int64")


# --------------------------------------------------------------------------
# 5) 小工具
# --------------------------------------------------------------------------
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def to_numpy(x) -> np.ndarray:
    if torch.is_tensor(x):
        return x.detach().cpu().numpy()
    return np.asarray(x)
