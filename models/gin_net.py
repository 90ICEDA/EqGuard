import os

import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint
from torch.nn import Sequential, Linear, BatchNorm1d, ReLU
from torch_geometric.nn import GINConv


def grad_ckpt_on() -> bool:
    """梯度检查点开关 ✓（`GNN_GRAD_CKPT=1` 时开 ✓）。

    为什么需要：v3.1 全量 fold 有 **3.22 M** trans 节点 ✗，4 层双分支在 8.15 GB 显存上
    backward 必 OOM ✗（2026-10-19 实测：epoch ~45 与 epoch 0 都 OOM 过 ✗）。
    检查点用**重算**换显存 ✓（数值上等价 ✓，仅慢 ~20–30% ✗→✓），是唯一不改模型容量/口径的办法 ✓。
    """
    return os.environ.get("GNN_GRAD_CKPT", "0").strip().lower() not in ("0", "", "false", "no")


class GINDual(torch.nn.Module):
    """C2：**结构 / 功能双分支** ✓（一致性只加在功能分支 ✓）。

    - 结构分支：`x[:, :split]`（门类型 one-hot + 拓扑距离/扇入扇出/环 ✓）
    - 功能分支：`x[:, split:]`（dist/2hop/环 + 锥特征 XOR/MUX 比例 ✓）
    - 融合：concat / gate / attn ✓
    - `forward()` 返回**融合 logits** ✓，同时把功能分支 logits 存到 `self.fn_logits` ✓
      （训练脚本用它算"仅功能分支一致性" ✓，评估路径不用改 ✓）
    """

    def __init__(self, in_channels, hidden_channels, out_channels, num_layers=2,
                 split=29, fusion="concat"):
        super().__init__()
        self.split = int(split)
        self.fusion = fusion

        def enc(cin):
            layers = torch.nn.ModuleList()
            layers.append(GINConv(Sequential(Linear(cin, hidden_channels),
                                             BatchNorm1d(hidden_channels), ReLU(),
                                             Linear(hidden_channels, hidden_channels))))
            for _ in range(num_layers - 1):
                layers.append(GINConv(Sequential(Linear(hidden_channels, hidden_channels),
                                                 BatchNorm1d(hidden_channels), ReLU(),
                                                 Linear(hidden_channels, hidden_channels))))
            return layers

        self.enc_s = enc(max(1, self.split))
        self.enc_f = enc(max(1, in_channels - self.split))
        self.fn_head = Linear(hidden_channels, out_channels)      # 功能分支专用头 ✓
        if fusion == "concat":
            self.fuse = Sequential(Linear(2 * hidden_channels, hidden_channels), ReLU())
        elif fusion == "gate":
            self.fuse = Linear(2 * hidden_channels, hidden_channels)
        self.classifier = Linear(hidden_channels, out_channels)
        self.fn_logits = None

    def _run(self, enc, x, edge_index):
        use_ck = grad_ckpt_on() and self.training and torch.is_grad_enabled()
        for conv in enc:
            if use_ck:
                def _seg(t, c=conv):
                    # 注意：训练态 dropout 固定为 True ✓（checkpoint 重算时必须与首算一致 ✓）
                    return F.dropout(F.relu(c(t, edge_index)), p=0.2, training=True)

                x = checkpoint(_seg, x, use_reentrant=False)
            else:
                x = F.relu(conv(x, edge_index))
                x = F.dropout(x, p=0.2, training=self.training)
        return x

    def forward(self, x, edge_index):
        hs = self._run(self.enc_s, x[:, :self.split], edge_index)
        hf = self._run(self.enc_f, x[:, self.split:], edge_index)
        self.fn_logits = self.fn_head(hf)                          # 仅功能分支 ✓
        if self.fusion == "concat":
            h = self.fuse(torch.cat([hs, hf], dim=1))
        elif self.fusion == "gate":
            g = torch.sigmoid(self.fuse(torch.cat([hs, hf], dim=1)))
            h = g * hs + (1 - g) * hf
        else:                                                       # attn
            w = torch.softmax(torch.stack([hs, hf], 0), dim=0)
            h = w[0] * hs + w[1] * hf
        return self.classifier(h)


class GINNodeClassifier(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels, num_layers=3):
        super(GINNodeClassifier, self).__init__()
        self.convs = torch.nn.ModuleList()
        
        # 第一层：输入维度 -> 隐藏维度
        self.convs.append(GINConv(
            Sequential(Linear(in_channels, hidden_channels),
                       BatchNorm1d(hidden_channels), ReLU(),
                       Linear(hidden_channels, hidden_channels))
        ))
        
        # 后续隐藏层
        for _ in range(num_layers - 1):
            self.convs.append(GINConv(
                Sequential(Linear(hidden_channels, hidden_channels),
                           BatchNorm1d(hidden_channels), ReLU(),
                           Linear(hidden_channels, hidden_channels))
            ))
            
        # 分类头：输出未归一化的 Logits (用于 CrossEntropy 和一致性计算)
        self.classifier = Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        use_ck = grad_ckpt_on() and self.training and torch.is_grad_enabled()
        for conv in self.convs:
            if use_ck:
                def _seg(t, c=conv):
                    return F.dropout(F.relu(c(t, edge_index)), p=0.2, training=True)

                x = checkpoint(_seg, x, use_reentrant=False)
            else:
                x = conv(x, edge_index)
                x = F.relu(x)
                x = F.dropout(x, p=0.2, training=self.training)
        
        logits = self.classifier(x)
        return logits