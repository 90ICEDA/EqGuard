import pandas as pd
import numpy as np
import os
from scipy.stats import ks_2samp

def run_sanity_check_csv(orig_csv='all_circuit_nodes.csv', trans_csv='all_circuit_nodes_trans.csv'):
    print("开始执行 Sanity Check 并准备导出 CSV...")
    
    # 1. 加载数据
    if not os.path.exists(orig_csv) or not os.path.exists(trans_csv):
        print("错误: 找不到输入 CSV 文件")
        return

    df_orig = pd.read_csv(orig_csv)
    df_trans = pd.read_csv(trans_csv)

    # 2. 划分三类群体
    groups = {
        'Benign_Original': df_orig[df_orig['label'] == 0].copy(),
        'Benign_Transformed': df_trans[df_trans['label'] == 0].copy(),
        'Trojan': df_orig[df_orig['label'] == 1].copy()
    }

    # 计算 Subgraph Size
    for name in groups:
        groups[name]['subgraph_size'] = groups[name]['fan_in_2hop'] + groups[name]['fan_out_2hop']

    features = ['fan_in', 'fan_out_2hop', 'dist_to_pi', 'dist_to_po', 'subgraph_size', 'total_degree']

    # 3. 计算各组的统计指标 (Mean, Std, Median)
    summary_rows = []
    for feat in features:
        row = {'Feature': feat}
        for g_name, g_df in groups.items():
            row[f'{g_name}_Mean'] = g_df[feat].mean()
            row[f'{g_name}_Std'] = g_df[feat].std()
            row[f'{g_name}_Median'] = g_df[feat].median()
        summary_rows.append(row)
    
    df_stats = pd.DataFrame(summary_rows)

    # 4. 计算漂移指标 (KS-Test: Original vs Transformed)
    drift_rows = []
    for feat in features:
        stat, p_val = ks_2samp(groups['Benign_Original'][feat], groups['Benign_Transformed'][feat])
        drift_rows.append({
            'Feature': feat,
            'KS_Stat_Drift': stat,
            'P_Value': p_val,
            'Drift_Assessment': 'Significant' if p_val < 0.05 else 'Stable'
        })
    df_drift = pd.DataFrame(drift_rows)

    # 5. 整合结果
    # 我们将统计表和漂移表合并在一起
    final_report = pd.merge(df_stats, df_drift, on='Feature')

    # 6. 计算 Gate Type 分布 (Top 5) 并作为附加行
    gate_report_rows = []
    for g_name, g_df in groups.items():
        top_gates = g_df['gate_type'].value_counts(normalize=True).head(5).to_dict()
        for gate, val in top_gates.items():
            gate_report_rows.append({
                'Feature': f'GateType_{g_name}',
                'Benign_Original_Mean': gate, # 借用列名存储门名
                'Benign_Transformed_Mean': val, # 借用列名存储百分比
                'KS_Stat_Drift': np.nan,
                'Drift_Assessment': 'Distribution_Info'
            })
    df_gates = pd.DataFrame(gate_report_rows)

    # 7. 最终保存
    output_path = 'sanity_check_report.csv'
    pd.concat([final_report, df_gates], ignore_index=True).to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[成功] 统计报告已生成: {output_path}")
    print("\n--- 报告摘要 (均值对比) ---")
    print(df_stats[['Feature', 'Benign_Original_Mean', 'Benign_Transformed_Mean', 'Trojan_Mean']].round(4))

if __name__ == "__main__":
    run_sanity_check_csv()