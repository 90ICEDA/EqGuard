import pandas as pd
import json
import os

def run_data_cleaning(orig_csv='all_circuit_nodes.csv', 
                      trans_csv='all_circuit_nodes_trans.csv', 
                      alignment_json='./data/verilog_data/data/for_train/alignment.json'):
    
    print("正在加载 CSV 数据...")
    if not os.path.exists(orig_csv) or not os.path.exists(trans_csv):
        print(f"[ERROR] 找不到 CSV 文件，请先运行 nodes.py 生成它们。")
        return

    df_orig = pd.read_csv(orig_csv)
    df_trans = pd.read_csv(trans_csv)

    suspicious_list = []

    # ---------------------------------------------------------
    # 规则 1: 死路木马检测 (Dead-end Trojan)
    # 条件: label=1 且 fan_out_2hop=0 且 is_po_adj=0
    # ---------------------------------------------------------
    print("执行规则 1: 检测无有效扇出的木马节点...")
    # 在 Original 图中检测
    rule1_orig = df_orig[
        (df_orig['label'] == 1) & 
        (df_orig['fan_out_2hop'] == 0) & 
        (df_orig['is_po_adj'] == 0)
    ]
    
    for _, row in rule1_orig.iterrows():
        suspicious_list.append({
            'Node_Index': int(row['node_index']),
            'Source_Graph': 'Original',
            'Reason': '死路木马 (Label=1但无扇出且非PO引脚)',
            'Details': f"GateType: {row['gate_type']}"
        })

    # ---------------------------------------------------------
    # 规则 2: 变换一致性检测 (Label Mismatch)
    # 条件: 原始节点与变换后对应的节点 Label 不一致
    # ---------------------------------------------------------
    print("执行规则 2: 检测变换前后标签冲突...")
    if os.path.exists(alignment_json):
        with open(alignment_json, 'r') as f:
            alignment = json.load(f) # 格式 [[orig_idx, trans_idx], ...]
        
        # 将 trans 的 label 转换为字典以加速查询
        trans_label_dict = df_trans.set_index('node_index')['label'].to_dict()
        # 将 orig 的 label 转换为字典
        orig_label_dict = df_orig.set_index('node_index')['label'].to_dict()

        for o_idx, t_idx in alignment:
            o_label = orig_label_dict.get(o_idx)
            t_label = trans_label_dict.get(t_idx)

            if o_label is not None and t_label is not None:
                if o_label != t_label:
                    suspicious_list.append({
                        'Node_Index': f"O:{o_idx} -> T:{t_idx}",
                        'Source_Graph': 'Alignment',
                        'Reason': f'标签冲突 (原始:{o_label}, 变换后:{t_label})',
                        'Details': '节点在等价变换过程中丢失了木马属性或错误标记'
                    })
    else:
        print(f"[WARNING] 找不到对齐文件 {alignment_json}，跳过一致性检测。")

    # ---------------------------------------------------------
    # 补充规则: 逻辑不可达节点检测 (Isolated Nodes)
    # 条件: dist_to_pi < 0 或 dist_to_po < 0
    # ---------------------------------------------------------
    print("执行补充规则: 检测逻辑不可达节点...")
    unreachable = df_orig[(df_orig['dist_to_pi'] < 0) | (df_orig['dist_to_po'] < 0)]
    
    for _, row in unreachable.iterrows():
        suspicious_list.append({
            'Node_Index': int(row['node_index']),
            'Source_Graph': 'Original',
            'Reason': '逻辑不可达 (孤立节点)',
            'Details': f"PI距离: {row['dist_to_pi']}, PO距离: {row['dist_to_po']}"
        })

    # ---------------------------------------------------------
    # 保存结果
    # ---------------------------------------------------------
    if suspicious_list:
        report_df = pd.DataFrame(suspicious_list)
        # 去重（防止同一节点触发多条规则）
        report_df = report_df.drop_duplicates(subset=['Node_Index', 'Reason'])
        
        output_file = 'suspicious_samples_report.csv'
        report_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n[完成] 清洗结束，发现 {len(report_df)} 个可疑异常点。")
        print(f"详细报告已生成: {output_file}")
        
        # 打印简单摘要
        print("\n异常分类统计:")
        print(report_df['Reason'].value_counts())
    else:
        print("\n[完成] 未发现任何逻辑或标签异常。")

if __name__ == "__main__":
    run_data_cleaning()