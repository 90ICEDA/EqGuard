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
    
    random.seed(42)
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
                    'dist_to_pi': raw_feats[idx, -4],
                    'dist_to_po': raw_feats[idx, -3],
                    'fan_in_2hop': int(np.expm1(raw_feats[idx, -2])),
                    'fan_out_2hop': int(np.expm1(raw_feats[idx, -1])),
                    # 'dist_to_pi': raw_feats[idx, -5],
                    # 'dist_to_po': raw_feats[idx, -4],
                    # 'fan_in_2hop': int(np.expm1(raw_feats[idx, -3])),
                    # 'fan_out_2hop': int(np.expm1(raw_feats[idx, -2])),
                    # 'in_out_ratio': int(np.expm1(raw_feats[idx, -1]))*0,
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
    # 提取训练集掩码和标签
    mask_o, mask_t = data_o.train_mask, data_t.train_mask
    
    # 分类任务只针对训练集节点
    preds_o_train = preds_o_all[mask_o]
    preds_t_train = preds_t_all[mask_t]

    # 1. 基础分类损失
    weight = torch.tensor([1.0, trojan_w], device=preds_o_all.device)
    if use_hnm:
        task_loss_o = hnm_loss(preds_o_train, labels_o, mining_ratio=0.1, hard_weight=10.0, base_weight=weight)
        task_loss_t = hnm_loss(preds_t_train, labels_t, mining_ratio=0.1, hard_weight=10.0, base_weight=weight)
    else:
        task_loss_o = compute_task_loss(preds_o_train, labels_o, loss_type=loss_type, weight=weight)
        task_loss_t = compute_task_loss(preds_t_train, labels_t, loss_type=loss_type, weight=weight)

    # 2. 【核心修改】配对一致性损失 (严格过滤非训练集节点)
    loss_const = compute_consistency_loss(preds_o_all, preds_t_all, data_t.alignment, mask_o, mask_t, mode=const_mode)

    # 3. 检出率惩罚
    T = 0.5
    probs_o_train = F.softmax(preds_o_train / T, dim=1)
    probs_t_train = F.softmax(preds_t_train / T, dim=1)

    # 2. 计算可导的 Soft F1 指标
    F1mic_o, F1mac_o, sdr_n_o, sdr_tr_o = calc_soft_f1_metrics(probs_o_train, labels_o)
    F1mic_t, F1mac_t, sdr_n_t, sdr_tr_t = calc_soft_f1_metrics(probs_t_train, labels_t)


    loss_det_o = trojan_w * (-torch.log(sdr_tr_o + 1e-10))
    loss_det_t = trojan_w * (-torch.log(sdr_tr_t + 1e-10))  
    loss_det_rate = loss_det_o + loss_det_t

    loss_normal_consistency = (1.0 - sdr_n_o) + (1.0 - sdr_n_t)

    # 2. 新增：位置惩罚项 (Location Penalty)
    # 根据 33 维特征，dist_to_pi 索引为 29
    dist_pi_o = data_o.x[data_o.train_mask][:, 29]
    dist_pi_t = data_t.x[data_t.train_mask][:, 29]
    penalty_o = torch.mean(probs_o_train[:, 1] * (1.0 / (dist_pi_o + 0.5)))
    penalty_t = torch.mean(probs_t_train[:, 1] * (1.0 / (dist_pi_t + 0.5)))
    location_loss = penalty_o + penalty_t

    total_loss = (task_loss_o+task_loss_t) + \
                 lambda_const * loss_const + \
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

def train():
    # --- 1. 配置与参数设置 ---
    seed_everything(43)
    config_path = os.path.join(current_dir, 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    device = torch.device(config['train']['device'] if torch.cuda.is_available() else 'cpu')

    # 【手动指定测试文件】 替换为你想要测试的文件名（不带.v）
    TARGET_TEST_FILE = "s15850t100" 

    # --- 2. 加载并预处理数据 ---
    try:
        data_orig, data_trans = get_siamese_data(config)
        # 特征预处理
        with torch.no_grad():
            for d in [data_orig, data_trans]:
                dist_idx = [29, 30]
                mask_neg = (d.x[:, dist_idx] == -1.0)
                d.x[:, dist_idx] = torch.where(mask_neg, torch.tensor(20.0, device=device), d.x[:, dist_idx])
                d.x[:, dist_idx] = torch.log1p(d.x[:, dist_idx])
        
        # 加载门映射表供后续分析使用
        gatelookup_path = os.path.join(current_dir, 'gatelookup_recommended.json')
        with open(gatelookup_path, 'r') as f:
            g_json = json.load(f)
            g_map = g_json.get('gatelookup', g_json)

    except Exception as e:
        print(f"数据加载异常: {e}"); return

    # --- 3. 准备掩码 (单次划分) ---
    print(f"\n>>> [单电路测试模式] 目标文件: {TARGET_TEST_FILE}")
    
    # 为 Original 生成掩码
    tr_m_o, va_m_o, te_m_o = get_file_level_loco_masks(data_orig.file_ids, data_orig.prefixes, TARGET_TEST_FILE, val_size=3, is_trans=False)
    data_orig.train_mask, data_orig.val_mask, data_orig.test_mask = tr_m_o, va_m_o, te_m_o

    # 为 Transformed 生成掩码 (包含 tr 后缀匹配)
    tr_m_t, va_m_t, te_m_t = get_file_level_loco_masks(data_trans.file_ids, data_trans.prefixes, TARGET_TEST_FILE, val_size=3, is_trans=True)
    data_trans.train_mask, data_trans.val_mask, data_trans.test_mask = tr_m_t, va_m_t, te_m_t

    # --- 4. 初始化模型 ---
    model = GINNodeClassifier(
        in_channels=config['model']['in_channels'],
        hidden_channels=config['model']['hidden_channels'],
        out_channels=config['model']['out_channels'],
        num_layers=config['model']['num_layers']
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config['train']['lr']), weight_decay=1e-4)

    # 动态权重计算
    train_labels = data_orig.y[data_orig.train_mask]
    tr_w = min(max((train_labels == 0).sum() / ((train_labels == 1).sum() + 1e-6) * 0.7, 5.0), 30.0)

    best_val_auc = -1.0
    best_thr = 0.5
    os.makedirs('pytorch_models', exist_ok=True)

    # --- 5. 训练循环 ---
    print(f"开始训练，木马权重: {tr_w:.2f}")
    for epoch in range(config['train']['epochs']):
        model.train()
        optimizer.zero_grad()
        preds_o_all = model(data_orig.x, data_orig.edge_index)
        preds_t_all = model(data_trans.x, data_trans.edge_index)

        loss_val, _, _, _, _, _, _ = siamese_loss(
            preds_o_all, preds_t_all, 
            data_orig.y[data_orig.train_mask], data_trans.y[data_trans.train_mask],
            data_orig, data_trans,
            lambda_const=0.0, lambda_det=0.3, lambda_nor=1.5, lambda_pos=10.0,
            trojan_w=25.0, const_mode='sym_kl' # 改用 sym_kl 提升一致性
        )
        loss_val.backward()
        optimizer.step()

        if (epoch + 1) % 10 == 0:
            model.eval()
            with torch.no_grad():
                val_probs = F.softmax(model(data_orig.x, data_orig.edge_index)[data_orig.val_mask], dim=1)
                val_labels = data_orig.y[data_orig.val_mask]
                
                # 计算验证集 PR-AUC
                val_auc = average_precision_score(val_labels.cpu(), val_probs[:, 1].cpu())
                # 寻找验证集最优阈值
                sweep = perform_threshold_sweep(val_probs, val_labels)
                recs = np.array(sweep['rec'])
                indices_above_70 = np.where(recs >= 0.70)[0]
                if len(indices_above_70) > 0:
                    current_thr = sweep['thr'][indices_above_70[np.argmax(np.array(sweep['macro_f1'])[indices_above_70])]]
                else:
                    current_thr = sweep['thr'][np.argmax(recs)]

                print(f"Epoch {epoch+1:03d} | Loss: {loss_val.item():.4f} | Val PR-AUC: {val_auc:.4f} | BestThr: {current_thr:.3f}")

                if val_auc > best_val_auc:
                    best_val_auc = val_auc
                    best_thr = current_thr
                    torch.save(model.state_dict(), f'pytorch_models/selected_test_model.pkl')

    # --- 6. 最终评估与 CSV 生成 ---
    print(f"\n>>> 训练完成。加载最优模型 (Val AUC: {best_val_auc:.4f}) 使用阈值: {best_thr:.4f}")
    model.load_state_dict(torch.load(f'pytorch_models/selected_test_model.pkl'))
    
    # 生成测试集分析报表 (TP, FP, FN 详细列表)
    print("正在生成测试集样本分析报表...")
    analyze_samples_unified(model, data_orig, best_thr, g_map, mask_type='test')
    
    # 生成验证集分析报表
    print("正在生成验证集样本分析报表...")
    analyze_samples_unified(model, data_orig, best_thr, g_map, mask_type='val')

    print("\n[成功] 已生成以下文件：")
    print(f"1. node_sample_analysis_test.csv (测试文件 {TARGET_TEST_FILE} 的节点详情)")
    print(f"2. node_sample_analysis_val.csv (验证集 3 个电路的节点详情)")

if __name__ == "__main__":
    train()