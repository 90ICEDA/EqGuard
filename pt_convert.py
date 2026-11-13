import torch
import os

# 如果环境里有 torch_geometric，建议导入一下，确保 Data 类被识别
try:
    from torch_geometric.data import Data
except ImportError:
    pass

# 1. 定义路径
path_orig = './data/processed/orig_graph.pt'
path_trans = './data/processed/trans_graph.pt'
out_orig = './data/processed/orig_graph_legacy.pt'
out_trans = './data/processed/trans_graph_legacy.pt'

print("开始读取数据...")

# 2. 加载数据：关键在于设置 weights_only=False
# 这样可以绕过 PyTorch 2.6 的安全限制，允许加载 Data 对象
data_o = torch.load(path_orig, weights_only=False, map_location='cpu')
data_t = torch.load(path_trans, weights_only=False, map_location='cpu')

def to_plain_dict(data_obj):
    """
    将 torch_geometric 的 Data 对象转换为纯字典。
    原因：Python 3.6 的旧环境通常没装 torch_geometric，
    直接存 Data 对象会导致老环境加载时报 ModuleNotFoundError。
    """
    out_dict = {}
    # 提取 Data 对象中的标准属性 (x, edge_index, y 等)
    for key in data_obj.keys():
        out_dict[key] = data_obj[key]
    
    # 提取我们之前手动注入的自定义属性
    custom_attrs = ['prefixes', 'file_ids', 'alignment']
    for attr in custom_attrs:
        if hasattr(data_obj, attr):
            out_dict[attr] = getattr(data_obj, attr)
            
    return out_dict

print("正在转换为兼容字典格式...")
dict_o = to_plain_dict(data_o)
dict_t = to_plain_dict(data_t)

# 3. 保存为旧版格式
# _use_new_zipfile_serialization=False 确保 PyTorch 1.1.0 能读懂
print("正在执行旧版序列化保存...")
torch.save(dict_o, out_orig, _use_new_zipfile_serialization=False)
torch.save(dict_t, out_trans, _use_new_zipfile_serialization=False)

print(f"转换成功！\n原始格式文件: {out_orig}\n变换格式文件: {out_trans}")