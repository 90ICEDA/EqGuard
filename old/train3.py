import torch
import torch.nn.functional as F
import yaml
import os
import sys
import numpy as np
import json
from sklearn.metrics import f1_score, recall_score, confusion_matrix
import matplotlib.pyplot as plt

# 自动处理路径，确保能找到 models 和 data_loader
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from models.gin_net import GINNodeClassifier
# --- 关键修改：导入数据加载工具 ---
from data_loader import get_siamese_data

def calc_hard_f1(preds, labels):
    """ 计算标准 F1 分数 (用于评估和日志) """
    y_pred = preds.argmax(dim=1).cpu().numpy()
    y_true = labels.cpu().numpy()
    
    # average='macro' 对木马检测这种不平衡类别非常重要
    mic = f1_score(y_true, y_pred, average='micro')
    mac = f1_score(y_true, y_pred, average='macro')
    det_rate = recall_score(y_true, y_pred, pos_label=1, zero_division=0)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    if cm.size == 4:
        tn, fp, fn, tp = cm.ravel()
    else:
        # 处理特殊情况（如全为0或全为1时ravel报错）
        tn, fp, fn, tp = 0, 0, 0, 0 
        
    return mic, mac, det_rate, tp, fp, tn, fn


def calc_soft_f1_metrics(probs, labels):
    """ 计算二分类下的可导 Soft F1 (用于损失函数) """
    labels_one_hot = F.one_hot(labels, num_classes=2).float()
    
    tp = torch.sum(probs * labels_one_hot, dim=0)         
    fp = torch.sum(probs * (1 - labels_one_hot), dim=0)   
    fn = torch.sum((1 - probs) * labels_one_hot, dim=0)   

    soft_recalls = tp / (tp + fn + 1e-10)
    sdr_normal = soft_recalls[0]
    sdr_trojan = soft_recalls[1]
    soft_f1_per_class = (2 * tp) / (2 * tp + fp + fn + 1e-10)
    
    F1mac = torch.mean(soft_f1_per_class) 
    correct_probs = torch.sum(probs * labels_one_hot) 
    F1mic = correct_probs / (labels.size(0) + 1e-10) 
    
    return F1mic, F1mac, sdr_normal, sdr_trojan


def siamese_loss(preds_o, preds_t, labels_o, labels_t, lambda_const=2.0, lambda_det=2.0, lambda_nor=1.0, trojan_w = 8.0):
    """ 孪生损失函数：结合分类误差和指标一致性误差 """
    probs_o = F.softmax(preds_o, dim=1)
    probs_t = F.softmax(preds_t, dim=1)

    # 1. 基础分类损失 (Task Loss)
    weight = torch.tensor([1.0, trojan_w], device=preds_o.device)
    task_loss_o = F.cross_entropy(preds_o, labels_o, weight = weight)
    task_loss_t = F.cross_entropy(preds_t, labels_t, weight = weight)

    # 2. 计算可导的 Soft F1 指标
    F1mic_o, F1mac_o, sdr_n_o, sdr_tr_o = calc_soft_f1_metrics(probs_o, labels_o)
    F1mic_t, F1mac_t, sdr_n_t, sdr_tr_t = calc_soft_f1_metrics(probs_t, labels_t)

    # 3. 指标对齐约束 (Consistency Loss)
    # 让原始和变换后的 F1 尽可能接近（MSE 越小，一致性越强）
    loss_mic_consistency = F.mse_loss(F1mic_o, F1mic_t)
    loss_mac_consistency = F.mse_loss(F1mac_o, F1mac_t)

    loss_det_o = trojan_w * (-torch.log(sdr_tr_o + 1e-10)) + 1.0 * (-torch.log(sdr_n_o + 1e-10))
    loss_det_t = trojan_w * (-torch.log(sdr_tr_t + 1e-10)) + 1.0 * (-torch.log(sdr_n_t + 1e-10))
    
    loss_det_rate = loss_det_o + loss_det_t

    total_loss = (task_loss_o + task_loss_t) + \
                 lambda_const * (loss_mic_consistency + loss_mac_consistency) + \
                 lambda_det * loss_det_rate
    
    loss_normal_consistency = (1.0 - sdr_n_o) + (1.0 - sdr_n_t)
    total_loss += lambda_nor * loss_normal_consistency

    return total_loss, F1mic_o, F1mac_o, F1mic_t, F1mac_t, sdr_tr_o, sdr_tr_t

def analyze_feature_importance_by_gradient(model, data):
    model.eval()
    data.x.requires_grad = True # 开启特征梯度追踪
    
    # 前向传播
    output = model(data.x, data.edge_index)
    probs = F.softmax(output, dim=1)
    
    # 目标：针对“木马”类（类别1）计算重要性
    # 我们只看模型预测为木马的那些节点，或者真实的木马节点
    target_idx = (data.y == 1) # 或者使用 probs[:, 1] > 0.5
    if target_idx.sum() == 0:
        print("未检测到木马节点，无法分析重要性")
        return

    # 计算木马类得分总和
    score = probs[target_idx, 1].sum()
    
    # 反向传播计算梯度
    model.zero_grad()
    score.backward()
    
    # 特征的重要性 = 梯度的绝对值
    importances = data.x.grad.abs().mean(dim=0).cpu().numpy()
    
    return importances

# 在训练完加载 best_model 后运行
# importances = analyze_feature_importance_by_gradient(model, data_orig)


def plot_feature_importance(importances, feature_names, top_k=15):
    """
    importances: analyze_feature_importance_by_gradient 返回的数组
    feature_names: 上面函数生成的名称列表
    """
    # 组合名字和数值
    data = list(zip(feature_names, importances))
    # 按重要性降序排列
    data.sort(key=lambda x: x[1], reverse=True)
    
    # 只取前 K 个最重要的特征，防止图表太拥挤
    data = data[:top_k]
    names, values = zip(*data)

    plt.figure(figsize=(10, 8))
    # 使用横向条形图，方便阅读特征名
    bars = plt.barh(names, values, color='skyblue', edgecolor='navy')
    plt.xlabel('Importance Score (Gradient Magnitude)')
    plt.title(f'Top {top_k} Most Influential Features for Trojan Detection')
    plt.gca().invert_yaxis() # 让最重要的排在最上面
    
    # 在条形图上标注具体数值
    for bar in bars:
        width = bar.get_width()
        plt.text(width, bar.get_y() + bar.get_height()/2, f'{width:.4f}', 
                 va='center', ha='left', fontsize=10)

    plt.grid(axis='x', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig('feature_importance.png') # 保存为图片
    plt.show()

def get_feature_names(gatelookup):
    # 1. 还原 One-hot 门名字 (按索引 0, 1, 2... 排序)
    names = [None] * len(gatelookup)
    for name, idx in gatelookup.items():
        names[idx] = name
    
        extra_names = [
        'Lib_In_Count',   # 输入端口数
        'Total_Degree',   # 邻居总数
        'Is_PI_Adj',      # 是否与PI相邻
        'Is_PO_Adj',      # 是否与PO相邻
        'Dist_to_PI',     # 到PI距离
        'Dist_to_PO'      # 到PO距离
    ]
    
    return names + extra_names

def plot_training_metrics(history):
    """ 绘制训练过程中的指标变化图 """
    epochs = history['epoch']
    
    plt.figure(figsize=(15, 10))

    # 1. Macro F1 子图
    plt.subplot(2, 2, 1)
    plt.plot(epochs, history['mac_orig'], 'b-o', label='Orig Macro F1')
    plt.plot(epochs, history['mac_trans'], 'r-s', label='Trans Macro F1')
    plt.title('Macro F1 Score (Orig vs Trans)')
    plt.xlabel('Epoch')
    plt.ylabel('F1 Score')
    plt.legend()
    plt.grid(True)

    # 2. Detection Rate 子图
    plt.subplot(2, 2, 2)
    plt.plot(epochs, history['det_orig'], 'b-o', label='Orig Det Rate')
    plt.plot(epochs, history['det_trans'], 'r-s', label='Trans Det Rate')
    plt.axhline(y=1.0, color='g', linestyle='--', alpha=0.5, label='Target')
    plt.title('Detection Rate (Recall)')
    plt.xlabel('Epoch')
    plt.ylabel('Rate')
    plt.legend()
    plt.grid(True)

    # 3. Loss 子图
    plt.subplot(2, 2, 3)
    plt.plot(epochs, history['loss'], 'k-x', label='Total Loss')
    plt.title('Training Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.grid(True)

    # 4. Consistency Gap 子图
    plt.subplot(2, 2, 4)
    plt.plot(epochs, history['gap'], 'm-d', label='Mac Gap')
    plt.title('Consistency Gap (|Orig - Trans|)')
    plt.xlabel('Epoch')
    plt.ylabel('Difference')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.savefig('training_metrics.png')
    print("[成功] 训练趋势图已保存为 training_metrics.png")
    plt.show()

def train():
    # --- 1. 加载配置 ---
    config_path = os.path.join(current_dir, 'config.yaml')
    if not os.path.exists(config_path):
        print(f"错误: 找不到配置文件 {config_path}")
        return
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    device = torch.device(config['train']['device'] if torch.cuda.is_available() else 'cpu')
    print(f"训练设备: {device}")

    # --- 2. 使用 data_loader 获取数据对 ---
    try:
        # get_siamese_data 会处理路径检查、加载、维度验证并移至 device
        data_orig, data_trans = get_siamese_data(config)
        print(f"数据加载成功: Orig节点={data_orig.x.size(0)}, Trans节点={data_trans.x.size(0)}")
    except Exception as e:
        print(f"数据处理异常: {e}")
        return
    
    train_labels = data_orig.y[data_orig.train_mask]
    n_count = (train_labels == 0).sum().item()
    tr_count = (train_labels == 1).sum().item()
    # 比例反转权重：正常节点越多，木马权重的倍数越高
    auto_trojan_w = max(n_count / (tr_count + 1e-6)*0.7, 1.0)
    auto_trojan_w = min(auto_trojan_w, 6.0) # 建议最高设为100倍，防止梯度爆炸
    print(f"检测到类别比例: {n_count}:{tr_count}, 动态木马权重设为: {auto_trojan_w:.2f}")

    # --- 3. 初始化模型与优化器 ---
    model = GINNodeClassifier(
        in_channels=config['model']['in_channels'],
        hidden_channels=config['model']['hidden_channels'],
        out_channels=config['model']['out_channels'],
        num_layers=config['model']['num_layers']
    ).to(device)
    
    optimizer = torch.optim.Adam(model.parameters(), 
                                 lr=float(config['train']['lr']), 
                                 weight_decay=float(config['train']['weight_decay']))
    
    history = {
        'epoch': [],
        'loss': [],
        'mac_orig': [],
        'mac_trans': [],
        'det_orig': [],
        'det_trans': [],
        'gap': []
    }

    # --- 4. 训练循环 ---
    best_val_score = 0
    os.makedirs('pytorch_models', exist_ok=True) # 确保文件夹存在
    print(f"开始训练: Lambda_const={config['siamese']['lambda_const']}, Epochs={config['train']['epochs']}")
    
    for epoch in range(config['train']['epochs']):
        model.train()
        optimizer.zero_grad()
        
        # 前向传播 (全图获取嵌入)
        preds_o_all = model(data_orig.x, data_orig.edge_index)
        preds_t_all = model(data_trans.x, data_trans.edge_index)

        l_det = config['siamese'].get('lambda_det', 2.0)
        current_lambda_const = config['siamese']['lambda_const'] if epoch > 20 else 0.0
        current_lambda_det = 0.5
        current_lambda_nor = 1.0 if epoch > 20 else 0
        current_trojan_w = 70.0
        # 核心：仅使用训练集掩码节点计算 Siamese Loss
        loss_val, smic_o, smac_o, smic_t, smac_t , sdr_o, sdr_t = siamese_loss(
            preds_o_all[data_orig.train_mask], 
            preds_t_all[data_trans.train_mask], 
            data_orig.y[data_orig.train_mask], 
            data_trans.y[data_trans.train_mask],
            lambda_const=0,
            lambda_det=0,
            lambda_nor=0,
            trojan_w=current_trojan_w # 传入自动权重
        )
        
        loss_val.backward()
        optimizer.step()
        
        # --- 5. 验证与日志记录 (每 10 轮) ---
        if (epoch + 1) % 10 == 0:
            model.eval()
            with torch.no_grad():
                # 计算验证集 (Val Set) 的真实硬 F1 分数
                val_preds_o = model(data_orig.x, data_orig.edge_index)[data_orig.val_mask]
                val_preds_t = model(data_trans.x, data_trans.edge_index)[data_trans.val_mask]
                
                mic_o, mac_o, det_o, tp_o, fp_o, tn_o, fn_o = calc_hard_f1(val_preds_o, data_orig.y[data_orig.val_mask])
                mic_t, mac_t, det_t, tp_t, fp_t, tn_t, fn_t = calc_hard_f1(val_preds_t, data_trans.y[data_trans.val_mask])
                
                mac_gap = abs(mac_o - mac_t)
                val_score = 2*(mac_o + mac_t) / 2 + (det_o + det_t) / 2

                history['epoch'].append(epoch + 1)
                history['loss'].append(loss_val.item())
                history['mac_orig'].append(mac_o)
                history['mac_trans'].append(mac_t)
                history['det_orig'].append(det_o)
                history['det_trans'].append(det_t)
                history['gap'].append(mac_gap)
                
                print(f"Epoch {epoch+1:03d} | Loss: {loss_val.item():.4f} | Gap: {mac_gap:.4f}")
                print(f"  [Val Orig]  Mac:{mac_o:.4f} | TP:{tp_o}, FP:{fp_o}, TN:{tn_o}, FN:{fn_o}")
                print(f"  [Val Trans] Mac:{mac_t:.4f} | TP:{tp_t}, FP:{fp_t}, TN:{tn_t}, FN:{fn_t}")
                print(f"  [Val Det Rate] Orig: {det_o:.4%} | Trans: {det_t:.4%}")

                if val_score > best_val_score:
                    best_val_score = val_score
                    torch.save(model.state_dict(), 'pytorch_models/best_siamese_gin.pkl')
                    print(f"  >>> Best Model Updated (Val Score: {val_score:.4f})")

    # --- 6. 最终测试 (使用全新的 Test Set) ---
    print("\n" + "="*30 + "\n训练完成，开始最终测试 (Test Set)\n" + "="*30)
    best_path = 'pytorch_models/best_siamese_gin.pkl'
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path))
        print(f"成功加载最优模型权重 (Best Val Score: {best_val_score:.4f})")
    else:
        print("警告: 未找到保存的最优模型，使用当前权重测试")

    model.eval()
    with torch.no_grad():
        test_preds_o = model(data_orig.x, data_orig.edge_index)[data_orig.test_mask]
        test_preds_t = model(data_trans.x, data_trans.edge_index)[data_trans.test_mask]
        
        t_mic_o, t_mac_o, t_det_o, tp_o, fp_o, tn_o, fn_o = calc_hard_f1(test_preds_o, data_orig.y[data_orig.test_mask])
        t_mic_t, t_mac_t, t_det_t, tp_t, fp_t, tn_t, fn_t = calc_hard_f1(test_preds_t, data_trans.y[data_trans.test_mask])

        
        print(f"Test Original    - Macro F1: {t_mac_o:.4f} | Det Rate: {t_det_o:.4%}")
        print(f"Test Transformed - Macro F1: {t_mac_t:.4f} | Det Rate: {t_det_t:.4%}")
        print(f"  [Val Orig]  TP:{tp_o}, FP:{fp_o}, TN:{tn_o}, FN:{fn_o}")
        print(f"  [Val Trans] TP:{tp_t}, FP:{fp_t}, TN:{tn_t}, FN:{fn_t}")
        print(f"Final Consistency Gap: {abs(t_mac_o - t_mac_t):.4f}")

    # print("\n正在分析特征贡献度...")
    # try:
    #     with open('./gatelookup_recommended.json', 'r') as f:
    #         gatelookup_raw = json.load(f)
    #         gatelookup = gatelookup_raw['gatelookup'] if 'gatelookup' in gatelookup_raw else gatelookup_raw

    #     importances = analyze_feature_importance_by_gradient(model, data_orig)
        
    #     if importances is not None:

    #         all_feature_names = get_feature_names(gatelookup) 
            
    #         plot_feature_importance(importances, all_feature_names, top_k=20)
    #         print("[成功] 特征重要性图已生成并保存为 feature_importance.png")
    # except Exception as e:
    #     print(f"[错误] 特征分析失败: {e}")



    # 保存模型权重
    save_dir = os.path.join(current_dir, 'pytorch_models')
    os.makedirs(save_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(save_dir, 'siamese_gin_model.pkl'))
    print(f"模型已保存至 {save_dir}")
    plot_training_metrics(history)

if __name__ == "__main__":
    train()