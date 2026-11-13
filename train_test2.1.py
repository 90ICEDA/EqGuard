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

# --- 困难样本变体映射（train_mode=4 时使用）---
FIXED_TRANS_VARIANTS = {
    'rs232t1000': 'rs232t1000tr43',
    's15850t100': 's15850t100tr42',
    's38417t300': 's38417t300tr42',
    's38584t100': 's38584t100tr42',
    's35932t200': 's35932t200tr42'
}

def get_file_level_loco_masks(file_ids, prefixes, target_file, val_size=1, is_trans=False,
                              include_trans_in_train=False, use_fixed_trans=False):
    file_ids_arr = np.array(file_ids)
    prefixes_arr = np.array(prefixes)

    # --- 1. 确定基准前缀 ---
    clean_name = re.sub(r'(_tr|tr|equiv|_equiv)\d*$', '', target_file)
    match = re.search(r'^(.+?)(?=t\d|_tr|tr\d|equiv)', clean_name)
    target_prefix = match.group(1).rstrip('_') if match else clean_name

    unique_prefixes = sorted(list(set(prefixes)))
    available_prefixes = [p for p in unique_prefixes if p != target_prefix]

    random.seed(len(target_file) + sum(ord(c) for c in target_file))
    actual_val_size = min(len(available_prefixes), val_size)
    val_prefixes = random.sample(available_prefixes, actual_val_size)
    train_prefixes = [p for p in available_prefixes if p not in val_prefixes]

    # --- 2. Trans 域的选择逻辑 ---
    if is_trans:
        test_mask_np = np.array([str(fid).startswith(target_file) for fid in file_ids])
        train_mask = torch.zeros(len(file_ids), dtype=torch.bool)
        val_mask = torch.zeros(len(file_ids), dtype=torch.bool)

        if include_trans_in_train:
            def pick_fid_for_prefix(p):
                """为指定前缀选择一个文件ID，优先固定困难样本"""
                p_fids = sorted(list(set(file_ids_arr[prefixes_arr == p])))
                if not p_fids:
                    return None
                picked_fid = None
                # 优先使用固定困难样本
                if use_fixed_trans:
                    for fid in p_fids:
                        fid_clean = fid.replace('.v', '')
                        base_name = re.sub(r'(_tr|tr|equiv|_equiv)\d*$', '', fid_clean)
                        if base_name in FIXED_TRANS_VARIANTS:
                            target_variant = FIXED_TRANS_VARIANTS[base_name]
                            for candidate in p_fids:
                                if candidate.replace('.v', '') == target_variant:
                                    picked_fid = candidate
                                    break
                            if picked_fid:
                                break
                # 回退到随机选择
                if picked_fid is None:
                    random.seed(sum(ord(c) for c in (p + target_file)))
                    picked_fid = random.choice(p_fids)
                return picked_fid

            # 训练前缀
            for p in train_prefixes:
                fid = pick_fid_for_prefix(p)
                if fid:
                    train_mask[file_ids_arr == fid] = True

            # 验证前缀
            for p in val_prefixes:
                fid = pick_fid_for_prefix(p)
                if fid:
                    val_mask[file_ids_arr == fid] = True

        return train_mask, val_mask, torch.from_numpy(test_mask_np)

    # --- 3. Orig 域逻辑（保持不变）---
    test_mask_np = (file_ids_arr == target_file)
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

def calibrate_threshold(probs, labels, strategy='recall_first', target_recall=0.85, target_fpr=0.05):
    """
    通用阈值校准函数
    strategy='recall_first': 在 Recall > target_recall 的点中，找 FPR 最大的 (或按需改为最小)
    strategy='fpr_first': 在 FPR <= target_fpr 的点中，找 Recall 最大的
    """
    trojan_probs = probs[:, 1].cpu().numpy()
    y_true = labels.cpu().numpy()
    
    # 获取 PR 曲线的阈值点
    precisions, recalls, thresholds = precision_recall_curve(y_true, trojan_probs)
    # 计算对应的 FPR
    # FPR = FP / (FP + TN)
    fprs = []
    for t in thresholds:
        y_pred = (trojan_probs >= t).astype(int)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0,0,0,0)
        fprs.append(fp / (fp + tn + 1e-10))
    fprs = np.array(fprs)
    recalls_trimmed = recalls[:len(thresholds)] # 对齐长度

    if strategy == 'recall_first':
        # 模式 A: Recall > 0.85 时，FPR 最大 (通常用于寻找 Mixed-label region 的边界)
        valid_indices = np.where(recalls_trimmed > target_recall)[0]
        if len(valid_indices) == 0:
            best_idx = np.argmax(recalls_trimmed) # 找不到就选召回最高的
        else:
            # 在满足召回的点里找 FPR 最大的
            sub_idx = np.argmax(fprs[valid_indices])
            best_idx = valid_indices[sub_idx]
            
    elif strategy == 'fpr_first':
        # 模式 B: FPR <= 5% 时，Recall 最大 (工业界常用，控制误报前提下求最高检出)
        valid_indices = np.where(fprs <= target_fpr)[0]
        if len(valid_indices) == 0:
            best_idx = np.argmin(fprs) # 找不到就选误报最低的
        else:
            # 在满足误报率的点里找 Recall 最大的
            sub_idx = np.argmax(recalls_trimmed[valid_indices])
            best_idx = valid_indices[sub_idx]
    else:
        best_idx = len(thresholds) // 2 # 默认中间值

    actual_threshold = thresholds[min(best_idx, len(thresholds)-1)]
    return actual_threshold


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




from collections import defaultdict

def analyze_samples_unified(model, data_o, data_t, threshold, glook, save_dir, filename, mask_type='test'):
    model.eval()
    output_path = os.path.join(save_dir, filename)
    
    # 1. 确定掩码
    mask_o = data_o.test_mask if mask_type == 'test' else data_o.val_mask
    mask_t = data_t.test_mask if mask_type == 'test' else data_t.val_mask
    
    # 2. 建立 Trans 到 Orig 的反向映射索引
    align = data_t.alignment
    t_to_o_map = {align[1, i].item(): align[0, i].item() for i in range(align.shape[1])}

    # 3. 准备门类型映射
    actual_lookup = glook.get('gatelookup', glook)
    idx_to_gate = {v: k for k, v in actual_lookup.items() if isinstance(v, (int, float))}
    num_gate_types = len(idx_to_gate)

    results = []

    with torch.no_grad():
        # --- 处理 Orig 侧节点 ---
        probs_o = F.softmax(model(data_o.x, data_o.edge_index), dim=1)[:, 1].cpu().numpy()
        y_o = data_o.y.cpu().numpy()
        feats_o = data_o.x.cpu().numpy()
        fids_o = np.array(data_o.file_ids)
        
        o_indices = torch.where(mask_o)[0].cpu().numpy()
        for idx in o_indices:
            p = probs_o[idx]
            lab = int(y_o[idx])
            stype = ('TP' if p >= threshold else 'FN') if lab == 1 else ('FP' if p >= threshold else 'TN')
            
            # 数值还原逻辑：np.expm1 是 log1p 的逆运算，round确保精度误差不影响整数转换
            results.append({
                'netlist': fids_o[idx], 
                'node_idx': idx, 
                'is_orig': 1, 
                'paired_idx': idx,
                'sample_type': stype, 
                'gate': idx_to_gate.get(np.argmax(feats_o[idx, :num_gate_types]), "Unknown"),
                'label': lab, 
                'score': float(p),
                # 物理特征还原
                'dist_pi': int(round(np.expm1(feats_o[idx, 29]))),
                'dist_po': int(round(np.expm1(feats_o[idx, 30]))),
                'fan_in_2hop': int(round(np.expm1(feats_o[idx, 31]))),
                'fan_out_2hop': int(round(np.expm1(feats_o[idx, 32])))
            })

        # --- 处理 Trans 侧节点 ---
        probs_t = F.softmax(model(data_t.x, data_t.edge_index), dim=1)[:, 1].cpu().numpy()
        y_t = data_t.y.cpu().numpy()
        feats_t = data_t.x.cpu().numpy()
        fids_t = np.array(data_t.file_ids)

        t_indices = torch.where(mask_t)[0].cpu().numpy()
        for idx in t_indices:
            p = probs_t[idx]
            lab = int(y_t[idx])
            stype = ('TP' if p >= threshold else 'FN') if lab == 1 else ('FP' if p >= threshold else 'TN')
            
            results.append({
                'netlist': fids_t[idx], 
                'node_idx': idx, 
                'is_orig': 0, 
                'paired_idx': t_to_o_map.get(idx, -1),
                'sample_type': stype, 
                'gate': idx_to_gate.get(np.argmax(feats_t[idx, :num_gate_types]), "Unknown"),
                'label': lab, 
                'score': round(float(p), 4),
                # 物理特征还原
                'dist_pi': int(round(np.expm1(feats_t[idx, 29]))),
                'dist_po': int(round(np.expm1(feats_t[idx, 30]))),
                'fan_in_2hop': int(round(np.expm1(feats_t[idx, 31]))),
                'fan_out_2hop': int(round(np.expm1(feats_t[idx, 32])))
            })

    # 4. 导出 CSV
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"  [成功] 节点分析报告已保存至: {output_path}")

def plot_score_distribution(tp_scores, fp_scores, tn_scores, fn_scores, threshold, save_path):
    """
    绘制 TP, FP, TN, FN 四类样本的分数分布图
    """
    plt.figure(figsize=(12, 7))
    
    # 设置 bins 确保对比清晰
    bins = np.linspace(0, 1, 50)
    
    # 绘制分布
    # 我们通常最关注 TP 和 FP 的重叠
    if len(tn_scores) > 0 and not np.isnan(tn_scores).all():
        plt.hist(tn_scores, bins=bins, alpha=0.3, label=f'TN n={len(tn_scores)}', color='gray', density=True)
    
    if len(fn_scores) > 0 and not np.isnan(fn_scores).all():
        plt.hist(fn_scores, bins=bins, alpha=0.5, label=f'FN n={len(fn_scores)}', color='orange', density=True)
        
    if len(fp_scores) > 0 and not np.isnan(fp_scores).all():
        plt.hist(fp_scores, bins=bins, alpha=0.5, label=f'FP n={len(fp_scores)}', color='red', density=True)
        
    if len(tp_scores) > 0 and not np.isnan(tp_scores).all():
        plt.hist(tp_scores, bins=bins, alpha=0.7, label=f'TP n={len(tp_scores)}', color='green', density=True)
    
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

def _group_mean(values, group_ids, num_groups):
    """
    values: [N, D] tensor
    group_ids: [N] long tensor，取值 0..num_groups-1
    返回: [num_groups, D]，每个组内均值
    """
    out = torch.zeros(num_groups, values.shape[1], device=values.device, dtype=values.dtype)
    cnt = torch.zeros(num_groups, device=values.device, dtype=values.dtype)
    out.index_add_(0, group_ids, values)
    cnt.index_add_(0, group_ids, torch.ones(values.shape[0], device=values.device, dtype=values.dtype))
    cnt = cnt.clamp_min(1e-10).unsqueeze(1)
    return out / cnt


def compute_consistency_loss(preds_o, preds_t, alignment, mask_o, mask_t,
                             mode='mae_prob', group_by_orig=True):
    """
    计算配对节点的一致性损失 (L_const)。
    只计算同时处于 Orig 和 Trans 训练集内的配对，防止验证/测试集泄露。
    group_by_orig=True: 对同一 Orig 门的 N 个 Trans 配对先组内平均，再与 Orig 比较。
                       每个 Orig 门对 loss 贡献相同，不受映射比影响。
    group_by_orig=False: 逐配对计算（旧行为，高映射比门主导）。
    """
    idx_o = alignment[0]
    idx_t = alignment[1]

    train_pair_mask = mask_o[idx_o] & mask_t[idx_t]
    sel_idx_o = idx_o[train_pair_mask]
    sel_idx_t = idx_t[train_pair_mask]

    if len(sel_idx_o) == 0:
        return torch.tensor(0.0, device=preds_o.device)

    logits_o = preds_o[sel_idx_o]
    logits_t = preds_t[sel_idx_t]
    T = 0.5
    p_o = F.softmax(logits_o / T, dim=1)
    p_t = F.softmax(logits_t / T, dim=1)

    # ---------- 逐配对 ----------
    if not group_by_orig:
        if mode == 'mse_logit':
            return F.mse_loss(logits_o, logits_t)
        elif mode == 'sym_kl':
            log_p_o = F.log_softmax(logits_o / T, dim=1)
            log_p_t = F.log_softmax(logits_t / T, dim=1)
            kl_ot = F.kl_div(log_p_t, p_o, reduction='batchmean')
            kl_to = F.kl_div(log_p_o, p_t, reduction='batchmean')
            return (kl_ot + kl_to) / 2.0
        elif mode == 'mae_prob':
            return F.l1_loss(p_o, p_t)
        return torch.tensor(0.0, device=preds_o.device)

    # ---------- 按 Orig 分组 ----------
    unique_o, inverse = torch.unique(sel_idx_o, return_inverse=True)
    num_orig = unique_o.shape[0]

    if mode == 'mse_logit':
        logits_o_avg = _group_mean(logits_o, inverse, num_orig)
        logits_t_avg = _group_mean(logits_t, inverse, num_orig)
        return F.mse_loss(logits_o_avg, logits_t_avg)

    elif mode == 'sym_kl':
        p_o_avg = _group_mean(p_o, inverse, num_orig)
        p_t_avg = _group_mean(p_t, inverse, num_orig)
        # 平均后重新归一化，保证是合法分布
        p_o_avg = p_o_avg / p_o_avg.sum(dim=1, keepdim=True).clamp_min(1e-10)
        p_t_avg = p_t_avg / p_t_avg.sum(dim=1, keepdim=True).clamp_min(1e-10)
        log_p_o = torch.log(p_o_avg + 1e-10)
        log_p_t = torch.log(p_t_avg + 1e-10)
        kl_ot = F.kl_div(log_p_t, p_o_avg, reduction='batchmean')
        kl_to = F.kl_div(log_p_o, p_t_avg, reduction='batchmean')
        return (kl_ot + kl_to) / 2.0

    elif mode == 'mae_prob':
        p_o_avg = _group_mean(p_o, inverse, num_orig)
        p_t_avg = _group_mean(p_t, inverse, num_orig)
        # p_o 对同一 Orig 重复了 N 次，均值仍等于原值；p_t 是 N 个 Trans 的平均
        return F.l1_loss(p_o_avg, p_t_avg)

    return torch.tensor(0.0, device=preds_o.device)

from scipy.stats import spearmanr, wilcoxon # 确保导入了 wilcoxon

def calc_detailed_consistency(preds_o, preds_t, labels_o, alignment, threshold, top_k=50):
    """
    返回 12 个指标，每个指标都有「逐对」和「PerOrig（按 Orig 分组去偏）」两版。
    PerOrig 消除映射比偏差：每个 Orig 门在统计中权重相同，不受它被拆成多少子节点影响。
    """
    with torch.no_grad():
        idx_o_np = alignment[0].cpu().numpy()
        p_o = F.softmax(preds_o[alignment[0]], dim=1)[:, 1].cpu().numpy()
        p_t = F.softmax(preds_t[alignment[1]], dim=1)[:, 1].cpu().numpy()
        y_true = labels_o[alignment[0]].cpu().numpy()

        # ============ 逐对版本（保留兼容） ============
        diff = np.abs(p_o - p_t)
        paired_mae = float(np.mean(diff))

        t_mask = (y_true == 1)
        b_mask = (y_true == 0)
        t_drift = float(np.mean(p_t[t_mask] - p_o[t_mask])) if t_mask.any() else 0.0
        b_drift = float(np.mean(p_t[b_mask] - p_o[b_mask])) if b_mask.any() else 0.0

        f_o = (p_o >= threshold).astype(int)
        f_t = (p_t >= threshold).astype(int)
        flip_rate = float(np.mean(f_o != f_t))

        if len(np.unique(p_o)) > 1 and len(np.unique(p_t)) > 1:
            rank_corr, _ = spearmanr(p_o, p_t)
        else:
            rank_corr = 0.0

        k = min(top_k, len(p_o))
        top_k_o = np.argsort(p_o)[-k:]
        top_k_t = np.argsort(p_t)[-k:]
        overlap = float(len(np.intersect1d(top_k_o, top_k_t)) / k)

        # ============ PerOrig 版本（每个 Orig 门等权） ============
        unique_o = np.unique(idx_o_np)
        num_orig = len(unique_o)
        if num_orig > 0:
            # 每个 Orig 门的组内平均
            p_o_po = np.array([p_o[idx_o_np == o].mean() for o in unique_o])
            p_t_po = np.array([p_t[idx_o_np == o].mean() for o in unique_o])
            y_po = np.array([y_true[idx_o_np == o][0] for o in unique_o])

            # MAE / Orig
            paired_mae_per_orig = float(np.abs(p_o_po - p_t_po).mean())

            # Trojan / Benign Drift / Orig
            t_po = (y_po == 1)
            b_po = (y_po == 0)
            t_drift_po = float(np.mean(p_t_po[t_po] - p_o_po[t_po])) if t_po.any() else 0.0
            b_drift_po = float(np.mean(p_t_po[b_po] - p_o_po[b_po])) if b_po.any() else 0.0

            # Flip Rate / Orig（每个 Orig 平均概率过阈值是否翻转）
            f_o_po = (p_o_po >= threshold).astype(int)
            f_t_po = (p_t_po >= threshold).astype(int)
            flip_rate_po = float(np.mean(f_o_po != f_t_po))

            # Spearman / Orig（对唯一的 Orig 概率向量求秩相关）
            if len(np.unique(p_o_po)) > 1 and len(np.unique(p_t_po)) > 1:
                rank_corr_po, _ = spearmanr(p_o_po, p_t_po)
            else:
                rank_corr_po = 0.0

            # TopK Overlap / Orig（在唯一的 Orig 概率上取 TopK）
            k_po = min(top_k, num_orig)
            tk_o_po = np.argsort(p_o_po)[-k_po:]
            tk_t_po = np.argsort(p_t_po)[-k_po:]
            overlap_po = float(len(np.intersect1d(tk_o_po, tk_t_po)) / k_po)
        else:
            paired_mae_per_orig = 0.0
            t_drift_po = b_drift_po = 0.0
            flip_rate_po = rank_corr_po = overlap_po = 0.0

    return {
        # ---- 逐对版本（原有） ----
        'Paired_MAE':           paired_mae,
        'Trojan_Drift':         t_drift,
        'Benign_Drift':         b_drift,
        'Flip_Rate':            flip_rate,
        'Spearman_Corr':        rank_corr,
        'TopK_Overlap':         overlap,
        # ---- PerOrig 版本（新增，消除映射比偏差） ----
        'Paired_MAE_PerOrig':    paired_mae_per_orig,
        'Trojan_Drift_PerOrig':  t_drift_po,
        'Benign_Drift_PerOrig':  b_drift_po,
        'Flip_Rate_PerOrig':     flip_rate_po,
        'Spearman_Corr_PerOrig': rank_corr_po,
        'TopK_Overlap_PerOrig':  overlap_po,
    }

def calc_paired_consistency_metrics(preds_o, preds_t, alignment):
    """
    返回 (paired_mae, paired_mae_per_orig, rank_corr)
    - paired_mae:          逐配对 |p_o - p_t| 的均值（原指标）
    - paired_mae_per_orig: 对每个 Orig 门先对其 N 个配对求均值，再对 Orig 取平均
    - rank_corr:           Spearman 秩相关
    """
    with torch.no_grad():
        idx_o = alignment[0]
        idx_t = alignment[1]
        p_o = F.softmax(preds_o[idx_o], dim=1)[:, 1].cpu().numpy()
        p_t = F.softmax(preds_t[idx_t], dim=1)[:, 1].cpu().numpy()
        idx_o_np = idx_o.cpu().numpy()

        diff = np.abs(p_o - p_t)
        paired_mae = float(np.mean(diff))

        # 按 Orig 分组
        unique_o = np.unique(idx_o_np)
        if len(unique_o) > 0:
            per_orig = np.array([diff[idx_o_np == o].mean() for o in unique_o])
            paired_mae_per_orig = float(per_orig.mean())
        else:
            paired_mae_per_orig = 0.0

        if len(np.unique(p_o)) > 1 and len(np.unique(p_t)) > 1:
            rank_corr, _ = spearmanr(p_o, p_t)
        else:
            rank_corr = 0.0

    return paired_mae, paired_mae_per_orig, rank_corr
def siamese_loss(preds_o_all, preds_t_all, labels_o, labels_t, data_o, data_t,
                 lambda_const=2.0, lambda_det=2.0, lambda_nor=1.0, lambda_pos=10.0,
                 trojan_w=8.0, loss_type='ce', use_hnm=False, const_mode='mae_prob',
                 include_trans_loss=False):
    device = preds_o_all.device
    mask_o, mask_t = data_o.train_mask, data_t.train_mask
    preds_o_train = preds_o_all[mask_o]
    weight = torch.tensor([1.0, trojan_w], device=device)
    T = 0.5
    
    # --- 1. 原始图 (Orig) 基本指标 ---
    if use_hnm:
        task_loss_o = hnm_loss(preds_o_train, labels_o, mining_ratio=0.1, hard_weight=10.0, base_weight=weight)
    else:
        task_loss_o = compute_task_loss(preds_o_train, labels_o, loss_type=loss_type, weight=weight)
    
    probs_o_train = F.softmax(preds_o_train/T, dim=1)
    F1mic_o, F1mac_o, _, sdr_tr_o = calc_soft_f1_metrics(probs_o_train, labels_o)

    # --- 2. 变换图 (Trans) 基本指标 ---
    task_loss_t = torch.tensor(0.0, device=device)
    F1mic_t, F1mac_t, sdr_tr_t = torch.tensor(0.0, device=device), torch.tensor(0.0, device=device), torch.tensor(0.0, device=device)
    
    # 预初始化 Trans 侧的惩罚项为 0
    loss_det_rate_t = torch.tensor(0.0, device=device)
    penalty_t = torch.tensor(0.0, device=device)

    if include_trans_loss and mask_t.any():
        preds_t_train = preds_t_all[mask_t]
        if use_hnm:
            task_loss_t = hnm_loss(preds_t_train, labels_t, mining_ratio=0.1, hard_weight=10.0, base_weight=weight)
        else:
            task_loss_t = compute_task_loss(preds_t_train, labels_t, loss_type=loss_type, weight=weight)
        
        probs_t_train = F.softmax(preds_t_train/T, dim=1)
        F1mic_t, F1mac_t, _, sdr_tr_t = calc_soft_f1_metrics(probs_t_train, labels_t)

        loss_det_rate_t = torch.pow(1.0 - sdr_tr_t, 2)
        dist_pi_t = data_t.x[data_t.train_mask][:, 29]
        penalty_t = torch.mean(probs_t_train[:, 1] * (1.0 / (dist_pi_t + 0.5)))

    # --- 3. 综合损失计算 ---
    # 一致性损失
    loss_const = compute_consistency_loss(preds_o_all, preds_t_all, data_t.alignment, mask_o, mask_t, mode=const_mode, group_by_orig=True)
    
    # 检出率损失 (Orig + Trans)
    # 在 Mode 1 下，loss_det_rate_t 是 0
    loss_det_total = torch.pow(1.0 - sdr_tr_o, 2) + loss_det_rate_t
    
    # 位置惩罚 (Orig + Trans)
    dist_pi_o = data_o.x[data_o.train_mask][:, 29]
    penalty_o = torch.mean(probs_o_train[:, 1] * (1.0 / (dist_pi_o + 0.5)))
    penalty_total = penalty_o + penalty_t

    # 汇总总损失
    total_loss = (task_loss_o + task_loss_t) + \
                 lambda_const * loss_const + \
                 lambda_det * loss_det_total + \
                 lambda_pos * penalty_total

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
    config_path = os.path.join(current_dir, 'config.yaml')
    if not os.path.exists(config_path):
        print(f"错误: 找不到配置文件 {config_path}")
        return
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    seed_everything(config['train']['seed_id'])
    
    device = torch.device(config['train']['device'] if torch.cuda.is_available() else 'cpu')
    print(f"训练设备: {device}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_results_dir = os.path.join(current_dir, "results", f"run_{run_id}_seed{config['train']['seed_id']}mode{config['train']['train_mode']}")
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

        # 3.1 & 3.2 生成掩码 (传入 train_mode 开关)
        data_orig.train_mask, data_orig.val_mask, data_orig.test_mask = get_file_level_loco_masks(
            data_orig.file_ids, data_orig.prefixes, target_file, val_size=1, is_trans=False)

        
        include_trans = config['train']['train_mode'] in [2, 3, 4]
        use_fixed = (config['train']['train_mode'] == 4)

        data_trans.train_mask, data_trans.val_mask, data_trans.test_mask = get_file_level_loco_masks(
            data_trans.file_ids, data_trans.prefixes, target_file, val_size=1, is_trans=True,
            include_trans_in_train=include_trans, use_fixed_trans=use_fixed)

        # 记录 log.txt
        train_f_o = sorted(list(set(np.array(data_orig.file_ids)[data_orig.train_mask.cpu().numpy()])))
        val_f_o = sorted(list(set(np.array(data_orig.file_ids)[data_orig.val_mask.cpu().numpy()])))
        test_f_o = sorted(list(set(np.array(data_orig.file_ids)[data_orig.test_mask.cpu().numpy()])))
        test_f_t = sorted(list(set(np.array(data_trans.file_ids)[data_trans.test_mask.cpu().numpy()])))
        with open(os.path.join(circuit_results_dir, "log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Script Name: {os.path.basename(__file__)}\n")
            f.write(f"Training Mode: {config['train']['train_mode']}\n")
            f.write(f"Train (Orig): {', '.join(train_f_o)}\n")
            if config['train']['train_mode'] in [2, 3, 4]:
                train_f_t = sorted(list(set(np.array(data_trans.file_ids)[data_trans.train_mask.cpu().numpy()])))
                f.write(f"Train (Trans): {', '.join(train_f_t)}\n")
            f.write(f"Validation (Orig): {', '.join(val_f_o)}\n")
            f.write(f"Test Target (All): {', '.join(test_f_o + test_f_t)}\n")


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
        BEST_MODEL_STRATEGY = 'pr_auc'
        TARGET_RECALL = 0.85


        # --- 4. 内部训练循环 ---
        for epoch in range(config['train']['epochs']):
            model.train()
            optimizer.zero_grad()
            preds_o_all = model(data_orig.x, data_orig.edge_index)
            preds_t_all = model(data_trans.x, data_trans.edge_index)

            hnm_enabled = False if epoch >= 30 else False
            # const_strategy = 'mse_logit' # 可选: 'mse_logit', 'sym_kl', 'mae_prob'
            # selected_loss = 'ce'# 可选：'ce', 'focal', 'asl'

            final_lambda_const = config['siamese']['lambda_const'] if config['train']['train_mode'] in [3, 4] else 0.0



            # 核心：仅使用训练集掩码节点计算 Siamese Loss
            loss_val, smic_o, smac_o, smic_t, smac_t , sdr_o, sdr_t = siamese_loss(
                preds_o_all, 
                preds_t_all, 
                data_orig.y[data_orig.train_mask], 
                data_trans.y[data_trans.train_mask],
                data_orig,
                data_trans,
                lambda_const=final_lambda_const,
                lambda_det=config['siamese']['lambda_det'],
                lambda_nor=config['siamese']['lambda_nor'],
                lambda_pos=config['siamese']['lambda_pos'],
                trojan_w=config['siamese']['trojan_w'],
                loss_type=config['siamese']['loss_type'],
                use_hnm=hnm_enabled,
                const_mode=config['siamese']['const_mode'],
                include_trans_loss=(config['train']['train_mode'] in [2,3,4])
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

                    current_pr_auc = average_precision_score(val_labels_o.cpu(), val_probs_o[:, 1].cpu())
                    
                    # 获取全阈值扫描结果
                    sweep = perform_threshold_sweep(val_probs_o, val_labels_o)
                    recs = np.array(sweep['rec'])
                    f1s = np.array(sweep['macro_f1'])
                    fprs = np.array(sweep['fpr'])
                    thrs = np.array(sweep['thr'])

                    # --- 根据不同策略计算当前得分 ---
                    current_epoch_score = 0.0
                    

                    calibrated_thr = calibrate_threshold(
                        val_probs_o, val_labels_o, 
                        strategy=config['train']['thr_strategy'],
                        target_recall=0.85, target_fpr=0.05
                    )

                    if BEST_MODEL_STRATEGY == 'pr_auc':
                        current_epoch_score = current_pr_auc
                    elif BEST_MODEL_STRATEGY == 'fpr_at_recall':
                        # 原逻辑：Recall达标时的 1-FPR
                        sweep = perform_threshold_sweep(val_probs_o, val_labels_o)
                        recs = np.array(sweep['rec'])
                        fprs = np.array(sweep['fpr'])
                        idx_above = np.where(recs >= TARGET_RECALL)[0]
                        current_epoch_score = 1.0 - np.min(fprs[idx_above]) if len(idx_above) > 0 else np.max(recs)*0.1

                    # C. 计算 Orig 和 Trans 的各项指标
                    metrics_o = calculate_full_metrics(val_probs_o, val_labels_o, calibrated_thr)
                    
                    # --- 修改处：增加对空验证集的判断 ---
                    if val_labels_t.shape[0] > 0:
                        # 如果 Trans 有验证节点（Mode 2），正常计算
                        metrics_t = calculate_full_metrics(val_probs_t, val_labels_t, calibrated_thr)
                    else:
                        # 如果 Trans 没有验证节点（Mode 1），赋予全 0 占位符防止报错
                        metrics_t = {k: 0.0 for k in metrics_o.keys()}

                    # D. 计算一致性指标
                    p_mae, p_mae_per_orig, r_corr = calc_paired_consistency_metrics(logits_o_all, logits_t_all, data_trans.alignment)
                    c_gap = abs(metrics_o['PR-AUC'] - metrics_t['PR-AUC'])

                    print(f"  [Epoch {epoch+1:03d}] Loss: {loss_val.item():.4f} | Thr: {calibrated_thr:.3f}")
                    print(f"  Ep {epoch+1:03d} | Loss: {loss_val.item():.3f} | MAE: {p_mae:.4f} | Thr: {calibrated_thr:.2f}")
                    print(f"  [Val_O] PR-AUC: {metrics_o['PR-AUC']:.4f} | Rec: {metrics_o['Recall']:.4f} | FPR: {metrics_o['FPR']:.4f} | TP/FP/FN: {int(metrics_o['TP'])}/{int(metrics_o['FP'])}/{int(metrics_o['FN'])}")
                    print(f"  [Val_T] PR-AUC: {metrics_t['PR-AUC']:.4f} | Rec: {metrics_t['Recall']:.4f} | FPR: {metrics_t['FPR']:.4f} | TP/FP/FN: {int(metrics_t['TP'])}/{int(metrics_t['FP'])}/{int(metrics_t['FN'])}")
                    print(f"  [Match] Gap: {c_gap:.4f} | Paired-MAE: {p_mae:.4f}")

                    # 记录最优模型 (以验证集 PR-AUC 为准)
                    if current_epoch_score > best_fold_val_score:
                        best_fold_val_score = current_epoch_score
                        # 记录此时的阈值备用
                        best_threshold_from_val = calibrated_thr
                        torch.save(model.state_dict(), f'pytorch_models/best_file_{target_file}.pkl')
        # --- 6. 本轮 Fold 最终评估 ---
        model.load_state_dict(torch.load(f'pytorch_models/best_file_{target_file}.pkl'))
        model.eval()
        with torch.no_grad():
            # 1. 验证集阈值校准 (基于 Orig 验证集)
            # val_logits_best = model(data_orig.x, data_orig.edge_index)[data_orig.val_mask]
            # val_probs_best = F.softmax(val_logits_best, dim=1)
            # val_labels_best = data_orig.y[data_orig.val_mask]
            # best_sweep = perform_threshold_sweep(val_probs_best, val_labels_best)

            # recs_v, fprs_v, thrs_v = np.array(best_sweep['rec']), np.array(best_sweep['fpr']), np.array(best_sweep['thr'])
            # target_rec_limit = 0.85
            # target_indices = np.where(recs_v >= target_rec_limit)[0]

            calibrated_threshold = best_threshold_from_val

            print(f"--- Fold {target_file} 评估 (应用验证集最优阈值: {calibrated_threshold:.4f}) ---")

            # 2. 运行全量预测
            final_logits_o = model(data_orig.x, data_orig.edge_index)
            final_logits_t = model(data_trans.x, data_trans.edge_index)
            
            all_fids_o = np.array(data_orig.file_ids)
            all_fids_t = np.array(data_trans.file_ids)

            # 3. 评估 Original 并记录
            test_probs_o = F.softmax(final_logits_o[data_orig.test_mask], dim=1)
            test_labels_o = data_orig.y[data_orig.test_mask]
            res_o = calculate_full_metrics(test_probs_o, test_labels_o, threshold=calibrated_threshold)
            
            # 将 Orig 的结果存入总表
            loco_final_results.append({
                'Test_File': f"{target_file}_ORIG",
                'PR-AUC_O': res_o['PR-AUC'],
                'PR-AUC_T': np.nan, # Orig 行没有 Trans 指标
                'ROC-AUC_O': res_o['ROC-AUC'],
                'Recall_O': res_o['Recall'],
                'FPR_O': res_o['FPR'],
                'Threshold': calibrated_threshold,
                'Type': 'ORIG'
            })

            # 4. 遍历每个 Trans 变体，单独计算指标和一致性
            for t_fname in test_f_t:
                f_mask = (all_fids_t == t_fname)
                # 计算该变体的分类指标
                res_this_t = calculate_full_metrics(F.softmax(final_logits_t[f_mask], dim=1), data_trans.y[f_mask], calibrated_threshold)
                
                # 计算该变体相对于 Orig 的一致性指标 (Pair-wise)
                # 逻辑：过滤 alignment 使得只包含 [当前 Orig, 当前这个 Trans 变体]
                pair_mask = (all_fids_o[data_trans.alignment[0]] == target_file) & (all_fids_t[data_trans.alignment[1]] == t_fname)
                this_alignment = data_trans.alignment[:, pair_mask]
                
                if this_alignment.shape[1] > 0:
                    consist_metrics = calc_detailed_consistency(final_logits_o, final_logits_t, data_orig.y, this_alignment, calibrated_threshold)
                else:
                    consist_metrics = {k: np.nan for k in [
                        'Paired_MAE', 'Paired_MAE_PerOrig',
                        'Trojan_Drift', 'Trojan_Drift_PerOrig',
                        'Benign_Drift', 'Benign_Drift_PerOrig',
                        'Flip_Rate', 'Flip_Rate_PerOrig',
                        'Spearman_Corr', 'Spearman_Corr_PerOrig',
                        'TopK_Overlap', 'TopK_Overlap_PerOrig',
                    ]}

                # 将该变体的结果存入总表
                loco_final_results.append({
                    'Test_File': t_fname,
                    'PR-AUC_O': res_o['PR-AUC'], # 保留对应的 Orig 指标做参考
                    'PR-AUC_T': res_this_t['PR-AUC'],
                    'PR_Drop': res_o['PR-AUC'] - res_this_t['PR-AUC'],
                    'ROC-AUC_O': res_o['ROC-AUC'],
                    'ROC-AUC_T': res_this_t['ROC-AUC'],
                    'Recall_O': res_o['Recall'],
                    'Recall_T': res_this_t['Recall'],
                    'FPR_O': res_o['FPR'],
                    'FPR_T': res_this_t['FPR'],
                    'Consistency_Gap': abs(res_o['PR-AUC'] - res_this_t['PR-AUC']),
                    **consist_metrics,
                    'Threshold': calibrated_threshold,
                    'Type': 'TRANS'
                })

            # 5. 生成可视化图片 (代码保持不变)
            # A. 处理原始测试网表图片生成 (循环内逻辑不变)
            for f_name in test_f_o:
                f_mask = (all_fids_o == f_name)
                f_probs = F.softmax(final_logits_o[f_mask], dim=1)[:, 1].cpu().numpy()
                f_labels = data_orig.y[f_mask].cpu().numpy()
                f_preds = (f_probs >= calibrated_threshold).astype(int)
                tp_s, fp_s, tn_s, fn_s = f_probs[(f_labels==1)&(f_preds==1)], f_probs[(f_labels==0)&(f_preds==1)], f_probs[(f_labels==0)&(f_preds==0)], f_probs[(f_labels==1)&(f_preds==0)]
                plot_score_distribution(tp_s, fp_s, tn_s, fn_s, calibrated_threshold, os.path.join(circuit_results_dir, f"final_dist_{f_name}.png"))
                f_sweep = perform_threshold_sweep(F.softmax(final_logits_o[f_mask], dim=1), data_orig.y[f_mask])
                plot_dual_threshold_curves(f_sweep, f_sweep, calibrated_threshold, os.path.join(circuit_results_dir, f"final_sweep_{f_name}.png"))

            # B. 处理所有 Trans 变体图片生成 (循环内逻辑不变)
            for f_name in test_f_t:
                f_mask = (all_fids_t == f_name)
                f_probs = F.softmax(final_logits_t[f_mask], dim=1)[:, 1].cpu().numpy()
                f_labels = data_trans.y[f_mask].cpu().numpy()
                f_preds = (f_probs >= calibrated_threshold).astype(int)
                tp_s, fp_s, tn_s, fn_s = f_probs[(f_labels==1)&(f_preds==1)], f_probs[(f_labels==0)&(f_preds==1)], f_probs[(f_labels==0)&(f_preds==0)], f_probs[(f_labels==1)&(f_preds==0)]
                plot_score_distribution(tp_s, fp_s, tn_s, fn_s, calibrated_threshold, os.path.join(circuit_results_dir, f"final_dist_{f_name}.png"))
                orig_ref_name = f_name.split('tr')[0]
                o_ref_mask = (all_fids_o == orig_ref_name)
                o_sweep = perform_threshold_sweep(F.softmax(final_logits_o[o_ref_mask], dim=1), data_orig.y[o_ref_mask])
                t_sweep = perform_threshold_sweep(F.softmax(final_logits_t[f_mask], dim=1), data_trans.y[f_mask])
                plot_dual_threshold_curves(o_sweep, t_sweep, calibrated_threshold, os.path.join(circuit_results_dir, f"final_sweep_{f_name}.png"))

            # 6. 生成节点分析 CSV (保持原样)
            glook_path = os.path.join(current_dir, 'data/verilog_data/gatelookup_recommended.json')
            if os.path.exists(glook_path):
                with open(glook_path, 'r') as gj:
                    full_json = json.load(gj)
                    glook = full_json.get('gatelookup', full_json)
                analyze_samples_unified(model, data_orig, data_trans, calibrated_threshold, glook, circuit_results_dir, "node_test_analysis.csv", mask_type='test')
                analyze_samples_unified(model, data_orig, data_trans, calibrated_threshold, glook, circuit_results_dir, "node_val_analysis.csv", mask_type='val')

            # 7. 实时生成运行中汇总 CSV
            running_df = pd.DataFrame(loco_final_results)
            numeric_cols = running_df.select_dtypes(include=[np.number]).columns
            if len(loco_final_results) > 0:
                curr_mean = running_df[numeric_cols].mean()
                curr_std = running_df[numeric_cols].std()
                running_stats_rows = [
                    pd.Series({'Test_File': 'RUNNING_MEAN', **curr_mean}),
                    pd.Series({'Test_File': 'RUNNING_STD', **curr_std})
                ]
                running_report = pd.concat([running_df, pd.DataFrame(running_stats_rows)], ignore_index=True)
                running_csv_path = os.path.join(base_results_dir, 'running_summary.csv')
                running_report.to_csv(running_csv_path, index=False, encoding='utf-8-sig')
                shutil.copy(running_csv_path, os.path.join(circuit_results_dir, "current_progress.csv"))

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
    
    # --- 7.2 执行 Wilcoxon 检验 (修正对齐逻辑) ---
    try:
        # 1. 提取 TRANS 数据并清洗名称
        trans_df = summary_df[summary_df['Type'] == 'TRANS'].copy()
        # 统一去掉 tr 及之后的数字，得到基准名，例如 rs232t1000
        trans_df['Base_Name'] = trans_df['Test_File'].str.split('tr').str[0]
        # 按基准名分组求均值
        grouped_trans = trans_df.groupby('Base_Name')['PR-AUC_T'].mean()

        # 2. 提取 ORIG 数据并清洗名称
        orig_df = summary_df[summary_df['Type'] == 'ORIG'].copy()
        # 统一去掉 _ORIG 后缀，得到基准名，例如 rs232t1000
        orig_df['Base_Name'] = orig_df['Test_File'].str.replace('_ORIG', '', regex=False)
        orig_df = orig_df.set_index('Base_Name')

        # 3. 筛选两个集合中共同拥有的电路（取交集，防止 KeyError）
        common_circuits = grouped_trans.index.intersection(orig_df.index)
        
        if len(common_circuits) >= 2: # Wilcoxon 要求至少 2 个样本
            val_o = orig_df.loc[common_circuits]['PR-AUC_O'].values
            val_t = grouped_trans.loc[common_circuits].values
            
            # 检查两个数组是否完全一样（完全一样 wilcoxon 会报错）
            if np.array_equal(val_o, val_t):
                p_val = 1.0
            else:
                _, p_val = wilcoxon(val_o, val_t)
            print(f"修正后的 Wilcoxon P-value (N={len(common_circuits)}): {p_val:.4f}")
        else:
            p_val = 1.0
            print("样本量不足，无法执行 Wilcoxon 检验")
            
    except Exception as e:
        print(f"Wilcoxon 检验执行失败: {e}")
        p_val = 1.0

    # 7.4 构造统计行并拼接
    stats_rows = [
        pd.Series({'Test_File': 'MEAN', **stats_mean}),
        pd.Series({'Test_File': 'STD', **stats_std}),
        pd.Series({'Test_File': 'CI_95_LOW', **ci_low}),
        pd.Series({'Test_File': 'CI_95_HIGH', **ci_high}),
        pd.Series({'Test_File': 'WILCOXON_P', 'PR-AUC_O': p_val}) # PR_Drop列存Worst-case
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