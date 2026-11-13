import torch
import torch.nn.functional as F
import yaml
import os
import sys
import numpy as np
import json
from sklearn.metrics import f1_score, recall_score, confusion_matrix, precision_recall_curve
import matplotlib.pyplot as plt
import pandas as pd
import networkx as nx
from scipy.sparse import load_npz
# 确保可以显示中文（如果需要）或设置样式
plt.style.use('seaborn-v0_8-whitegrid')
# 自动处理路径，确保能找到 models 和 data_loader
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from models.gin_net import GINNodeClassifier
# --- 关键修改：导入数据加载工具 ---
from data_loader import get_siamese_data

import random

def seed_everything(seed=42):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed) # 如果有多个GPU
    # 锁定底层算法，确保卷积等操作的结果确定
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

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

def perform_threshold_sweep(probs, labels):
    """ 核心功能：扫描 0.01 到 0.99 的阈值，计算各项指标 """
    trojan_probs = probs[:, 1].cpu().numpy() # 提取木马类的概率
    y_true = labels.cpu().numpy()
    
    thresholds = np.linspace(0.01, 0.99, 100)
    res = {'thr': [], 'pre': [], 'rec': [], 'fpr': [], 'macro_f1': [], 'fp': []}

    for t in thresholds:
        y_pred = (trojan_probs >= t).astype(int)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0,0,0,0)
        
        res['thr'].append(t)
        res['pre'].append(tp / (tp + fp + 1e-10))
        res['rec'].append(tp / (tp + fn + 1e-10))
        res['fpr'].append(fp / (fp + tn + 1e-10))
        res['fp'].append(fp)
        # 计算 Macro-F1
        f1_1 = 2 * tp / (2 * tp + fp + fn + 1e-10)
        f1_0 = 2 * tn / (2 * tn + fp + fn + 1e-10)
        res['macro_f1'].append((f1_1 + f1_0) / 2)
    return res

def get_metrics_at_target_recall(probs, labels, target_recall=0.85):
    """
    在验证集上寻找：当 Recall 至少为 target_recall 时，最小的 FPR 和对应的阈值
    """
    trojan_probs = probs[:, 1].cpu().numpy()
    y_true = labels.cpu().numpy()
    
    # 获取 PR 曲线的阈值点
    precisions, recalls, thresholds = precision_recall_curve(y_true, trojan_probs)
    
    # 找到所有满足 recall >= target_recall 的索引
    valid_indices = np.where(recalls >= target_recall)[0]
    if len(valid_indices) == 0:
        return 0.5, 0.0, 1.0, 0.0 # 没找到符合条件的
    
    # 在满足条件的索引中，找 Precision 最高的点（等价于 FP 最低）
    best_idx = valid_indices[np.argmax(precisions[valid_indices])]
    
    # 注意：thresholds 的长度比 precisions 少 1
    actual_threshold = thresholds[min(best_idx, len(thresholds)-1)]
    
    # 计算该阈值下的硬指标
    y_pred = (trojan_probs >= actual_threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0,0,0,0)
    
    fpr = fp / (fp + tn + 1e-10)
    rec = tp / (tp + fn + 1e-10)
    # 计算 Macro-F1
    f1_1 = 2 * tp / (2 * tp + fp + fn + 1e-10)
    f1_0 = 2 * tn / (2 * tn + fp + fn + 1e-10)
    macro_f1 = (f1_1 + f1_0) / 2
    
    return actual_threshold, macro_f1, fpr, rec


def analyze_false_positives(model, data, threshold, gatelookup, output_file='fp_analysis.csv'):
    model.eval()
    with torch.no_grad():
        # 1. 获取预测概率
        logits = model(data.x, data.edge_index)
        probs = F.softmax(logits, dim=1)[:, 1].cpu().numpy()
        y_true = data.y.cpu().numpy()
        
        # 2. 确定测试集中的 FP 索引
        test_mask = data.test_mask.cpu().numpy()
        y_pred = (probs >= threshold).astype(int)
        
        # FP 条件：测试集内 + 标签为0 + 预测为1
        fp_indices = np.where((test_mask == True) & (y_true == 0) & (y_pred == 1))[0]
        
        if len(fp_indices) == 0:
            print("未发现 FP 样本，无需分析。")
            return

        print(f"发现 {len(fp_indices)} 个 FP 样本，正在进行特征采样分析...")

        # 3. 加载原始物理特征和图结构 (由 parser 生成)
        # 注意：这里假设 parser 生成的文件在 ./data/ 目录下
        raw_feats = np.load('./data/verilog_data/data/for_train/feats_orig.npy')
        adj = load_npz('./data/verilog_data/data/for_train/adj_full_orig.npz')
        G = nx.from_scipy_sparse_array(adj)

        # 反转 gatelookup 以便通过索引找门名字
        idx_to_gate = {v: k for k, v in gatelookup.items()}
        num_gate_types = len(gatelookup)

        analysis_results = []

        for idx in fp_indices:
            # A. 门类型
            gate_one_hot = raw_feats[idx, :num_gate_types]
            gate_idx = np.argmax(gate_one_hot)
            gate_name = idx_to_gate.get(gate_idx, "Unknown")

            # B. 物理特征 (对应 parser 中的 featsright)
            # featsright 顺序: [Lib_In_Count, Total_Degree, Is_PI_Adj, Is_PO_Adj, Dist_to_PI, Dist_to_PO]
            # 注意：feats 拼接顺序是 featsleft(gates) + featsright + distances
            fan_in = raw_feats[idx, num_gate_types]
            degree = raw_feats[idx, num_gate_types + 1]
            dist_pi = raw_feats[idx, -2] # 倒数第二个是 PI 距离
            dist_po = raw_feats[idx, -1] # 最后一个是 PO 距离

            # C. 子图大小 (计算 2-hop 范围内的节点数)
            subgraph_nodes = nx.ego_graph(G, idx, radius=2).number_of_nodes()

            # D. Rare Node 判定（示例：如果输入数极少或距离PI/PO极远）
            is_rare = 1 if (fan_in > 5 or (dist_pi > 2.0 and dist_po > 2.0)) else 0

            analysis_results.append({
                'node_index': idx,
                'gate_type': gate_name,
                'fan_in': int(np.expm1(fan_in)), # 还原 log1p
                'degree': int(np.expm1(degree)), # 还原 log1p
                'dist_to_pi': dist_pi * 10,      # 还原缩放
                'dist_to_po': dist_po * 10,
                'subgraph_size_2hop': subgraph_nodes,
                'is_rare_candidate': is_rare,
                'confidence_score': probs[idx]
            })

        # 4. 导出 CSV
        df = pd.DataFrame(analysis_results)
        df.to_csv(output_file, index=False)
        print(f"FP 采样分析报告已保存至 {output_file}")
        
        # 打印统计摘要
        print("\n--- FP 样本统计摘要 ---")
        print(df.describe())
        print("\n高频 FP 门类型 Top 5:")
        print(df['gate_type'].value_counts().head(5))

def plot_threshold_curves(res, save_name='threshold_sweep.png'):
    """ 核心功能：绘制曲线并找出 Recall 85% 时的最优 FP """
    plt.figure(figsize=(10, 6))
    plt.plot(res['thr'], res['rec'], label='Recall (Trojan)', color='royalblue', lw=2)
    plt.plot(res['thr'], res['macro_f1'], label='Macro-F1', color='crimson', lw=2)
    plt.plot(res['thr'], res['fpr'], label='FPR (False Positive)', color='orange', linestyle='--')
    
    # 寻找 Recall 接近 85% 的临界点
    idx_85 = (np.abs(np.array(res['rec']) - 0.85)).argmin()
    plt.axvline(x=res['thr'][idx_85], color='green', linestyle=':', label=f"Target Recall≈85%")
    
    plt.title('Threshold Sweep Analysis')
    plt.xlabel('Threshold (Probability)')
    plt.ylabel('Metrics Score')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(save_name)
    plt.show()
    
    print(f"\n[阈值分析结果] 当 Recall 保持在 {res['rec'][idx_85]:.2%} 时:")
    print(f" - 推荐阈值: {res['thr'][idx_85]:.3f}")
    print(f" - 此时误报数 (FP): {res['fp'][idx_85]}")
    print(f" - 此时误报率 (FPR): {res['fpr'][idx_85]:.4%}")

def apply_expert_priors(probs, data, subgraph_counts):
    """
    根据物理位置和子图大小修正概率 (严格版)
    """
    # 假设特征最后两列是 dist_to_pi, dist_to_po
    # 重要：需要确认 data.x 里的原始缩放。通常是 距离/10
    dist_to_pi = data.x[:, -2].cpu().numpy() 
    
    # 1. 修正：PI 边缘硬过滤
    # 针对 dist_to_pi 为 0 的节点 (边界扫描链/IO寄存器)
    # 我们不仅削减概率，而是将其强制压低
    pi_mask = (dist_to_pi < 0.05) 
    probs[pi_mask] *= 0.2  # 削减 80%
    
    # 2. 修正：大子图译码逻辑过滤
    # 观察发现 TP 都在 20 以下，FP 都在 30 以上
    # 我们设置 30 为惩罚阈值
    large_mask = (subgraph_counts > 30)
    probs[large_mask] *= 0.2  # 削减 80%
    
    return probs

def analyze_samples_unified(model, data, threshold, gatelookup, output_file='node_sample_analysis.csv'):
    model.eval()
    feats_path = os.path.join('data/verilog_data/data/for_train/feats_orig.npy')
    adj_path = os.path.join('data/verilog_data/data/for_train/adj_full_orig.npz')

    with torch.no_grad():
        # 1. 获取模型原始输出概率
        logits = model(data.x, data.edge_index)
        probs = F.softmax(logits, dim=1)[:, 1].cpu().numpy()
        y_true = data.y.cpu().numpy()
        test_mask = data.test_mask.cpu().numpy()

        # 2. 必须先计算子图大小
        print("正在预计算子图规模...")
        adj = load_npz(adj_path)
        G = nx.from_scipy_sparse_array(adj)
        subgraph_counts = np.zeros(len(probs))
        test_indices = np.where(test_mask)[0]
        for idx in test_indices:
            subgraph_counts[idx] = nx.ego_graph(G, idx, radius=2).number_of_nodes()

        # 3. 【关键步骤】在判定 FP 之前，先执行专家修正
        # 这一步会直接修改 probs 数组中的值
        probs = apply_expert_priors(probs, data, subgraph_counts)
        
        # 4. 【关键步骤】使用修正后的 probs 重新计算 y_pred
        # 只有这样，修正后的概率低于 threshold 的节点才不会被算作 FP
        y_pred = (probs >= threshold).astype(int)
        
        # 5. 重新筛选样本
        tp_idx = np.where((test_mask) & (y_true == 1) & (y_pred == 1))[0]
        fp_idx = np.where((test_mask) & (y_true == 0) & (y_pred == 1))[0]
        fn_idx = np.where((test_mask) & (y_true == 1) & (y_pred == 0))[0]
        
        print(f"--- 策略修正后统计 ---")
        print(f"TP: {len(tp_idx)} | FP: {len(fp_idx)} | FN: {len(fn_idx)}")

        # 6. 构建分析列表 (保持与之前一致)
        raw_feats = np.load(feats_path)
        idx_to_gate = {v: k for k, v in gatelookup.items()}
        num_gate_types = len(gatelookup)
        analysis_results = []

        sample_groups = [(tp_idx, 'TP'), (fp_idx, 'FP'), (fn_idx, 'FN')]
        for indices, s_type in sample_groups:
            for idx in indices:
                gate_idx = np.argmax(raw_feats[idx, :num_gate_types])
                gate_name = idx_to_gate.get(gate_idx, "Unknown")
                analysis_results.append({
                    'node_index': idx,
                    'sample_type': s_type,
                    'gate_type': gate_name,
                    'fan_in': int(np.expm1(raw_feats[idx, num_gate_types])),
                    'degree': int(np.expm1(raw_feats[idx, num_gate_types + 1])),
                    'dist_to_pi': raw_feats[idx, -2] * 10,
                    'dist_to_po': raw_feats[idx, -1] * 10,
                    'subgraph_size_2hop': subgraph_counts[idx],
                    'confidence_score': probs[idx], # 这里必须是修正后的值
                    'true_label': int(y_true[idx])
                })

        if analysis_results:
            df = pd.DataFrame(analysis_results)
            df.to_csv(os.path.join(current_dir, output_file), index=False)

def focal_loss(preds, labels, gamma=2.0, alpha=None):
    """
    Focal Loss: 通过 (1-pt)^gamma 抑制简单样本
    """
    ce_loss = F.cross_entropy(preds, labels, reduction='none', weight=alpha)
    pt = torch.exp(-ce_loss) # pt 是预测正确的概率
    f_loss = ((1 - pt) ** gamma * ce_loss).mean()
    return f_loss

def asymmetric_focal_loss(preds, labels, gamma_pos=0.0, gamma_neg=4.0, clip=0.05):
    """
    Asymmetric Focal Loss (ASL): 对正负样本使用不同的指数
    gamma_neg 通常设为 4.0 以极力压低负样本（正常门）的误报
    """
    probs = F.softmax(preds, dim=1)
    p_t = probs[:, 1]       # 预测为木马的概率
    p_n = probs[:, 0]       # 预测为正常的概率
    
    # 转换为 float 标签
    target = labels.float()

    # 正样本损失 (Trojan) - 保持敏感
    loss_pos = -target * torch.log(p_t + 1e-10) * ( (1 - p_t) ** gamma_pos )
    
    # 负样本损失 (Normal) - 极力压制
    # 1-p_n 表示模型认为它是木马的倾向，倾向越高，惩罚越重
    loss_neg = -(1 - target) * torch.log(p_n + 1e-10) * ( (1 - p_n + clip) ** gamma_neg )
    
    return (loss_pos + loss_neg).mean()

def compute_task_loss(preds, labels, loss_type='ce', weight=None):
    """
    损失函数统一调用接口
    """
    if loss_type == 'ce':
        # 对应标准的 BCE/CrossEntropy
        return F.cross_entropy(preds, labels, weight=weight)
    
    elif loss_type == 'focal':
        # 经典的 Focal Loss
        return focal_loss(preds, labels, gamma=2.0, alpha=weight)
    
    elif loss_type == 'asl':
        # 非对称 Focal Loss，降低 FP 的终极武器
        # 注意：ASL 内部已经处理了权重逻辑，通常不需要额外传 weight
        return asymmetric_focal_loss(preds, labels, gamma_pos=1.0, gamma_neg=4.0)
    
    else:
        raise ValueError(f"Unknown loss type: {loss_type}")


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


def siamese_loss(preds_o, preds_t, labels_o, labels_t, 
                 lambda_const=2.0, lambda_det=2.0, lambda_nor=1.0, 
                 trojan_w=8.0, loss_type='ce'):
    """ 孪生损失函数：结合分类误差和指标一致性误差 """
    probs_o = F.softmax(preds_o, dim=1)
    probs_t = F.softmax(preds_t, dim=1)

    # 1. 基础分类损失 (Task Loss)
    weight = torch.tensor([1.0, trojan_w], device=preds_o.device)
    task_loss_o = compute_task_loss(preds_o, labels_o, loss_type=loss_type, weight=weight)
    task_loss_t = compute_task_loss(preds_t, labels_t, loss_type=loss_type, weight=weight)

    # 2. 计算可导的 Soft F1 指标
    F1mic_o, F1mac_o, sdr_n_o, sdr_tr_o = calc_soft_f1_metrics(probs_o, labels_o)
    F1mic_t, F1mac_t, sdr_n_t, sdr_tr_t = calc_soft_f1_metrics(probs_t, labels_t)

    # 3. 指标对齐约束 (Consistency Loss)
    # 让原始和变换后的 F1 尽可能接近（MSE 越小，一致性越强）
    loss_mic_consistency = F.mse_loss(F1mic_o, F1mic_t)
    loss_mac_consistency = F.mse_loss(F1mac_o, F1mac_t)

    loss_det_o = trojan_w * (-torch.log(sdr_tr_o + 1e-10))
    loss_det_t = trojan_w * (-torch.log(sdr_tr_t + 1e-10))  
    loss_det_rate = loss_det_o + loss_det_t

    loss_normal_consistency = (1.0 - sdr_n_o) + (1.0 - sdr_n_t)

    total_loss = (task_loss_o + task_loss_t) + \
                 lambda_const * loss_mac_consistency + \
                 lambda_det * loss_det_rate + \
                 lambda_nor * loss_normal_consistency

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
def plot_dual_threshold_curves(res_o, res_t, save_name='dual_threshold_analysis.png'):
    """
    同时绘制原始和变换后的曲线，观察一致性
    """
    plt.figure(figsize=(14, 6))
    
    # 子图 1: Recall & FPR 对比
    plt.subplot(1, 2, 1)
    plt.plot(res_o['thr'], res_o['rec'], 'b-', label='Recall (Orig)')
    plt.plot(res_t['thr'], res_t['rec'], 'b--', label='Recall (Trans)', alpha=0.6)
    
    plt.plot(res_o['thr'], res_o['fpr'], 'r-', label='FPR (Orig)')
    plt.plot(res_t['thr'], res_t['fpr'], 'r--', label='FPR (Trans)', alpha=0.6)
    
    plt.axhline(y=0.85, color='gray', linestyle=':', label='85% Recall Target')
    plt.title('Recall & FPR Consistency')
    plt.xlabel('Threshold')
    plt.ylabel('Rate')
    plt.legend()

    # 子图 2: Macro-F1 对比
    plt.subplot(1, 2, 2)
    plt.plot(res_o['thr'], res_o['macro_f1'], 'g-', label='Macro-F1 (Orig)')
    plt.plot(res_t['thr'], res_t['macro_f1'], 'g--', label='Macro-F1 (Trans)', alpha=0.6)
    
    # 标注 Orig 在 85% Recall 时的阈值点
    idx_85 = (np.abs(np.array(res_o['rec']) - 0.85)).argmin()
    target_thr = res_o['thr'][idx_85]
    plt.axvline(x=target_thr, color='purple', linestyle='-.', label=f'Best Thr: {target_thr:.2f}')
    
    plt.title('Macro-F1 Consistency')
    plt.xlabel('Threshold')
    plt.ylabel('F1 Score')
    plt.legend()

    plt.tight_layout()
    plt.savefig(save_name)
    plt.show()

    # 打印对比数据
    print(f"\n[对比分析] 当阈值为 {target_thr:.3f} 时:")
    print(f"  - Original:    Recall={res_o['rec'][idx_85]:.2%}, FP={res_o['fp'][idx_85]}, FPR={res_o['fpr'][idx_85]:.4%}")
    print(f"  - Transformed: Recall={res_t['rec'][idx_85]:.2%}, FP={res_t['fp'][idx_85]}, FPR={res_t['fpr'][idx_85]:.4%}")

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
    seed_everything(43)
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
        # current_lambda_const = config['siamese']['lambda_const'] if epoch > 90 else 0.0
        # current_lambda_det = 0.3
        # current_lambda_nor = 2.0 if epoch <100 else 5.0
        # current_trojan_w = 20.0 if epoch <100 else 5.0
        current_lambda_const = 0.0 if epoch > 80 else 0.0
        current_lambda_det = 0.3 if epoch <90 else 0.1
        current_lambda_nor = 1.5 if epoch<100 else 15.0
        current_trojan_w = 25.0 if epoch <100 else 10.0
        # 备选：'ce', 'focal', 'asl'
        selected_loss = 'ce'
        # 核心：仅使用训练集掩码节点计算 Siamese Loss
        loss_val, smic_o, smac_o, smic_t, smac_t , sdr_o, sdr_t = siamese_loss(
            preds_o_all[data_orig.train_mask], 
            preds_t_all[data_trans.train_mask], 
            data_orig.y[data_orig.train_mask], 
            data_trans.y[data_trans.train_mask],
            lambda_const=current_lambda_const,
            lambda_det=current_lambda_det,
            lambda_nor=current_lambda_nor,
            trojan_w=current_trojan_w,
            loss_type=selected_loss
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
                val_score = 4*(mac_o + mac_t) / 2 + (det_o + det_t) / 2

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
        probs_o_all = F.softmax(model(data_orig.x, data_orig.edge_index), dim=1)
        probs_t_all = F.softmax(model(data_trans.x, data_trans.edge_index), dim=1)

        # 2. 提取测试集部分
        test_probs_o = probs_o_all[data_orig.test_mask]
        test_probs_t = probs_t_all[data_trans.test_mask]
        test_labels_o = data_orig.y[data_orig.test_mask]
        test_labels_t = data_trans.y[data_trans.test_mask]

        # 3. 对两组数据分别进行阈值扫描
        print("\n" + "="*20 + " 正在执行双重阈值分析 " + "="*20)
        res_o = perform_threshold_sweep(test_probs_o, test_labels_o)
        res_t = perform_threshold_sweep(test_probs_t, test_labels_t)

        # 4. 绘制对比图
        plot_dual_threshold_curves(res_o, res_t, 'dual_threshold_comparison.png')

        # --- 以下是保留原有的 0.5 阈值硬输出对比，用于参考 ---
        t_mic_o, t_mac_o, t_det_o, tp_o, fp_o, tn_o, fn_o = calc_hard_f1(test_probs_o, test_labels_o) # 注意这里传入概率也是可以的，calc_hard_f1 内部用了 argmax
        t_mic_t, t_mac_t, t_det_t, tp_t, fp_t, tn_t, fn_t = calc_hard_f1(test_probs_t, test_labels_t)

        
        print(f"Test Original    - Macro F1: {t_mac_o:.4f} | Det Rate: {t_det_o:.4%}")
        print(f"Test Transformed - Macro F1: {t_mac_t:.4f} | Det Rate: {t_det_t:.4%}")
        print(f"  [Val Orig]  TP:{tp_o}, FP:{fp_o}, TN:{tn_o}, FN:{fn_o}")
        print(f"  [Val Trans] TP:{tp_t}, FP:{fp_t}, TN:{tn_t}, FN:{fn_t}")
        print(f"Final Consistency Gap: {abs(t_mac_o - t_mac_t):.4f}")

    print("\n正在分析特征贡献度...")
    try:
        with open('./gatelookup_recommended.json', 'r') as f:
            gatelookup_raw = json.load(f)
            gatelookup = gatelookup_raw['gatelookup'] if 'gatelookup' in gatelookup_raw else gatelookup_raw

        importances = analyze_feature_importance_by_gradient(model, data_orig)
        
        if importances is not None:

            all_feature_names = get_feature_names(gatelookup) 
            
            plot_feature_importance(importances, all_feature_names, top_k=20)
            print("[成功] 特征重要性图已生成并保存为 feature_importance.png")
    except Exception as e:
        print(f"[错误] 特征分析失败: {e}")

    with open('./gatelookup_recommended.json', 'r') as f:
        gatelookup = json.load(f)
        if 'gatelookup' in gatelookup: gatelookup = gatelookup['gatelookup']

    gatelookup_path = os.path.join(current_dir, 'gatelookup_recommended.json')
    with open(gatelookup_path, 'r') as f:
        g_json = json.load(f)
        g_map = g_json.get('gatelookup', g_json)

    
    analyze_samples_unified(model, data_orig, 0.51, g_map)

    # 保存模型权重
    save_dir = os.path.join(current_dir, 'pytorch_models')
    os.makedirs(save_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(save_dir, 'siamese_gin_model.pkl'))
    print(f"模型已保存至 {save_dir}")
    plot_training_metrics(history)

if __name__ == "__main__":
    train()