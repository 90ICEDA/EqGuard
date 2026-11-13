"""Publish single-factor evidence without altering frozen historical results."""
from pathlib import Path
import csv,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;DOC=R/'10.15/00_说明';BASE=R/'_p0pilot/cec_pretrain_seed42_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
 assert (O/'MECHANISM_COMPLETE.json').exists()
 det=[]
 for setting,folder in [('0.2',BASE),('0',O)]:
  for r in csv.DictReader((folder/'detection_metrics.csv').open(encoding='utf-8-sig')):
   if r['operation']=='historical_fpr5':det.append(dict(dropout=setting,**r))
 mech=list(csv.DictReader((O/'mechanism_comparison.csv').open(encoding='utf-8-sig')))
 def table(rows,keys):
  out='|'+'|'.join(keys)+'|\n|'+'|'.join(['---']*len(keys))+'|\n'
  for row in rows:
   vals=[]
   for k in keys:
    v=row[k]
    try:v=f'{float(v):.5f}' if k not in ['dropout','arm','split','stage','space','selected_update'] else str(v)
    except (ValueError,TypeError):v=str(v)
    vals.append(v)
   out+='|'+'|'.join(vals)+'|\n'
  return out
 report='# 功能预训练dropout单因素检验（seed42，2026-11-05）\n\n'
 report+='## 实验合同与实际执行\n\n只改变50次功能预训练中的编码器dropout：两个分支各2处、post输出1处，共5处p=0.2改为0。没有使用model.eval()替代，BatchNorm始终保持原训练行为。随后200次微调恢复p=0.2，原分类监督/损失/旧H采样表/优化器/选模全部不变。Z/R/P同步修改，旧p=0.2三组直接复用，新三组共750次优化更新；仍仅seed42，0新增SAT。\n\n'
 report+='39维v3、同图、同标签、同初始化、同投影头初始化、同50预训练+200微调预算、同382唯一配对/500名额、同已证函数不同负边及方差项。冻结合同和原始脚本按哈希核对，旧检查点未改写。dropout移除后随机数消耗自然改变，属于该单因素干预的结果，不要求后续权重逐位相同。\n\n'
 report+='每组预训练实测250次dropout调用被关闭；微调前还原原函数。首步检查包含显存、有限损失/权重、表示标准差及BN累计次数；后续保留全部50/200步历史和检查点。\n\n'
 report+='## 检测结果\n\n微调每5次用验证AP选模；阈值仅在验证集校准。下表AP不依赖阈值；r1/r5按原实现报告。测试为历史固定留出探索性结果，不据此选择本轮设置。\n\n'+table(det,['dropout','arm','split','selected_update','ap','auc','r1','r5'])
 report+='\n## 函数区分诊断\n\n复用上一轮20个验证集函数不同反例块，不追加SAT。每个源对象内计算同函数/不同函数距离AUC，再对源等权，越接近1越能区分；0.5为无区分。验证负块小且已有分析，属于机制诊断。concat128为根64+锥均值64；微调best阶段投影头仅作为冻结读出探针，实际检测不使用投影头。所有评估均关闭dropout并使用BN运行统计，因此不会把单次训练噪声直接当成函数差异。\n\n'
 report+=table([r for r in mech if r['space'] in ['root64','projection32']],['dropout','arm','stage','space','same_vs_different_auc','same_rms','different_rms','source_balanced_effective_rank'])
 report+='\n## 解释边界\n\n配对来源集中和同源重复曝光保持旧合同不变，避免混入第二个因素。这一检验只能回答当前协议下移除功能预训练dropout的影响，不能独立证明其他数据分布、随机种子或损失配置的结论；不能把距离整体缩小视为功能能力提高。检测AP、不同函数区分和微调保留须分别判断。尚未加入表示区分新目标或微调保持项。\n\n证据目录：`_p0pilot/cec_dropout_seed42_20261105/`，EXECUTION_CONTRACT、FIRST_*、DROPOUT_*、TRAINING_COMPLETE、ANALYSIS_COMPLETE、MECHANISM_COMPLETE、mechanism_comparison.csv及全部检查点。\n'
 path=DOC/'等价锥功能预训练dropout单因素检验_seed42_20261105.md';path.write_text(report,encoding='utf-8')
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(path.relative_to(R)),detection=det),ensure_ascii=False,indent=2),encoding='utf-8')
 print(path)
if __name__=='__main__':main()
