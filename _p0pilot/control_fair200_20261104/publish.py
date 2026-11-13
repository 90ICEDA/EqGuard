from pathlib import Path
import json,csv,datetime,hashlib,collections
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];N=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def f(v):return f'{float(v):.4f}'
def pct(v):return f'{float(v)*100:.2f}%'
def main():
 assert (O/'ANALYSIS_COMPLETE.json').exists() and (O/'FAIRNESS_VERIFIED.json').exists()
 assert not (O/'PUBLISHED.json').exists(),'already published'
 m=read(O/'manifest.json');agg=rows(O/'aggregate.csv');g=rows(O/'global_metrics.csv');s=rows(O/'region_summary.csv');d=rows(O/'paired_source_deltas.csv')
 lines=['# 等预算正常区域监督实验：改进双分支200次（2026-11-04）','',
 '## 问题与结论边界','',
 '检验已有正常监督中的预算配置：针对制造来源可追溯的木马相似正常区域C，是否优于同视图同门型宿主背景H。不是首次加入正常对照，也不是删除正常图。不增加SAT、等价一致性或区域辅助损失。旧200次结果仅为历史参考，不能代替本轮H组。','',
 '## 冻结协议与实际预算','',
 '六次训练全部完成：H/C各seed42、1、2，每次200次更新，共1200次。使用ginvenv_gpu、39维v2、原有有向图、dual_mix_post_cat、split29、hidden64、2+2分支和1层融合后GIN，46620参数。Adam lr0.0002、weight_decay0.001、BF16、clip1；ASL与1.4倍soft-miss平方保持原实现。每5次按旧可信标签范围的木马视图平均验证AP选模。每个种子的两组从同一份初始化开始。','',
 '|侧|源对象|视图|每组唯一候选节点|公共正例/步|公共负例/步|替换负例槽/步|替换槽占监督条目|',
 '|---|---:|---:|---:|---:|---:|---:|---:|']
 for dm in ['orig','trans']:
  a=m['counts'][dm];lines.append(f"|{dm}|{a['sources']}|{a['views']}|{a['C_unique']}|{a['base_positive']}|{a['base_negative']}|320|{pct(320/(a['base_positive']+a['base_negative']+320))}|")
 lines += ['',
 '原始候选121/329节点，经同视图、同25类门型、结构14维训练归一化距离RMS≤2的一对一背景匹配后保留116/294；排除5/35个无共同支持节点。主实验仍有20个双侧源对象、20个orig视图及44个trans视图。公共监督排除全部原候选与匹配H并集，未匹配C也不混入公共监督。所有正例保持；其他正常监督仍在公共集合中。',
 '每源对象每步16个名额，轮换该对象实现视图、均匀选源角色再选后代节点，允许重复。每侧每组总64000个额外负例曝光；每个C节点与其H配对节点的曝光次数逐步完全相同。两组完整图前向与BN范围、训练预算相同。320个槽独立源对象均衡，但公共背景保持历史权重，不能称全体监督源均衡。',
 '损失输入是“公共监督索引+320个负例索引”，继续原损失归一化；正例数及分母在两组严格相同。没有另行增加困难负例权重。本轮替换预算尤其在trans侧仅约0.076%，若效果不明确，不能外推为任意监督强度都无效。','',
 '## 三种预先固定的验证集操作点','',
 'historical_fpr5：沿用历史可信验证负例95%分位阈值；val_recall80/90：仅用验证可信正例分数确定达到至少80%/90% pooled recall的阈值，再固定应用测试。后两者并不保证测试召回相同，也不等同于逐视图宏平均召回。须结合实际测试召回判断误报收益，不能把整体压低分数当区分能力提升。测试未用于选训练节点、预算、检查点或阈值。','',
 '## 汇总结果（三种子均值）','',
 '|划分|操作点|组|节点AP±种子SD|木马视图召回|正常区域节点FPR（等源）|配对集合正确排序|配对联合成功|',
 '|---|---|---|---:|---:|---:|---:|---:|']
 for a in agg:lines.append(f"|{a['split']}|{a['operation']}|{a['arm']}|{f(a['ap_mean'])}±{f(a['ap_sd'])}|{pct(a['recall_mean'])}|{pct(a['source_mean_node_fpr_mean'])}|{pct(a['pair_correct_order_mean'])}|{pct(a['pair_joint_success_mean'])}|")
 lines += ['', 'AP为历史协议木马视图逐视图AP的平均，非整个拼接图的pooled AP。正常主评价覆盖val/test各6源对象、12视图、130/142节点；这些对象不全在训练配对家族中。配对集合指标覆盖val/test各5源对象、10视图、94/105个正常节点，比较同源制造角色的后代集合，非新SAT等价证明，也非每个中间门逐一同角色。','',
 '## 测试逐种子结果（历史操作点）','',
 '|seed|H AP|C AP|C−H AP|H 区域FPR|C 区域FPR|H 木马召回|C 木马召回|H 联合成功|C 联合成功|',
 '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 diffs=[]
 for seed in [42,1,2]:
  aa={x['arm']:x for x in g if x['split']=='test' and x['operation']=='historical_fpr5' and int(x['seed'])==seed};bb={x['arm']:x for x in s if x['split']=='test' and x['operation']=='historical_fpr5' and x['domain']=='trans' and int(x['seed'])==seed};h=aa['H'];c=aa['C'];bh=bb['H'];bc=bb['C'];delta=float(c['ap'])-float(h['ap']);diffs.append(delta)
  lines.append(f"|{seed}|{f(h['ap'])}|{f(c['ap'])}|{delta:+.4f}|{pct(bh['source_mean_node_fpr'])}|{pct(bc['source_mean_node_fpr'])}|{pct(h['recall'])}|{pct(c['recall'])}|{pct(bh['pair_joint_success'])}|{pct(bc['pair_joint_success'])}|")
 lines += ['',f'配对AP差值均值{np.mean(diffs):+.4f}，种子间SD {np.std(diffs,ddof=1):.4f}；3个种子只是训练随机性重复，不是3套独立数据。','',
 '## 测试逐源对象（历史操作点，先跨视图再跨种子）','',
 '|源对象|H区域节点FPR|C区域节点FPR|C−H（百分点）|3种子中FPR下降次数|',
 '|---|---:|---:|---:|---:|']
 source_rows=[]
 for source in sorted({x['source'] for x in d if x['split']=='test'}):
  a=[x for x in d if x['split']=='test' and x['operation']=='historical_fpr5' and x['source']==source];h=np.mean([float(x['H_fpr']) for x in a]);c=np.mean([float(x['C_fpr']) for x in a]);n=sum(float(x['delta_fpr'])<0 for x in a);lines.append(f'|{source}|{pct(h)}|{pct(c)}|{100*(c-h):+.2f}|{n}/3|');source_rows.append(dict(source=source,H_fpr=h,C_fpr=c,delta=c-h,seeds_improved=n))
 with (O/'test_source_average.csv').open('w',encoding='utf-8-sig',newline='') as file:
  w=csv.DictWriter(file,fieldnames=list(source_rows[0]));w.writeheader();w.writerows(source_rows)
 lines += ['', '## 可靠性与限制','',
 '独立核查通过：同门型同视图匹配、已有可信负标签、两组相同正例/负例预算、逐节点一一对应曝光、原始图和标签文件哈希未变、六次200更新及有限预测。每5步保存恢复点，成功结果可复用；本轮无中断补跑，未启动SAT。队列串行占用GPU。',
 '首个任务启动期间仅修正异常日志文件名拼接，训练和评估逻辑没有改变；首版执行源快照与绑定哈希保存在runner_initial_snapshot.py及FAIRNESS_VERIFIED.json。',
 '源对象报告用于避免把节点/视图当独立样本，但同宿主不同对象仍相关；val/test各单宿主，当前测试已在此前分析中查看，结果属探索性。候选偏向可追溯实现，不代表所有映射不明、被消除区域或所有结构可达等价对照。配对集合最大风险受集合节点数量影响，不能解释成单门功能的无偏分数。测试结果不能用于下一轮反向选择训练对象。','',
 '## 证据入口','',
 '- manifest.json、train_pairs.csv、excluded.csv：冻结合同、匹配清单与排除原因。',
 '- FAIRNESS_VERIFIED.json：独立预算/门型/来源和曝光核查。',
 '- seed*/H、C：初始化绑定、配置、逐步历史、检查点、选模记录及四域预测。',
 '- global_metrics.csv、region_summary.csv、per_source_all.csv、role_pairs_per_source_all.csv、paired_source_deltas.csv：操作点、源对象与种子配对结果。',
 '- aggregate.csv、test_source_average.csv、ANALYSIS_COMPLETE.json：汇总与最终审计。','']
 report='\n'.join(lines);(O/'实验报告.md').write_text(report,encoding='utf-8');target=N/'正常对照等预算实验_改进双分支200次_20261104.md';target.write_text(report,encoding='utf-8')
 brief=f"\n\n## 正常对照等预算训练完成（2026-11-04）\n\n用户授权后完成H/C各seed42、1、2共6次200更新（1200步），ginvenv_gpu、dual_mix_post_cat、39v2，0 SAT。20个训练源对象，严格匹配orig116/trans294个C/H唯一节点，每侧每步320个等额槽位，公共正例及背景、图与初始化固定。按旧验证AP选模，另报验证召回80/90操作点。测试AP配对差C−H均值{np.mean(diffs):+.4f}，SD {np.std(diffs,ddof=1):.4f}。完整源级误报、排名、配对集合联合成功和召回见[实验报告]({target.name})及`_p0pilot/control_fair200_20261104/`。不能仅凭AP或降低分数声称贡献成立；本轮固定低预算，测试属探索性，三种子不替代独立宿主。\n"
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  with (N/name).open('a',encoding='utf-8') as file:file.write(brief)
 with (N/'正常对照贡献量化与公平实验方案_20261104.md').open('a',encoding='utf-8') as file:file.write(brief)
 registry=R/'10.15/99_共用资产/运行登记/运行登记表.csv'
 with registry.open('a',encoding='utf-8',newline='') as file:csv.writer(file).writerow([datetime.datetime.now().astimezone().isoformat(),'正常对照等预算H-C强双分支200次','prepare/verify/run/analyze_results/publish.py','ginvenv_gpu;bf16;no SAT','42/1/2','frozen old mask;39v2','samegraph commonbase +320 paired slots per domain','_p0pilot/control_fair200_20261104',f'6 runs;1200 updates;test AP delta {np.mean(diffs):+.4f}','完成','20 sources;orig116/trans294 exact pairs;exploratory test'])
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target),time=datetime.datetime.now().astimezone().isoformat(),test_paired_AP_delta=float(np.mean(diffs)),SAT=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print(target)
if __name__=='__main__':main()
