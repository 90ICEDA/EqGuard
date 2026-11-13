import torch
import os
from torch_geometric.data import Data

class SiameseCircuitLoader:
    def __init__(self, config):
        """
        config: 传入你的 yaml 配置字典
        """
        self.orig_path = config['data']['orig_path']
        self.trans_path = config['data']['trans_path']
        self.device = torch.device(config['train']['device'] if torch.cuda.is_available() else 'cpu')

    def load_pair(self):
        """
        加载原始和变换后的图数据对
        """
        if not os.path.exists(self.orig_path) or not os.path.exists(self.trans_path):
            raise FileNotFoundError(f"找不到预处理后的 .pt 文件，请检查路径: {self.orig_path}")

        # 加载 PyG Data 对象
        data_orig = torch.load(self.orig_path, weights_only=False)
        data_trans = torch.load(self.trans_path, weights_only=False)

        # 数据完整性检查
        self._check_data(data_orig, "Original")
        self._check_data(data_trans, "Transformed")

        if data_orig.x.shape[1] != data_trans.x.shape[1]:
            raise ValueError(f"维度不匹配! Orig 特征维度({data_orig.x.shape[1]}) "
                             f"与 Trans 特征维度({data_trans.x.shape[1]}) 必须相同。")

        # 移动到指定设备 (CPU/GPU)
        data_orig = data_orig.to(self.device)
        data_trans = data_trans.to(self.device)

        return data_orig, data_trans

    def _check_data(self, data, name):
        """ 检查必要的字段是否存在 """
        required_fields = ['x', 'edge_index', 'y', 'train_mask', 'val_mask', 'test_mask']
        for field in required_fields:
            if not hasattr(data, field):
                print(f"[警告] {name} 数据对象缺少字段: {field}")

def get_siamese_data(config):
    """ 便利函数：直接获取数据对 """
    loader = SiameseCircuitLoader(config)
    return loader.load_pair()