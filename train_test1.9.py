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
import re
from scipy.sparse import load_npz
from datetime import datetime
import shutil
# 确保可以显示中文（如果需要）或设置样式
plt.style.use('seaborn-v0_8-whitegrid')
# 自动处理路径，确保能找到 models 和 data_loader
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from models.gin_net import GINNodeClassifier
# --- 关键修改：导入数据加载工具 ---
from data_loader import get_siamese_data

import random

def get_file_level_loco_masks(file_ids, prefixes, target_file, val_size=3, is_trans=False):
    """
    target_file: 原始网表的文件名 (例如 's38584t100')
    is_trans: 是否正在为变换后的图生成掩码
    """
    file_ids_arr = np.array(file_ids)
    prefixes_arr = np.array(prefixes)
    
    # --- 步骤 1: 确定该文件的基准电路前缀 (Prefix) ---
    # 统一去掉后缀干扰，确保能准确找到 prefix (例如 s38584)
    clean_name = re.sub(r'(_tr|tr|equiv|_equiv)\d*$', '', target_file)
    match = re.search(r'^(.+?)(?=t\d|_tr|tr\d|equiv)', clean_name)
    target_prefix = match.group(1).rstrip('_') if match else clean_name

    # --- 步骤 2: 划分 Train/Val 电路前缀 (隔离逻辑) ---
    unique_prefixes = sorted(list(set(prefixes)))
    # 所有的训练和验证集必须来自于“非 target_prefix”的电路
    available_prefixes = [p for p in unique_prefixes if p != target_prefix]
    
    random.seed(len(target_file) + sum(ord(c) for c in target_file)) 
    actual_val_size = min(len(available_prefixes), val_size)
    val_prefixes = random.sample(available_prefixes, actual_val_size)
    train_prefixes = [p for p in available_prefixes if p not in val_prefixes]

    # --- 步骤 3: 生成测试集掩码 (核心修改点) ---
    if not is_trans:
        # 原始图：精确匹配文件名
        test_mask_np = (file_ids_arr == target_file)
    else:
        # 变换图：匹配以 target_file 开头的文件名 (从而抓住 s38584t100tr1, s38584t100tr2 等)
        # 这种写法比正则更稳健
        test_mask_np = np.array([str(fid).startswith(target_file) for fid in file_ids])

    # --- 步骤 4: 转换为 Tensor ---
    train_mask = torch.from_numpy(np.isin(prefixes_arr, train_prefixes))
    val_mask = torch.from_numpy(np.isin(prefixes_arr, val_prefixes))
    test_mask = torch.from_numpy(test_mask_np)
    
    return train_mask, val_mask, test_mask

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

def analyze_samples_unified(model, data_o, data_t, threshold, glook, save_dir):
    """
    统一分析函数
    mask_type: 'test' 或 'val'
    """
    model.eval()
    output_file = os.path.join(save_dir, 'node_paired_analysis.csv')
    
    # 获取测试集的配对索引
    # 逻辑：从全量 alignment 中找出两端都在 test_mask 内的对
    align = data_t.alignment
    test_pair_mask = data_o.test_mask[align[0]] & data_t.test_mask[align[1]]
    test_align = align[:, test_pair_mask]

    if test_align.shape[1] == 0:
        print("  [Warning] 测试集无对齐数据，无法生成配对分析 CSV")
        return

    with torch.no_grad():
        # 获取两边的概率
        logits_o = model(data_o.x, data_o.edge_index)
        logits_t = model(data_t.x, data_t.edge_index)
        probs_o = F.softmax(logits_o, dim=1)[:, 1].cpu().numpy()
        probs_t = F.softmax(logits_t, dim=1)[:, 1].cpu().numpy()
        
        y_true = data_o.y.cpu().numpy()
        
        # 准备特征数据 (用于还原物理信息)
        feats_o = data_o.x.cpu().numpy()
        idx_to_gate = {v: k for k, v in glook.items()}
        num_gate_types = len(glook)

        analysis_results = []
        
        for i in range(test_align.shape[1]):
            idx_o = test_align[0, i].item()
            idx_t = test_align[1, i].item()
            
            p_o = probs_o[idx_o]
            p_t = probs_t[idx_t]
            label = int(y_true[idx_o])
            
            # 判定样本类型 (以 Orig 的预测为基准)
            pred_o = 1 if p_o >= threshold else 0
            if label == 1:
                s_type = 'TP' if pred_o == 1 else 'FN'
            else:
                s_type = 'FP' if pred_o == 1 else 'TN'

            # 提取特征 (示例：使用 data_o 的特征)
            gate_idx = np.argmax(feats_o[idx_o, :num_gate_types])
            
            analysis_results.append({
                'orig_index': idx_o,
                'trans_index': idx_t,
                'sample_type': s_type,
                'gate_type': idx_to_gate.get(gate_idx, "Unknown"),
                'true_label': label,
                'score_orig': round(float(p_o), 4),
                'score_trans': round(float(p_t), 4),
                'drift': round(float(abs(p_o - p_t)), 4),
                'is_flip': 1 if (pred_o != (1 if p_t >= threshold else 0)) else 0,
                # 物理特征
                'fan_in': int(np.expm1(feats_o[idx_o, num_gate_types])),
                'dist_to_pi': round(float(feats_o[idx_o, 29]), 2), # 假设 29 是 Dist_to_PI
                'dist_to_po': round(float(feats_o[idx_o, 30]), 2),
                'fan_in_2hop': int(np.expm1(feats_o[idx_o, -2])),
                'fan_out_2hop': int(np.expm1(feats_o[idx_o, -1]))
            })

        df = pd.DataFrame(analysis_results)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"  [成功] 配对节点分析报告已保存至: {output_file}")

def plot_score_distribution(tp_scores, fp_scores, tn_scores, fn_scores, threshold, save_path):
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
    plt.savefig(save_path)
    print(f"[成功] 分数分布图已保存为 {save_path}")
    plt.close()

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

    probs = np.nan_to_num(probs, nan=0.0, posinf=1.0, neginf=0.0)
    
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

    from sklearn.metrics import roc_auc_score, average_precision_score
    try:
        roc_auc = roc_auc_score(labels, scores)
    except:
        roc_auc = 0.5  # 处理全为单类别的特殊情况
    # PR-AUC (即 Average Precision)
    pr_auc = average_precision_score(labels, scores)
    
    return {
        'Recall': rec,
        'Precision': pre,
        'FPR': fpr,
        'Macro-F1': mac_f1,
        'PR-AUC': pr_auc,
        'ROC-AUC': roc_auc,
        'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn
    }

def calc_soft_f1_metrics(probs, labels):
    """ 计算二分类下的可导 Soft F1 (用于损失函数) """
    probs = torch.clamp(probs, 1e-7, 1.0 - 1e-7)
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

from scipy.stats import spearmanr  # 新增：用于计算秩相关


def compute_consistency_loss(preds_o, preds_t, alignment, mask_o, mask_t, mode='mae_prob'):
    """
    计算配对节点的一致性损失 (L_const)
    只计算同时处于 Orig 和 Trans 训练集内的配对，防止验证/测试集泄露
    """
    idx_o = alignment[0]
    idx_t = alignment[1]
    
    # 【严格隔离】只选择两端都在训练集掩码内的配对节点
    train_pair_mask = mask_o[idx_o] & mask_t[idx_t]
    sel_idx_o = idx_o[train_pair_mask]
    sel_idx_t = idx_t[train_pair_mask]

    if len(sel_idx_o) == 0:
        return torch.tensor(0.0, device=preds_o.device)

    logits_o = preds_o[sel_idx_o]
    logits_t = preds_t[sel_idx_t]
    
    # 计算概率 (用于 KL 和 MAE)
    T = 0.5
    p_o = F.softmax(logits_o / T, dim=1)
    p_t = F.softmax(logits_t / T, dim=1)

    if mode == 'mse_logit':
        # 1. MSE(logit_o, logit_t)
        return F.mse_loss(logits_o, logits_t)
    
    elif mode == 'sym_kl':
        # 2. 对称 KL(p_o, p_t)
        log_p_o = F.log_softmax(logits_o / T, dim=1)
        log_p_t = F.log_softmax(logits_t / T, dim=1)
        kl_ot = F.kl_div(log_p_t, p_o, reduction='batchmean')
        kl_to = F.kl_div(log_p_o, p_t, reduction='batchmean')
        return (kl_ot + kl_to) / 2.0
    
    elif mode == 'mae_prob':
        # 3. |p_o - p_t|
        return F.l1_loss(p_o, p_t)
    
    return torch.tensor(0.0, device=preds_o.device)

from scipy.stats import spearmanr, wilcoxon # 确保导入了 wilcoxon

def calc_detailed_consistency(preds_o, preds_t, labels_o, alignment, threshold, top_k=50):
    """ 计算深度一致性指标 """
    with torch.no_grad():
        # 获取配对节点的木马类概率 (仅针对传入的 alignment 范围)
        p_o = F.softmax(preds_o[alignment[0]], dim=1)[:, 1].cpu().numpy()
        p_t = F.softmax(preds_t[alignment[1]], dim=1)[:, 1].cpu().numpy()
        y_true = labels_o[alignment[0]].cpu().numpy()
        
        # 1. Paired-MAE & Spearman (原有)
        paired_mae = np.mean(np.abs(p_o - p_t))
        # 2. Spearman Rank Correlation (排序一致性)
        if len(np.unique(p_o)) > 1 and len(np.unique(p_t)) > 1:
            rank_corr, _ = spearmanr(p_o, p_t)
        else:
            rank_corr = 0.0
        
        # 2. Flip Rate (类别翻转率)
        f_o = (p_o >= threshold).astype(int)
        f_t = (p_t >= threshold).astype(int)
        flip_rate = np.mean(f_o != f_t)
        
        # 3. Score Drift (分数漂移)
        t_mask = (y_true == 1)
        b_mask = (y_true == 0)
        t_drift = np.mean(p_t[t_mask] - p_o[t_mask]) if any(t_mask) else 0.0
        b_drift = np.mean(p_t[b_mask] - p_o[b_mask]) if any(b_mask) else 0.0
        
        # 4. Top-k Overlap (高危节点重合度)
        k = min(top_k, len(p_o))
        top_k_o = np.argsort(p_o)[-k:]
        top_k_t = np.argsort(p_t)[-k:]
        overlap = len(np.intersect1d(top_k_o, top_k_t)) / k
        
    return {
        'Paired_MAE': paired_mae, 'Spearman_Corr': rank_corr,
        'Flip_Rate': flip_rate, 'Trojan_Drift': t_drift,
        'Benign_Drift': b_drift, 'TopK_Overlap': overlap
    }

def calc_paired_consistency_metrics(preds_o, preds_t, alignment):
    """
    固定度量定义：配对节点上的平均概率绝对误差 (Paired-MAE) 和 秩相关 (Spearman)
    """
    with torch.no_grad():
        # 获取配对节点的木马类概率
        p_o = F.softmax(preds_o[alignment[0]], dim=1)[:, 1].cpu().numpy()
        p_t = F.softmax(preds_t[alignment[1]], dim=1)[:, 1].cpu().numpy()
        
        # 1. Paired-MAE (数值一致性)
        paired_mae = np.mean(np.abs(p_o - p_t))
        
        # 2. Spearman Rank Correlation (排序一致性)
        if len(np.unique(p_o)) > 1 and len(np.unique(p_t)) > 1:
            rank_corr, _ = spearmanr(p_o, p_t)
        else:
            rank_corr = 0.0
            
    return paired_mae, rank_corr
def siamese_loss(preds_o_all, preds_t_all, labels_o, labels_t, data_o, data_t,
                 lambda_const=2.0, lambda_det=2.0, lambda_nor=1.0, lambda_pos=10.0,
                 trojan_w=8.0, loss_type='ce', use_hnm=False, const_mode='mae_prob'):
    mask_o, mask_t = data_o.train_mask, data_t.train_mask
    preds_o_train = preds_o_all[mask_o]
    # preds_t_train = preds_t_all[mask_t] # 注释掉或不使用

    weight = torch.tensor([1.0, trojan_w], device=preds_o_all.device)
    
    # 【修改】：只计算原始图的分类损失
    if use_hnm:
        task_loss_o = hnm_loss(preds_o_train, labels_o, mining_ratio=0.1, hard_weight=10.0, base_weight=weight)
    else:
        task_loss_o = compute_task_loss(preds_o_train, labels_o, loss_type=loss_type, weight=weight)
    
    # task_loss_t 设为 0，Trans 仅通过 loss_const 受约束
    task_loss_total = task_loss_o 

    # 一致性损失 (L_const) 依然保留，这是 Siamese 的核心
    loss_const = compute_consistency_loss(preds_o_all, preds_t_all, data_t.alignment, mask_o, mask_t, mode=const_mode)

    # 检出率惩罚也只针对 Orig 
    T = 0.5
    probs_o_train = F.softmax(preds_o_train / T, dim=1)
    F1mic_o, F1mac_o, sdr_n_o, sdr_tr_o = calc_soft_f1_metrics(probs_o_train, labels_o)

    loss_det_rate = trojan_w * torch.pow(1.0 - sdr_tr_o, 2)
    loss_normal_consistency = (1.0 - sdr_n_o)

    # 位置惩罚只针对 Orig
    dist_pi_o = data_o.x[data_o.train_mask][:, 29]
    penalty_o = torch.mean(probs_o_train[:, 1] * (1.0 / (dist_pi_o + 0.5)))

    total_loss = task_loss_total + \
                 lambda_const * loss_const + \
                 lambda_det * loss_det_rate + \
                 lambda_nor * loss_normal_consistency

    # 返回值保持结构一致，Trans 的指标设为 0
    return total_loss, F1mic_o, F1mac_o, torch.tensor(0.0), torch.tensor(0.0), sdr_tr_o, torch.tensor(0.0)

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
def plot_dual_threshold_curves(res_o, res_t, target_thr, save_path):
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
    plt.axvline(x=target_thr, color='purple', linestyle='-.', label=f'Best Thr: {target_thr:.2f}')
    
    plt.title('Macro-F1 Consistency')
    plt.xlabel('Threshold')
    plt.ylabel('F1 Score')
    plt.legend()

    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()
    

    # 打印对比数据
    # print(f"\n[对比分析] 当阈值为 {target_thr:.3f} 时:")
    # print(f"  - Original:    Recall={res_o['rec'][idx_85]:.2%}, FP={res_o['fp'][idx_85]}, FPR={res_o['fpr'][idx_85]:.4%}")
    # print(f"  - Transformed: Recall={res_t['rec'][idx_85]:.2%}, FP={res_t['fp'][idx_85]}, FPR={res_t['fpr'][idx_85]:.4%}")
    # return target_thr

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
    # 4. Consistency Metrics 子图 (修复此处)
    plt.subplot(2, 2, 4)
    # 检查长度防止再次报错
    if len(history['paired_mae']) == len(epochs):
        plt.plot(epochs, history['paired_mae'], 'm-d', label='Paired-MAE (Prob)')
        plt.plot(epochs, history['rank_corr'], 'c-s', label='Spearman Rank')
    plt.title('Node-Level Consistency Metrics')
    plt.xlabel('Epoch')
    plt.ylabel('Score')
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

def debug_alignment_from_pt(data_orig, data_trans):
    """
    直接从加载好的 pt 数据对象检查映射质量
    """
    print("\n" + "="*60)
    print("正在进行映射 (Alignment) 质量审计 [基于 .pt 对象]...")
    print("="*60)

    align = data_trans.alignment  # 配对矩阵 [2, M]
    file_ids_o = np.array(data_orig.file_ids)
    unique_files = sorted(list(set(data_orig.file_ids)))
    
    report = []

    for fid in unique_files:
        # 1. 提取当前电路的节点索引
        idx_in_orig = np.where(file_ids_o == fid)[0]
        
        # 2. 提取属于该电路的配对关系
        mask = np.isin(align[0], idx_in_orig)
        file_align = align[:, mask]
        
        num_nodes_o = len(idx_in_orig)
        num_pairs = file_align.shape[1]
        
        if num_pairs == 0:
            print(f"  [严重错误] 电路 {fid}: 在 alignment 表中没有找到任何配对节点！")
            report.append({'File': fid, 'Pairs': 0, 'Label_Match': 0, 'Feat_Match': 0})
            continue

        # 3. 标签一致性检查 (木马必须对应木马，正常必须对应正常)
        y_o = data_orig.y[file_align[0]]
        y_t = data_trans.y[file_align[1]]
        label_match = (y_o == y_t).sum().item() / num_pairs
        
        # 4. 特征一致性检查 (对比 x 向量是否相同)
        # 虽然变换后位置特征会变，但前几十维（门类型 One-hot）通常应该保持一致
        # 我们比较前 20 维特征作为代表
        check_dim = min(20, data_orig.x.shape[1])
        x_o = data_orig.x[file_align[0], :check_dim]
        x_t = data_trans.x[file_align[1], :check_dim]
        # 统计特征完全相同的行数
        feat_match = (torch.all(x_o == x_t, dim=1)).sum().item() / num_pairs

        report.append({
            'File': fid,
            'Pairs': num_pairs,
            'Coverage': num_pairs / num_nodes_o,
            'Label_Match': label_match,
            'Feat_Match': feat_match
        })

    # 打印简报
    df = pd.DataFrame(report)
    print(df.to_string(index=False))
    
    # 诊断建议
    if df['Label_Match'].min() < 1.0:
        print("\n❌ 结论：映射存在【标签冲突】！Orig 的木马在 Trans 中变成了正常节点。")
    elif df['Pairs'].min() == 0:
        print("\n❌ 结论：部分电路【完全缺失】映射关系。")
    else:
        print("\n✅ 结论：映射逻辑一致性良好。")
        
    return df
def train():
    # --- 1. 加载配置 ---
    seed_id = 42
    seed_everything(seed_id)
    config_path = os.path.join(current_dir, 'config.yaml')
    if not os.path.exists(config_path):
        print(f"错误: 找不到配置文件 {config_path}")
        return
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    device = torch.device(config['train']['device'] if torch.cuda.is_available() else 'cpu')
    print(f"训练设备: {device}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_results_dir = os.path.join(current_dir, "results", f"run_{run_id}_seed{seed_id}")
    os.makedirs(base_results_dir, exist_ok=True)

    # --- 2. 一次性加载全量数据 ---
    try:
        data_orig, data_trans = get_siamese_data(config)

        debug_alignment_from_pt(data_orig, data_trans)


        # 获取所有电路前缀
        all_prefixes = sorted(list(set(data_orig.prefixes)))
        loco_final_results = [] # 用于保存每一轮的结果
        print(f"数据加载成功: 共有 {len(all_prefixes)} 个电路前缀")
        print("正在预处理特征矩阵：修正距离特征...")
        with torch.no_grad():
            for d in [data_orig, data_trans]:
                # 假设索引 29 是 Dist_to_PI, 30 是 Dist_to_PO
                dist_indices = [29, 30]
                
                # 1. 处理 -1 异常值：将其替换为 20.0（代表极远/不可达）
                # 防止在 Loss 计算时出现 1 / (-1 + 0.5) = -2 这种奖励孤立节点的情况
                d.x[:, dist_indices] = torch.where(
                    d.x[:, dist_indices] == -1.0, 
                    torch.tensor(20.0, device=d.x.device), 
                    d.x[:, dist_indices]
                )
                
                # 2. 对数缩放：将 [0, 20] 的范围压缩到 [0, 3] 左右
                # 这样距离特征的量级就和 One-hot 特征 (0/1) 匹配了，防止距离特征主导梯度
                d.x[:, dist_indices] = torch.log1p(d.x[:, dist_indices])
    except Exception as e:
        print(f"数据处理异常: {e}")
        return
    
    all_file_ids = sorted(list(set(data_orig.file_ids)))
    loco_final_results = []

    # --- 3. LOCO 外层循环：轮换测试电路 ---
    for fold_idx, target_file in enumerate(all_file_ids):
        circuit_results_dir = os.path.join(base_results_dir, target_file)
        os.makedirs(circuit_results_dir, exist_ok=True)
        print(f"\n" + "="*60)
        print(f"\n>>> [File Fold {fold_idx+1}/{len(all_file_ids)}] 测试目标文件: {target_file}")
        print("="*60)
        
        # 3.1 为 Original 图生成 Mask (is_trans=False)
        tr_m_o, va_m_o, te_m_o = get_file_level_loco_masks(
            data_orig.file_ids, data_orig.prefixes, target_file, val_size=1, is_trans=False
        )
        data_orig.train_mask, data_orig.val_mask, data_orig.test_mask = tr_m_o, va_m_o, te_m_o

        # 3.2 为 Transformed 图生成 Mask (is_trans=True, 开启后缀 tr 匹配)
        tr_m_t, va_m_t, te_m_t = get_file_level_loco_masks(
            data_trans.file_ids, data_trans.prefixes, target_file, val_size=1, is_trans=True
        )
        data_trans.train_mask, data_trans.val_mask, data_trans.test_mask = tr_m_t, va_m_t, te_m_t

        with open(os.path.join(circuit_results_dir, "log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Executed Script: {os.path.basename(__file__)}\n")
            train_files = sorted(list(set(np.array(data_orig.file_ids)[data_orig.train_mask.cpu().numpy()])))
            val_files = sorted(list(set(np.array(data_orig.file_ids)[data_orig.val_mask.cpu().numpy()])))
            f.write(f"Training Set: {', '.join(train_files)}\n")
            f.write(f"Validation Set: {', '.join(val_files)}\n")
            f.write(f"Test Target: {target_file}\n")

        # 3.2 每一轮都要重新初始化模型与优化器
        model = GINNodeClassifier(
            in_channels=config['model']['in_channels'],
            hidden_channels=config['model']['hidden_channels'],
            out_channels=config['model']['out_channels'],
            num_layers=config['model']['num_layers']
        ).to(device)
        
        optimizer = torch.optim.Adam(model.parameters(), 
                                     lr=float(config['train']['lr']), 
                                     weight_decay=float(config['train']['weight_decay']))
        
        best_fold_val_score = -1.0
        best_threshold_from_val = 0.5
        BEST_MODEL_STRATEGY = 'fpr_at_recall' 
        TARGET_RECALL = 0.85


        # --- 4. 内部训练循环 ---
        for epoch in range(config['train']['epochs']):
            model.train()
            optimizer.zero_grad()
            preds_o_all = model(data_orig.x, data_orig.edge_index)
            preds_t_all = model(data_trans.x, data_trans.edge_index)

        # in/out
            current_lambda_const = 0.0
            current_lambda_det = 0.3
            current_lambda_nor = 0.5
            current_lambda_pos = 10.0
            current_trojan_w = 6.0

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
            hnm_enabled = False if epoch >= 60 else False
            const_strategy = 'sym_kl' # 可选: 'mse_logit', 'sym_kl', 'mae_prob'
            # 备选：'ce', 'focal', 'asl'
            selected_loss = 'ce'




            # 核心：仅使用训练集掩码节点计算 Siamese Loss
            loss_val, smic_o, smac_o, smic_t, smac_t , sdr_o, sdr_t = siamese_loss(
                preds_o_all, 
                preds_t_all, 
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
                use_hnm=hnm_enabled,
                const_mode=const_strategy
            )
            
            loss_val.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
            # --- 5. 验证逻辑 (每 10 轮) ---
            if (epoch + 1) % 10 == 0:
                model.eval()
                with torch.no_grad():
                    # 获取验证集概率
                    logits_o_all = model(data_orig.x, data_orig.edge_index)
                    logits_t_all = model(data_trans.x, data_trans.edge_index)
                    
                    val_probs_o = F.softmax(logits_o_all[data_orig.val_mask], dim=1)
                    val_probs_t = F.softmax(logits_t_all[data_trans.val_mask], dim=1)
                    val_labels_o = data_orig.y[data_orig.val_mask]
                    val_labels_t = data_trans.y[data_trans.val_mask]
                    
                    # 获取全阈值扫描结果
                    sweep = perform_threshold_sweep(val_probs_o, val_labels_o)
                    recs = np.array(sweep['rec'])
                    f1s = np.array(sweep['macro_f1'])
                    fprs = np.array(sweep['fpr'])
                    thrs = np.array(sweep['thr'])

                    # --- 根据不同策略计算当前得分 ---
                    current_epoch_score = 0.0
                    epoch_best_thr = 0.5

                    if BEST_MODEL_STRATEGY == 'pr_auc':
                        # 策略1: 最高的 PR-AUC
                        from sklearn.metrics import average_precision_score
                        current_epoch_score = average_precision_score(val_labels_o.cpu(), val_probs_o[:, 1].cpu())
                        epoch_best_thr = thrs[np.argmax(f1s)] # 辅助记录一个较好的阈值

                    elif BEST_MODEL_STRATEGY == 'macro_f1':
                        # 策略2: 最高的 Macro-F1
                        best_f1_idx = np.argmax(f1s)
                        current_epoch_score = f1s[best_f1_idx]
                        epoch_best_thr = thrs[best_f1_idx]

                    elif BEST_MODEL_STRATEGY == 'fpr_at_recall':
                        # 策略3: Recall >= 0.85 时 FPR 最低
                        # 我们希望 score 越大越好，所以用 (1.0 - FPR) 作为得分
                        idx_above_target = np.where(recs >= TARGET_RECALL)[0]
                        if len(idx_above_target) > 0:
                            # 在达标的索引中找最小 FPR
                            best_sub_idx = np.argmin(fprs[idx_above_target])
                            global_idx = idx_above_target[best_sub_idx]
                            current_epoch_score = 1.0 - fprs[global_idx] # 得分越高 FPR 越低
                            epoch_best_thr = thrs[global_idx]
                        else:
                            # 兜底：如果 Recall 没达标，以 Recall 越高分越高
                            current_epoch_score = np.max(recs) * 0.1 # 权重降级，确保不优于达标的模型
                            epoch_best_thr = thrs[np.argmax(recs)]

                    # C. 计算 Orig 和 Trans 的各项指标
                    metrics_o = calculate_full_metrics(val_probs_o, val_labels_o, epoch_best_thr)
                    metrics_t = calculate_full_metrics(val_probs_t, val_labels_t, epoch_best_thr)

                    # D. 计算一致性指标
                    p_mae, r_corr = calc_paired_consistency_metrics(logits_o_all, logits_t_all, data_trans.alignment)
                    c_gap = abs(metrics_o['PR-AUC'] - metrics_t['PR-AUC'])

                    print(f"  [Epoch {epoch+1:03d}] Loss: {loss_val.item():.4f} | Thr: {epoch_best_thr:.3f}")
                    print(f"  Ep {epoch+1:03d} | Loss: {loss_val.item():.3f} | MAE: {p_mae:.4f} | Thr: {epoch_best_thr:.2f}")
                    print(f"  [Val_O] PR-AUC: {metrics_o['PR-AUC']:.4f} | Rec: {metrics_o['Recall']:.4f} | FPR: {metrics_o['FPR']:.4f} | TP/FP/FN: {int(metrics_o['TP'])}/{int(metrics_o['FP'])}/{int(metrics_o['FN'])}")
                    print(f"  [Val_T] PR-AUC: {metrics_t['PR-AUC']:.4f} | Rec: {metrics_t['Recall']:.4f} | FPR: {metrics_t['FPR']:.4f} | TP/FP/FN: {int(metrics_t['TP'])}/{int(metrics_t['FP'])}/{int(metrics_t['FN'])}")
                    print(f"  [Match] Gap: {c_gap:.4f} | Paired-MAE: {p_mae:.4f}")

                    # 记录最优模型 (以验证集 PR-AUC 为准)
                    if current_epoch_score > best_fold_val_score:
                        best_fold_val_score = current_epoch_score
                        best_threshold_from_val = epoch_best_thr
                        torch.save(model.state_dict(), f'pytorch_models/best_file_{target_file}.pkl')

        # --- 6. 本轮 Fold 最终评估 ---
        model.load_state_dict(torch.load(f'pytorch_models/best_file_{target_file}.pkl'))
        model.eval()
        with torch.no_grad():
            val_logits_best = model(data_orig.x, data_orig.edge_index)[data_orig.val_mask]
            val_probs_best = F.softmax(val_logits_best, dim=1)
            val_labels_best = data_orig.y[data_orig.val_mask]
            
            # 为当前最优模型重新扫频
            best_sweep = perform_threshold_sweep(val_probs_best, val_labels_best)

            # 1. 转换为 numpy 数组
            recs_v = np.array(best_sweep['rec'])
            fprs_v = np.array(best_sweep['fpr'])
            thrs_v = np.array(best_sweep['thr'])

            # 2. 寻找满足 Recall >= 0.85 (或 0.70) 的最优阈值
            target_rec_limit = 0.85 # 建议设为 0.85
            target_indices = np.where(recs_v >= target_rec_limit)[0]

            if len(target_indices) > 0:
                # 3. 在满足 Recall 的前提下，找 Macro-F1 最高（误报最少）的点
                best_sub_idx = np.argmin(fprs_v[target_indices])
                calibrated_threshold = thrs_v[target_indices[best_sub_idx]]
            else:
                # 兜底：如果模型达不到红线，取 Recall 最高的点
                best_idx = np.argmax(recs_v)
                calibrated_threshold = thrs_v[best_idx]
                print(f"  [Warning] Fold {target_file} 无法达到 {target_rec_limit} Recall")

            print(f"--- Fold {target_file} 评估 (应用验证集最优阈值: {calibrated_threshold:.4f}) ---")

            # 运行测试集
            final_logits_o = model(data_orig.x, data_orig.edge_index)
            final_logits_t = model(data_trans.x, data_trans.edge_index)
            
            # 测试集切片
            test_probs_o = F.softmax(final_logits_o[data_orig.test_mask], dim=1)
            test_probs_t = F.softmax(final_logits_t[data_trans.test_mask], dim=1)
            test_labels_o = data_orig.y[data_orig.test_mask]
            test_labels_t = data_trans.y[data_trans.test_mask]

            # 计算最终指标
            res_o = calculate_full_metrics(test_probs_o, test_labels_o, threshold=calibrated_threshold)
            res_t = calculate_full_metrics(test_probs_t, test_labels_t, threshold=calibrated_threshold)
            
            test_pair_mask = data_orig.test_mask[data_trans.alignment[0]] & data_trans.test_mask[data_trans.alignment[1]]
            test_alignment = data_trans.alignment[:, test_pair_mask]
            
            # B. 计算新增的一致性指标
            consist_metrics = calc_detailed_consistency(
                final_logits_o, final_logits_t, data_orig.y, 
                test_alignment, calibrated_threshold
            )
            c_gap_f = abs(res_o['PR-AUC'] - res_t['PR-AUC'])

            # A. 绘制分数分布图 (Score Distribution)
            # 提取测试集四类样本的分数plot_dual_threshold_cidx_to_gateurves
            scores_o = test_probs_o[:, 1].cpu().numpy()
            y_o = test_labels_o.cpu().numpy()
            preds_o = (scores_o >= calibrated_threshold).astype(int)
            
            tp_s = scores_o[(y_o == 1) & (preds_o == 1)]
            fp_s = scores_o[(y_o == 0) & (preds_o == 1)]
            tn_s = scores_o[(y_o == 0) & (preds_o == 0)]
            fn_s = scores_o[(y_o == 1) & (preds_o == 0)]
            
            plot_score_distribution(tp_s, fp_s, tn_s, fn_s, calibrated_threshold, 
                                    os.path.join(circuit_results_dir, "final_score_distribution.png"))

            # B. 绘制阈值曲线图 (Threshold Sweep)
            sweep_o = perform_threshold_sweep(test_probs_o, test_labels_o)
            sweep_t = perform_threshold_sweep(test_probs_t, test_labels_t)
            plot_dual_threshold_curves(sweep_o, sweep_t, calibrated_threshold,
                                       os.path.join(circuit_results_dir, "final_threshold_sweep.png"))

            # C. 生成节点详细信息 CSV (image.png 对应的功能)
            # 加载 gatelookup (假设路径)
            gatelookup_path = os.path.join(current_dir, 'data/verilog_data/gatelookup_recommended.json')
            if os.path.exists(gatelookup_path):
                with open(gatelookup_path, 'r') as gj:
                    full_data = json.load(gj)
                    glook = full_data.get('gatelookup', full_data) 
                
                # 关键修改：传入 data_orig 和 data_trans
                analyze_samples_unified(model, data_orig, data_trans, calibrated_threshold, 
                                        glook, save_dir=circuit_results_dir)
            else:
                print("  [Error] 找不到 gatelookup_recommended.json，跳过 CSV 生成")
            
            
            
            loco_final_results.append({
                'Test_File': target_file,
                'PR-AUC_O': res_o['PR-AUC'],
                'PR-AUC_T': res_t['PR-AUC'],
                'PR_Drop': res_o['PR-AUC'] - res_t['PR-AUC'],
                'ROC-AUC_O': res_o['ROC-AUC'],
                'ROC-AUC_T': res_t['ROC-AUC'],
                'Recall_O': res_o['Recall'],
                'Recall_T': res_t['Recall'],
                'FPR_O': res_o['FPR'],
                'FPR_T': res_t['FPR'],
                'Consistency_Gap': c_gap_f,
                **consist_metrics,
                'Threshold': best_threshold_from_val
            })
            print(f"  [FOLD FINAL] Recall: {res_o['Recall']:.4f} | FPR: {res_o['FPR']:.4f}")
            print(f"  [FOLD FINAL] Recall: {res_t['Recall']:.4f} | FPR: {res_t['FPR']:.4f}")

    # --- 最终汇总报告 ---
# --- 7. 汇总、计算统计量并保存 ---
    summary_df = pd.DataFrame(loco_final_results)
    numeric_cols = summary_df.select_dtypes(include=[np.number]).columns
    
    # 7.1 自助法置信区间 (Bootstrap 95% CI)
    def bootstrap_ci(data):
        if len(data) < 2: return 0, 0
        means = [np.mean(np.random.choice(data, size=len(data), replace=True)) for _ in range(1000)]
        return np.percentile(means, [2.5, 97.5])

    # 7.2 计算基础统计量
    stats_mean = summary_df[numeric_cols].mean()
    stats_std = summary_df[numeric_cols].std()
    
    # 7.3 计算 CI 和 Wilcoxon P值
    ci_low, ci_high = {}, {}
    for col in numeric_cols:
        l, h = bootstrap_ci(summary_df[col].dropna().values)
        ci_low[col], ci_high[col] = l, h
    
    # Wilcoxon 检验 PR-AUC 在变换前后是否有显著差异
    _, p_val = wilcoxon(summary_df['PR-AUC_O'], summary_df['PR-AUC_T'])

    # 7.4 构造统计行并拼接
    stats_rows = [
        pd.Series({'Test_File': 'MEAN', **stats_mean}),
        pd.Series({'Test_File': 'STD', **stats_std}),
        pd.Series({'Test_File': 'CI_95_LOW', **ci_low}),
        pd.Series({'Test_File': 'CI_95_HIGH', **ci_high}),
        pd.Series({'Test_File': 'WILCOXON_P', 'PR-AUC_O': p_val, 'PR_Drop': summary_df['PR_Drop'].max()}) # PR_Drop列存Worst-case
    ]
    
    final_report_df = pd.concat([summary_df, pd.DataFrame(stats_rows)], ignore_index=True)
    output_path = os.path.join(base_results_dir, 'detailed_loco_summary.csv') # 修改路径
    final_report_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[任务完成] 汇总报告已保存至: {output_path}")
    
    print(f"\n[汇总结果] PR-AUC (O): {stats_mean['PR-AUC_O']:.4f} | PR-AUC (T): {stats_mean['PR-AUC_T']:.4f}")
    print(f"[稳定性] Flip Rate: {stats_mean['Flip_Rate']:.2%} | TopK Overlap: {stats_mean['TopK_Overlap']:.4f}")
    print(f"[统计] Wilcoxon P-value: {p_val:.4f} | Worst-case PR Drop: {summary_df['PR_Drop'].max():.4f}")
    
    # print(f"\n" + "="*50)
    # print(f"LOCO 任务全部完成！")
    # print(f"总测试文件数: {len(summary_df)}")
    # print(f"详细报告(含统计摘要)已保存至: {output_path}")
    
    # # 在控制台打印平均性能预览
    # avg_perf = stats_df[stats_df['Test_File'] == 'MEAN']
    # print(f"平均 PR-AUC (Orig): {avg_perf['PR-AUC_O'].values[0]:.4f}")
    # print(f"平均 Recall (Orig): {avg_perf['Recall_O'].values[0]:.4f}")
    # print(f"平均 Paired-MAE:    {avg_perf['Paired_MAE'].values[0]:.4f}")
    # print("="*50)

if __name__ == "__main__":
    train()