import torch
import torch.nn.functional as F
import yaml
import os
import sys
import numpy as np
import json
from sklearn.metrics import f1_score, recall_score, confusion_matrix, precision_recall_curve
from sklearn.metrics import average_precision_score, precision_score
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
            dist_pi = raw_feats[idx, -4] # 倒数第二个是 PI 距离
            dist_po = raw_feats[idx, -3] # 最后一个是 PO 距离

            # C. 子图大小 (计算 2-hop 范围内的节点数)
            subgraph_nodes = nx.ego_graph(G, idx, radius=2).number_of_nodes()

            # D. Rare Node 判定（示例：如果输入数极少或距离PI/PO极远）
            is_rare = 1 if (fan_in > 5 or (dist_pi > 2.0 and dist_po > 2.0)) else 0

            analysis_results.append({
                'node_index': idx,
                'gate_type': gate_name,
                'fan_in': int(np.expm1(fan_in)), # 还原 log1p
                'degree': int(np.expm1(degree)), # 还原 log1p
                'dist_to_pi': dist_pi,      
                'dist_to_po': dist_po,
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

    
    # --- 修正逻辑 2: 大子图译码逻辑过滤 ---
    # 之前的分析显示 TP 都在 20 以下，FP 大多 > 30
    
    # --- 修正逻辑 3: 高扇出(Fan-out)节点过滤 [新增] ---
    # 木马触发器为了隐蔽，通常 Fan-out 极小（只触发一个 Payload）
    # 如果一个节点在 2-hop 内驱动了大量节点 (例如 > 20个)，基本可以断定是功能逻辑或时钟树
    # 这里的 np.log1p(20) 约为 3.04
    
    return probs

def analyze_samples_unified(model, data, threshold, gatelookup, mask_type='test'):
    """
    统一分析函数
    mask_type: 'test' 或 'val'
    """
    model.eval()
    # 动态确定输出文件名
    output_file = f'node_sample_analysis_{mask_type}.csv'
    
    # 路径处理
    feats_path = os.path.join('data/verilog_data/data/for_train/feats_orig.npy')
    adj_path = os.path.join('data/verilog_data/data/for_train/adj_full_orig.npz')

    with torch.no_grad():
        # 1. 获取模型概率
        logits = model(data.x, data.edge_index)
        probs = F.softmax(logits, dim=1)[:, 1].cpu().numpy()
        y_true = data.y.cpu().numpy()
        
        # 2. 根据 mask_type 选择掩码
        if mask_type == 'val':
            mask = data.val_mask.cpu().numpy()
        else:
            mask = data.test_mask.cpu().numpy()
            
        # 3. 预计算子图大小（仅针对当前掩码覆盖的节点）
        print(f"正在分析 {mask_type.upper()} 集合，预计算子图规模...")
        adj = load_npz(adj_path)
        G = nx.from_scipy_sparse_array(adj)
        subgraph_counts = np.zeros(len(probs))
        indices_to_check = np.where(mask)[0]
        for idx in indices_to_check:
            subgraph_counts[idx] = nx.ego_graph(G, idx, radius=2).number_of_nodes()

        # 4. 执行专家修正
        probs = apply_expert_priors(probs, data, subgraph_counts)
        
        # 5. 判定预测结果
        y_pred = (probs >= threshold).astype(int)
        
        # 6. 分类筛选样本 (基于当前掩码)
        tp_idx = np.where((mask) & (y_true == 1) & (y_pred == 1))[0]
        fp_idx = np.where((mask) & (y_true == 0) & (y_pred == 1))[0]
        fn_idx = np.where((mask) & (y_true == 1) & (y_pred == 0))[0]
        
        print(f"\n[{mask_type.upper()} 修正后统计] TP: {len(tp_idx)} | FP: {len(fp_idx)} | FN: {len(fn_idx)}")

        # 7. 构建结果列表
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
                    'dist_to_pi': raw_feats[idx, -5],
                    'dist_to_po': raw_feats[idx, -4],
                    'fan_in_2hop': int(np.expm1(raw_feats[idx, -3])),
                    'fan_out_2hop': int(np.expm1(raw_feats[idx, -2])),
                    'in_out_ratio': int(np.expm1(raw_feats[idx, -1])),
                    'subgraph_size_2hop': subgraph_counts[idx],
                    'confidence_score': probs[idx],
                    'true_label': int(y_true[idx])
                })

        if analysis_results:
            df = pd.DataFrame(analysis_results)
            df.to_csv(os.path.join(current_dir, output_file), index=False)
            print(f"[成功] {mask_type.upper()} 分析报告已保存至 {output_file}")

def plot_score_distribution(tp_scores, fp_scores, tn_scores, fn_scores, threshold, save_name='score_distribution.png'):
    """
    绘制 TP, FP, TN, FN 四类样本的分数分布图
    """
    plt.figure(figsize=(12, 7))
    
    # 设置 bins 确保对比清晰
    bins = np.linspace(0, 1, 50)
    
    # 绘制分布
    # 我们通常最关注 TP 和 FP 的重叠
    plt.hist(tn_scores, bins=bins, alpha=0.3, label=f'TN (Normal-Right) n={len(tn_scores)}', color='gray', density=True)
    plt.hist(fn_scores, bins=bins, alpha=0.5, label=f'FN (Trojan-Missed) n={len(fn_scores)}', color='orange', density=True)
    plt.hist(fp_scores, bins=bins, alpha=0.5, label=f'FP (Normal-Mistaken) n={len(fp_scores)}', color='red', density=True)
    plt.hist(tp_scores, bins=bins, alpha=0.7, label=f'TP (Trojan-Right) n={len(tp_scores)}', color='green', density=True)
    
    # 画出当前使用的阈值线
    plt.axvline(threshold, color='black', linestyle='--', linewidth=2, label=f'Threshold: {threshold}')
    
    plt.title('Score Distribution by Prediction Category (Test Set)', fontsize=15)
    plt.xlabel('Trojan Probability Score', fontsize=12)
    plt.ylabel('Density', fontsize=12)
    plt.legend(loc='upper center')
    plt.grid(axis='y', alpha=0.3)
    
    # 重点标注重叠区域
    plt.text(threshold+0.02, plt.gca().get_ylim()[1]*0.8, '← Trojan Region', color='green', fontweight='bold')
    plt.text(threshold-0.18, plt.gca().get_ylim()[1]*0.8, 'Benign Region →', color='red', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(save_name)
    print(f"[成功] 分数分布图已保存为 {save_name}")
    plt.show()

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

def calculate_full_metrics(probs, labels, threshold):
    """
    probs: [N, 2] tensor or ndarray
    labels: [N] tensor or ndarray
    threshold: float
    """
    if torch.is_tensor(probs): probs = probs.detach().cpu().numpy()
    if torch.is_tensor(labels): labels = labels.detach().cpu().numpy()
    
    scores = probs[:, 1]
    preds = (scores >= threshold).astype(int)
    
    # 基础混淆矩阵
    cm = confusion_matrix(labels, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0,0,0,0)
    
    # 计算各项指标
    rec = recall_score(labels, preds, zero_division=0)
    pre = precision_score(labels, preds, zero_division=0)
    fpr = fp / (fp + tn + 1e-10)
    mac_f1 = f1_score(labels, preds, average='macro')
    # PR-AUC (即 Average Precision)
    pr_auc = average_precision_score(labels, scores)
    
    return {
        'Recall': rec,
        'Precision': pre,
        'FPR': fpr,
        'Macro-F1': mac_f1,
        'PR-AUC': pr_auc,
        'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn
    }

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


def siamese_loss(preds_o, preds_t, labels_o, labels_t, data_o, data_t,
                 lambda_const=2.0, lambda_det=2.0, lambda_nor=1.0, lambda_pos=10.0,
                 trojan_w=8.0, loss_type='ce', use_hnm=False):
    """ 孪生损失函数：结合分类误差和指标一致性误差 """
    T = 0.5 
    probs_o = F.softmax(preds_o / T, dim=1)
    probs_t = F.softmax(preds_t / T, dim=1)

    # 1. 基础分类损失 (Task Loss)
    weight = torch.tensor([1.0, trojan_w], device=preds_o.device)
    if use_hnm:
        task_loss_o = hnm_loss(preds_o, labels_o, mining_ratio=0.1, hard_weight=10.0, base_weight=weight)
        task_loss_t = hnm_loss(preds_t, labels_t, mining_ratio=0.1, hard_weight=10.0, base_weight=weight)
    else:
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
    loss_det_rate = loss_det_o

    loss_normal_consistency = (1.0 - sdr_n_o)

    # 2. 新增：位置惩罚项 (Location Penalty)
    # 根据 33 维特征，dist_to_pi 索引为 29
    dist_pi_o = data_o.x[data_o.train_mask][:, 29]
    dist_pi_t = data_t.x[data_t.train_mask][:, 29]
    penalty_o = torch.mean(probs_o[:, 1] * torch.exp(-5.0 * dist_pi_o))
    penalty_t = torch.mean(probs_t[:, 1] * torch.exp(-5.0 * dist_pi_t))
    location_loss = penalty_o

    total_loss = (task_loss_o) + \
                 lambda_const * loss_mac_consistency + \
                 lambda_det * loss_det_rate + \
                 lambda_nor * loss_normal_consistency + \
                 lambda_pos * location_loss

    return total_loss, F1mic_o, F1mac_o, F1mic_t, F1mac_t, sdr_tr_o, sdr_tr_t

def hnm_loss(preds, labels, mining_ratio=0.1, hard_weight=5.0, base_weight=None):
    """
    在线困难负样本挖掘损失
    mining_ratio: 挖掘正常节点中前 10% 的困难样本
    hard_weight: 困难样本的额外权重倍数
    """
    # 计算原始交叉熵 (不进行 mean 缩放)
    ce_loss = F.cross_entropy(preds, labels, reduction='none', weight=base_weight)
    
    probs = F.softmax(preds, dim=1)
    trojan_probs = probs[:, 1]
    
    # 创建掩码：只针对正常节点 (label=0)
    normal_mask = (labels == 0)
    trojan_mask = (labels == 1)
    
    # 在正常节点中寻找“困难样本”：即预测木马概率最高的那些
    normal_probs = trojan_probs[normal_mask]
    if len(normal_probs) > 0:
        # 计算需要挖掘的数量
        k = max(1, int(len(normal_probs) * mining_ratio))
        # 找到概率最高的前 k 个值的阈值
        top_k_threshold = torch.topk(normal_probs, k).values[-1]
        
        # 判定哪些是困难负样本
        hard_neg_mask = normal_mask & (trojan_probs >= top_k_threshold)
        
        # 赋予权重：木马节点保持原重，困难正常节点 * hard_weight，普通正常节点 1.0
        weights = torch.ones_like(labels, dtype=torch.float)
        weights[hard_neg_mask] = hard_weight
        
        return (ce_loss * weights).mean()
    
    return ce_loss.mean()

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
    return target_thr

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

def plot_confusion_matrix_comparison(cm_std, cm_hnm, save_name='cm_comparison.png'):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    labels = ['Benign', 'Trojan']
    
    for ax, cm, title in zip(axes, [cm_std, cm_hnm], ['Standard Training', 'HNM Training']):
        im = ax.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        ax.set_title(title)
        fig.colorbar(im, ax=ax)
        tick_marks = np.arange(len(labels))
        ax.set_xticks(tick_marks, labels)
        ax.set_yticks(tick_marks, labels)
        
        # 标注数值
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black")
        
        ax.set_ylabel('True Label')
        ax.set_xlabel('Predicted Label')

    plt.tight_layout()
    plt.savefig(save_name)
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
    print(f"开始训练: Epochs={config['train']['epochs']}")
    
    for epoch in range(config['train']['epochs']):
        model.train()
        optimizer.zero_grad()
        
        # 前向传播 (全图获取嵌入)
        preds_o_all = model(data_orig.x, data_orig.edge_index)
        preds_t_all = model(data_trans.x, data_trans.edge_index)

        l_det = config['siamese'].get('lambda_det', 2.0)

        # in/out
        current_lambda_const = 0 if epoch > 0 else 0.0
        current_lambda_det = 0.2
        current_lambda_nor = 3.0
        current_lambda_pos = 20.0
        current_trojan_w = 25.0 if epoch <70 else 25.0

        # 2-hop+hnm
        # current_lambda_const = 0.0 if epoch > 80 else 0.0
        # current_lambda_det = 0.3
        # current_lambda_nor = 1.5
        # current_lambda_pos = 10.0
        # current_trojan_w = 25.0

        # 2-hop+nor
        # current_lambda_const = 0.0 if epoch > 80 else 0.0
        # current_lambda_det = 0.25
        # current_lambda_nor = 3.0
        # current_trojan_w = 25.0
        
        # normal
        # current_lambda_const = 0.0 if epoch > 80 else 0.0
        # current_lambda_det = 0.3
        # current_lambda_nor = 3.0
        # current_trojan_w = 25.0
        # current_lambda_pos = 0
        # hnm
        # current_lambda_const = 0.0 if epoch > 80 else 0.0
        # current_lambda_det = 0.3 if epoch <90 else 0.1
        # current_lambda_nor = 1.5 if epoch<100 else 15.0
        # current_trojan_w = 25.0 if epoch <100 else 10.0
        hnm_enabled = True if epoch >= 80 else False
        # 备选：'ce', 'focal', 'asl'
        selected_loss = 'ce'
        # 核心：仅使用训练集掩码节点计算 Siamese Loss
        loss_val, smic_o, smac_o, smic_t, smac_t , sdr_o, sdr_t = siamese_loss(
            preds_o_all[data_orig.train_mask], 
            preds_t_all[data_trans.train_mask], 
            data_orig.y[data_orig.train_mask], 
            data_trans.y[data_trans.train_mask],
            data_orig,
            data_trans,
            lambda_const=current_lambda_const,
            lambda_det=current_lambda_det,
            lambda_nor=current_lambda_nor,
            lambda_pos=current_lambda_pos,
            trojan_w=current_trojan_w,
            loss_type=selected_loss,
            use_hnm=hnm_enabled
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
                val_score = 2*(mac_o) / 2 + (det_o) / 2

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


    # 2. 统一加载 gatelookup (修复 UnboundLocalError)
    g_map = {}
    gatelookup_path = os.path.join(current_dir, 'gatelookup_recommended.json')
    try:
        with open(gatelookup_path, 'r') as f:
            g_json = json.load(f)
            g_map = g_json.get('gatelookup', g_json)
    except Exception as e:
        print(f"警告: 无法加载门映射表: {e}")

    model.eval()
    with torch.no_grad():
        # A. 确定阈值：在 Validation Set 上寻找使 Recall ≈ 85% 的最优阈值
        val_probs_o = F.softmax(model(data_orig.x, data_orig.edge_index)[data_orig.val_mask], dim=1)
        test_probs_o = F.softmax(model(data_orig.x, data_orig.edge_index)[data_orig.test_mask], dim=1)
        # 使用你定义的扫频函数
        final_thr, _, _, _ = get_metrics_at_target_recall(val_probs_o, data_orig.y[data_orig.val_mask], target_recall=0.85)
        print(f"\n[Val Protocol] 基于验证集确定的最优阈值: {final_thr:.4f}")

        # best_thr, _, _, _ = get_metrics_at_target_recall(test_probs_o, data_orig.y[data_orig.test_mask], target_recall=0.85)
        # print(f"\n[Val Protocol] 测试集的最优阈值: {best_thr:.4f}")

        # B. 运行测试集推理
        test_logits_o = model(data_orig.x, data_orig.edge_index)[data_orig.test_mask]
        test_logits_t = model(data_trans.x, data_trans.edge_index)[data_trans.test_mask]
        
        test_probs_o = F.softmax(test_logits_o, dim=1)
        test_probs_t = F.softmax(test_logits_t, dim=1)

        # C. 重新启用：绘制 Threshold Sweep 曲线图 (PR/ROC 趋势)
        print("正在绘制阈值扫描曲线...")
        sweep_res_o = perform_threshold_sweep(test_probs_o, data_orig.y[data_orig.test_mask])
        sweep_res_t = perform_threshold_sweep(test_probs_t, data_trans.y[data_trans.test_mask])
        best_thr = plot_dual_threshold_curves(sweep_res_o, sweep_res_t, save_name='final_threshold_sweep.png')

        # D. 重新启用：绘制 Score Distribution (TP/FP 重叠分析)
        print("正在绘制分数分布图...")
        # 准备 Orig 电路的四类分数
        t_scores = test_probs_o[:, 1].cpu().numpy()
        t_labels = data_orig.y[data_orig.test_mask].cpu().numpy()
        t_preds = (t_scores >= final_thr).astype(int)
        
        plot_score_distribution(
            tp_scores = t_scores[(t_labels == 1) & (t_preds == 1)],
            fp_scores = t_scores[(t_labels == 0) & (t_preds == 1)],
            tn_scores = t_scores[(t_labels == 0) & (t_preds == 0)],
            fn_scores = t_scores[(t_labels == 1) & (t_preds == 0)],
            threshold = final_thr,
            save_name = 'final_score_distribution.png'
        )

        # E. 计算总表指标 (使用 calculate_full_metrics)
        res_orig = calculate_full_metrics(test_probs_o, data_orig.y[data_orig.test_mask], final_thr)
        res_trans = calculate_full_metrics(test_probs_t, data_trans.y[data_trans.test_mask], final_thr)

        # F. 打印汇总总表
        print(f"\n[Val Protocol] 基于验证集确定的最优阈值: {final_thr:.4f}")
        print("\n" + " 指标汇总总表 ".center(60, "="))
        print(f"{'Metric':<18} | {'Original':<15} | {'Transformed':<15}")
        print("-" * 60)
        for m in ['Recall', 'Precision', 'FPR', 'Macro-F1', 'PR-AUC']:
            print(f"{m:<18} | {res_orig[m]:<15.4f} | {res_trans[m]:<15.4f}")
        print("-" * 60)
        consist_gap = abs(res_orig['Macro-F1'] - res_trans['Macro-F1'])
        print(f"{'Consistency Gap':<18} | {consist_gap:<33.4f}")
        print(f"{'TP/FP/FN/TN (O)':<18} | {res_orig['TP']}/{res_orig['FP']}/{res_orig['FN']}/{res_orig['TN']}")
        print(f"{'TP/FP/FN/TN (T)':<18} | {res_trans['TP']}/{res_trans['FP']}/{res_trans['FN']}/{res_trans['TN']}")
        print("=" * 60)

                # E. 计算总表指标 (使用 calculate_full_metrics)
        res_orig_b = calculate_full_metrics(test_probs_o, data_orig.y[data_orig.test_mask], best_thr)
        res_trans_b = calculate_full_metrics(test_probs_t, data_trans.y[data_trans.test_mask], best_thr)

        # F. 打印汇总总表
        print(f"\n[Val Protocol] 测试集的最优阈值: {best_thr:.4f}")
        print("\n" + " 指标汇总总表 ".center(60, "="))
        print(f"{'Metric':<18} | {'Original':<15} | {'Transformed':<15}")
        print("-" * 60)
        for m in ['Recall', 'Precision', 'FPR', 'Macro-F1', 'PR-AUC']:
            print(f"{m:<18} | {res_orig_b[m]:<15.4f} | {res_trans_b[m]:<15.4f}")
        print("-" * 60)
        consist_gap_b = abs(res_orig_b['Macro-F1'] - res_trans_b['Macro-F1'])
        print(f"{'Consistency Gap':<18} | {consist_gap_b:<33.4f}")
        print(f"{'TP/FP/FN/TN (O)':<18} | {res_orig_b['TP']}/{res_orig_b['FP']}/{res_orig_b['FN']}/{res_orig_b['TN']}")
        print(f"{'TP/FP/FN/TN (T)':<18} | {res_trans_b['TP']}/{res_trans_b['FP']}/{res_trans_b['FN']}/{res_trans_b['TN']}")
        print("=" * 60)

    # --- 7. 生成采样 CSV 报告 (统一使用 final_thr) ---
    print("\n--- 正在生成采样 CSV 报告 ---")
    # 针对验证集做一次采样（看模型在选参集上的死角）
    analyze_samples_unified(model, data_orig, final_thr, g_map, mask_type='val')
    # 针对测试集做一次采样（看模型真正的泛化死角）
    analyze_samples_unified(model, data_orig, final_thr, g_map, mask_type='test')

    # 保存最终权重并画训练趋势
    torch.save(model.state_dict(), os.path.join(current_dir, 'siamese_gin_model.pkl'))
    plot_training_metrics(history)

if __name__ == "__main__":
    train()