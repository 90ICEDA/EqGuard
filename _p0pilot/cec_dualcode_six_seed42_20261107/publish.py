from pathlib import Path
import csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def read(n):return json.loads((O/n).read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read('VERIFIED.json')['passed'];mm=rows('evaluation_metrics.csv');ss=rows('encoding_stability.csv');arms=['INIT','Z0','Z1','R0','R1','P0','P1']
def metric(group,arm,key='family_macro_win',lo=9000,hi=9011):return float(np.mean([float(r[key]) for r in mm if r['group']==group and r['arm']==arm and lo<=int(r['tag'])<=hi]))
def stable(group,arm,key):return float(np.mean([float(r[key]) for r in ss if r['group']==group and r['arm']==arm]))
name='双编码一致性六组探索训练_seed42_32步_20261107.md'
text='''# 双编码候选排序一致性六组探索训练

2026-11-07。结论：本轮未验证一致性项带来稳定的真实功能排序或MUX收益。R1的JS略降，但主编码排序下降；新增编码的平均排序提升极小。去掉候选距离尺度变化后，JS下降基本消失，不能把损失下降当成功能增益。不进入检测微调。

## 协议与完成情况

ginvenv_gpu/CUDA，seed42，Z0/Z1/R0/R1/P0/P1各32步，共192次实际Adam更新，384次训练前向。共同旧INITIAL_STATE、47,360参数原模型及原7个三函数单元/21函数类/4制造源/2家族不变；25维自由Q锥输入，完整有向锥、引脚角色及相位，无dropout、投影头或检测头。Adam lr0.0002、weight_decay0.001、clip1、FP32无AMP/TF32，固定末步32。

每批六组全部消费相同双编码t和10000+t，基础Z/R/P损失取两编码均值；后缀1增加JS，后缀0系数0，所有组均计算JS。λ固定10.2311796013，仅由上轮训练初始化梯度标定，没有用验证重新调节。

每组预算64逻辑单元名额/384查询身份；含编码输入128单元/768查询/2304候选距离/768公共负项计算，加384个跨编码JS查询。逻辑函数曝光上限16，编码输入次数上限32。六组每批特征哈希与原加载预检一致、梯度参数使用一致，无漏步或重复更新；样本按原计划重复曝光不算新增独立证据。MUX三角色矩阵各实际更新19步，其余11参数张量32步，六组一致。

32步训练与420次冻结评价前向共约109.05秒（后处理另计），训练峰值已分配显存约122.27 MiB。0检测微调、0新增SAT、0测试读取，旧结果和Git历史保留。

## 功能排序结果

73个H3验证单元（37个双函数、36个三函数，2制造源、1留出宿主），指标为root64真实候选比错误候选更近的逐对胜率，按单元再家族平均；不是木马检测AP。以下新增编码9006—9011在训练前冻结，不挑最佳编码/检查点；它们仍不是新的独立电路或种子。

|评价编码|INIT|Z0|Z1|R0|R1|P0|P1|
|---|---:|---:|---:|---:|---:|---:|---:|
'''
for label,lo,hi in [('9000主编码',9000,9000),('新增6编码均值',9006,9011),('全部12编码均值',9000,9011)]:text+=f'|{label}|'+ '|'.join(f'{100*metric("val_H3_primary",a,lo=lo,hi=hi):.2f}%' for a in arms)+'|\n'
text+='''
主编码R1−R0=−0.57、R1−P1=−1.60、R1−Z1=−0.34个百分点；新增六编码R1−R0仅+0.17、R1−P1约+0.32、R1−Z1约+0.04个百分点。全部十二编码R1−R0仅+0.08个百分点，不能据此认定稳定泛化收益。原单编码三组不是本轮公平基线，只使用本轮R0等预算对照。

## MUX与来源

|子集（12编码均值）|R0|R1|P1|Z1|
|---|---:|---:|---:|---:|
'''
for group,label in [('train_MUX','训练MUX（3单元）'),('val_MUX','留出MUX（23单元）'),('val_source/s38417t100__ctlmatchb_d1_s42','留出ctlmatchb（34单元）'),('val_source/s38417t100__injalpha_d1_s42','留出injalpha（39单元）')]:text+=f'|{label}|'+ '|'.join(f'{100*metric(group,a):.2f}%' for a in ['R0','R1','P1','Z1'])+'|\n'
text+='''
主编码训练MUX的R0/R1=50.00/44.44%，留出MUX=46.01/44.57%；新增六编码留出MUX均值47.10/47.04%，也没有改善。训练MUX十二编码均值两者同为55.09%，仍未形成稳健的组合功能学习。R1在困难源ctlmatchb相对R0小幅变化，在易源injalpha略退化，不能仅看全体均值。

MUX与来源/abc-aig流程仍混杂；这些结果不构成“模型一定不能学MUX”或“单纯宿主偏差”的因果结论。它们表明当前训练支持、模型和预算下，加入此一致性项没有解决已知困难。

## 是否只是分布变平

JS和翻转率按6对互不重叠编码（9000/9001至9010/9011）取均值；候选熵、距离离散度按12编码取均值。

|留出73单元诊断|R0|R1|
|---|---:|---:|
'''
for label,key,style in [('原始跨编码JS','weighted_JS','.8f'),('逐对排序翻转率','pairwise_rank_flip_rate','.6f')]:text+=f'|{label}|{stable("val_H3_primary","R0",key):{style}}|{stable("val_H3_primary","R1",key):{style}}|\n'
for label,key in [('归一化候选熵（均匀=1）','normalized_candidate_entropy'),('候选距离标准差','candidate_distance_std'),('标准化真假距离余量','normalized_pair_margin')]:text+=f'|{label}|{metric("val_H3_primary","R0",key):.6f}|{metric("val_H3_primary","R1",key):.6f}|\n'
text+='''
JS约下降4%，但逐对翻转率均为27.949%，未见稳定排序改善。候选距离标准差略降约1.12%，熵略升，提示轻度变平；并未发生全体均匀或零距离坍缩。主编码验证有效秩R0/R1=16.48/16.29，根表示平均标准差0.855/0.850。

进一步做事后尺度复核：逐查询将R1距离中心化，再把标准差匹配为R0在同编码的标准差（保持R1候选顺序和相对形状）。R1的JS从0.00104109回到0.00108283，几乎等于R0的0.00108451。两侧各自标准化为单位尺度后，JS仅从0.097624降至0.096243，形状稳定性变化很小。该控制是冻结输出的尺度诊断，不是新的训练或可部署后处理，也不是训练轨迹的因果贡献百分比。

因此，不能排除轻度变平对原始JS下降的贡献；相反，其下降大部分在匹配尺度后消失。虽然不是整体表示坍缩，但原始JS减少不足以证明学到了可迁移函数。MUX的JS也略降，十二编码胜率仍更差，进一步说明不能用一致性损失代替真实排序评价。

## 核验、限制与下一步

独立CPU复核2016组胜率/AUC、168组熵/距离离散度/标准化余量、84组跨编码JS/翻转率；检查共同初始化、六个不同末步状态、实际Adam步数、192次连续更新、损失公式、同输入预算和旧文件哈希，均通过。尺度复核的原始JS与独立验证结果一致；所有日志和检查点保留。

本轮是单种子、小支持、多轮诊断后的探索，不能把12套编码当12份独立实验；各子集及双/三候选指标保留在evaluation_metrics.csv，旧/新PO单列，不能替换主指标。当前未验证JS有效，不继续直接加大λ、补种子或接检测微调。

下一步优先复用现有证明和冻结检查点，检查训练3个MUX单元中具体的真假函数、原生/展开对应和错误角色：区分训练支持不足、深层组合信息不足与目标本身不够针对功能。若继续研究一致性，须单独制定去尺度的候选相对关系目标预检，证明没有依靠变平降损失，再决定是否值得训练；不能同时改模型、样本池与损失。暂不扩大SAT。

证据：`_p0pilot/cec_dualcode_six_seed42_20261107/`，EXECUTION_CONTRACT.json、TRAINING_COMPLETE.json、COMPLETE.json、VERIFIED.json、PRIMARY_RESULT.json、evaluation_metrics.csv、encoding_stability.csv、comparisons.csv、SCALE_NEUTRAL_DIAGNOSTICS.csv、SCALE_NEUTRAL_SUMMARY.json、representation_geometry.csv、六组resume.pt/history.json及12编码INIT/六组冻结表示。
'''
(D/name).write_text(text,encoding='utf-8')
entry='''

### 2026-11-07 双编码一致性六组各32步探索（完成，未验证有效）

ginvenv_gpu按冻结合同完成seed42 Z0/Z1/R0/R1/P0/P1各32步、共192更新；同旧INITIAL_STATE/47,360参数/7单元/双编码输入/预算，λ10.2311796013不变，0检测微调/0新增SAT/0测试读取，旧资产保留。每组64逻辑单元/384查询身份，含编码128单元/768查询/2304候选距离/768公共负项，所有组消费同样计算。

主编码9000的INIT/Z0/Z1/R0/R1/P0/P1胜率=74.43/75.00/73.97/74.20/73.63/75.57/75.23%；R1较R0低0.57个百分点。新增六编码R1/R0/P1/Z1=73.21/73.04/72.89/73.17%，R1仅微小领先；十二编码R1较R0仅+0.08个百分点。留出MUX十二编码R0/R1=47.31/46.95%，训练MUX均55.09%，未验证组合功能改善。困难源ctlmatchb约47%、易源injalpha约96%，不能靠全体均值宣称收益。

R1跨编码JS约降4%，但留出排序翻转率R0/R1均27.949%；距离标准差降约1.12%，熵略升，无整体坍缩。将R1候选距离标准差逐查询匹配R0后，JS由0.001041回升0.001083，几乎等于R0的0.001085；不能排除变平贡献，原始损失下降不能当功能收益。独立复核2016组指标、168组分布及84组稳定性检查通过，参数实际步数/预算/旧文件哈希一致。

暂不检测微调或加大JS权重。建议下一步复用证明和检查点，审计3个训练MUX单元的真假函数、原生/展开角色与组合信息；若继续一致性需单独预检去尺度相对目标，不同时换模型/池/损失。

详见[六组训练与尺度诊断](双编码一致性六组探索训练_seed42_32步_20261107.md)，证据`_p0pilot/cec_dualcode_six_seed42_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();old=b.decode('utf-8-sig');assert '双编码一致性六组各32步探索（完成' not in old
 (O/(n+'.before')).write_bytes(b);p.write_text(old+entry,encoding='utf-8')
v=read('VERIFIED.json');v.update(training_forwards=384,scale_neutral_diagnostics_retained=True);(O/'VERIFIED.json').write_text(json.dumps(v,indent=2),encoding='utf-8')
manifest={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.suffix in ['.py','.json','.csv','.npz','.pt'] and '__pycache__' not in p.parts and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,actual_updates=192,SAT=0,finetune=0),ensure_ascii=False,indent=2),encoding='utf-8')
print('Report and both summaries updated; all previous results retained.')
