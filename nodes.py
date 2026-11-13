import numpy as np
import json
import os
import pandas as pd

def export_all_nodes_to_csv(data_dir='./data/verilog_data/data/for_train', output_path='all_circuit_nodes.csv'):
    print(f"开始从 {data_dir} 加载数据...")

    # 1. 加载特征矩阵 (33维)
    # [0-24]: One-hot, [25]: Fan-in, [26]: Degree, [27-28]: PI/PO Adj, 
    # [29-30]: Dist, [31-32]: Fan-in/out 2-hop
    feats = np.load(os.path.join(data_dir, 'feats_orig.npy'))
    num_nodes = feats.shape[0]

    # 2. 加载标签 (木马标记)
    with open(os.path.join(data_dir, 'class_map_orig.json'), 'r') as f:
        class_map = json.load(f)

    # 3. 加载数据集划分 (Train/Val/Test)
    with open(os.path.join(data_dir, 'role_orig.json'), 'r') as f:
        role = json.load(f)

    # 4. 加载门映射表 (还原名字)
    with open('gatelookup_recommended.json', 'r') as f:
        g_json = json.load(f)
        g_map = g_json.get('gatelookup', g_json)
        idx_to_gate = {v: k for k, v in g_map.items()}

    # 5. 构建数据列表
    all_data = []

    # 为了快速查询 split，构建一个映射
    split_map = {}
    for idx in role.get('tr', []): split_map[idx] = 'Train'
    for idx in role.get('va', []): split_map[idx] = 'Val'
    for idx in role.get('te', []): split_map[idx] = 'Test'

    print(f"正在处理 {num_nodes} 个节点...")


    for i in range(num_nodes):
        # 还原门名字
        gate_one_hot = feats[i, :25]
        gate_idx = np.argmax(gate_one_hot)
        gate_name = idx_to_gate.get(gate_idx, "Unknown")

        # 提取各个维度的特征
        node_info = {
            'node_index': i,
            'gate_type': gate_name,
            'label': int(class_map.get(str(i), 0)),
            'split': split_map.get(i, 'Unassigned'),
            'fan_in': int(np.expm1(feats[i, 25])),
            'total_degree': int(np.expm1(feats[i, 26])),
            'is_pi_adj': int(feats[i, 27]),
            'is_po_adj': int(feats[i, 28]),
            'dist_to_pi': feats[i, 29], # 还原缩放前的步数
            'dist_to_po': feats[i, 30],
            'fan_in_2hop': int(np.expm1(feats[i, 31])),
            'fan_out_2hop': int(np.expm1(feats[i, 32]))
        }
        all_data.append(node_info)

    # 6. 转换为 DataFrame 并导出
    df = pd.DataFrame(all_data)
    
    # 调整列顺序，方便阅读
    cols = ['node_index', 'gate_type', 'label', 'split', 'dist_to_pi', 'dist_to_po', 
            'fan_in', 'total_degree', 'fan_in_2hop', 'fan_out_2hop', 'is_pi_adj', 'is_po_adj']
    df = df[cols]
    
    df.to_csv(output_path, index=False)
    print(f"导出成功！文件已保存至: {output_path}")
    
    # 打印一些基本统计
    print("\n--- 电路概览 ---")
    print(f"总门数: {len(df)}")
    print(f"木马节点数: {df['label'].sum()}")
    print(df['gate_type'].value_counts().head(10))

if __name__ == "__main__":
    export_all_nodes_to_csv()