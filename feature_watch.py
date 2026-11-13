import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 加载特征矩阵 (假设路径如下)
feats = np.load('./data/verilog_data/data/for_train/feats_orig.npy')

# 提取数值特征列 (Index 25-32)
# 25:Fan-in, 26:Degree, 27:PI_Adj, 28:PO_Adj, 29:Dist_PI, 30:Dist_PO, 31:Fan-in-2h, 32:Fan-out-2h
num_feats = feats[:, 25:]

# 定义特征名称以便观察
feature_names = [
    'Fan-in (log1p)', 'Total Degree (log1p)', 
    'Is_PI_Adj', 'Is_PO_Adj', 
    'Dist_to_PI', 'Dist_to_PO', 
    'Fan-in 2-hop (log1p)', 'Fan-out 2-hop (log1p)'
]

# 转换为 DataFrame
df_num = pd.DataFrame(num_feats, columns=feature_names)
print("数值特征统计分布：")
print(df_num.describe())

# 如果想看原始数值（还原 log1p），可以执行：
# print(np.expm1(df_num[['Fan-in (log1p)', 'Total Degree (log1p)']]).describe())