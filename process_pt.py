import torch
import os
import numpy as np
import scipy.sparse as sp
import json
from torch_geometric.data import Data

def load_alignment(path):
    with open(path, 'r') as f:
        return json.load(f)

def build_pyg_data(adj_path, feat_path, class_path, role_path, metadata_path):
    # 1. 加载邻接矩阵并转为 edge_index
    adj = sp.load_npz(adj_path)
    adj_coo = adj.tocoo()
    edge_index = torch.tensor(np.vstack((adj_coo.row, adj_coo.col)), dtype=torch.long)

    # 2. 加载特征
    x = torch.from_numpy(np.load(feat_path)).float()


    # 3. 加载标签
    with open(class_path, 'r') as f:
        class_dict = json.load(f)
    # 确保标签顺序与节点索引一致
    y = torch.tensor([class_dict[str(i)] for i in range(len(class_dict))], dtype=torch.long)

    # 4. 加载角色划分并生成 Mask
    with open(role_path, 'r') as f:
        role = json.load(f)
    
    train_mask = torch.zeros(y.size(0), dtype=torch.bool)
    train_mask[role['tr']] = True
    
    val_mask = torch.zeros(y.size(0), dtype=torch.bool)
    val_mask[role['va']] = True
    
    test_mask = torch.zeros(y.size(0), dtype=torch.bool)
    test_mask[role['te']] = True

    data = Data(x=x, edge_index=edge_index, y=y, 
                train_mask=train_mask, val_mask=val_mask, test_mask=test_mask)

    # 6. 加载并注入电路前缀信息 (用于 LOCO)
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            meta = json.load(f)
            # 此时 data 已经定义，可以安全赋值
            data.prefixes = meta['prefixes'] 
            data.file_ids = meta['file_ids']
    else:
        print(f"警告: 找不到元数据文件 {metadata_path}")
        data.prefixes = []

    return data

# 分别生成两个 .pt 文件
orig_data = build_pyg_data(
    adj_path='./data/verilog_data/data/for_train/adj_full_orig.npz', 
    feat_path='./data/verilog_data/data/for_train/feats_orig.npy', 
    class_path='./data/verilog_data/data/for_train/class_map_orig.json', 
    role_path='./data/verilog_data/data/for_train/role_orig.json',
    metadata_path='./data/verilog_data/data/for_train/metadata_orig.json'
)

trans_data = build_pyg_data(
    adj_path='./data/verilog_data/data/for_train/adj_full_trans.npz', 
    feat_path='./data/verilog_data/data/for_train/feats_trans.npy', 
    class_path='./data/verilog_data/data/for_train/class_map_trans.json', 
    role_path='./data/verilog_data/data/for_train/role_trans.json',
    metadata_path='./data/verilog_data/data/for_train/metadata_trans.json'
)

# 2. 加载之前生成的索引映射
# 格式为: [[orig_idx, [trans_idx1, trans_idx2]], ...]
raw_alignment = load_alignment('./data/verilog_data/data/for_train/alignment.json')

alignment_tensor = torch.tensor(raw_alignment, dtype=torch.long).t() # 结果维度为 [2, N]

# 接下来正常存储即可
trans_data.alignment = alignment_tensor
print(f"对齐映射加载完成。映射对数量: {alignment_tensor.shape[1]}")

# 存储路径
os.makedirs('./data/processed', exist_ok=True)
torch.save(orig_data, './data/processed/orig_graph.pt')
torch.save(trans_data, './data/processed/trans_graph.pt')