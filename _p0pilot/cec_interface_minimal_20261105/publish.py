"""Publish prepared interface and unexecuted single-factor protocol."""
from pathlib import Path
import csv,json,hashlib
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
 done=read(O/'COMPLETE.json');export=read(O/'EXPORT_COMPLETE.json');replay=read(O/'EXPORTED_WITNESS_REPLAY.json');assert done['training_updates']==0 and replay['pass_all']
 title='等价锥引脚角色与边界对齐_最小接口及单因素合同_20261105.md'
 report='''# 等价锥引脚角色与边界输入对齐：最小接口、反例验证及下一轮合同

日期：2026-11-05。工程根目录：`C:\\Users\\91344\\Desktop\\GraphSAINT\\GIN_train`。

## 本轮完成与边界

仅制作独立侧文件与接口原型，未修改模型公共代码、训练引擎、图、39v3特征、标签或旧SAT证据。0次训练更新、0次优化器步、0次模型前向、0次SAT/Yosys。没有运行队列。下一轮合同已设计，模型接入与加载预检尚未执行。

复用5238条既有可靠配对，导出10429个唯一锥的1158804条引脚关联；涉及32个已有视图、15个源对象/查询上下文。15组上下文的完整PI/物理Q布局跨视图完全一致，每个锥导出的叶与旧证明叶逐项一致。未扩大搜索、未新增配对、未根据测试正例选样；接口仅覆盖这32个视图，不能称全数据388视图已接入。

## 一、最小语义接口

使用独立`cone_pin_incidence.jsonl.gz`，不改现有cell-to-cell边。每个输入引脚保存一条关联：

`(src_kind, src_index, physicalQ_complement, dst_gate_index, dst_role)`。

|字段|最小定义|
|---|---|
|src_kind|内部组合门、边界变量、常量三类|
|src_index|局部门索引、上下文边界槽位，或常量0/1；索引用于寻址，不当作连续大小特征|
|physicalQ_complement|同一个物理Q使用同一槽位，QN为相位1；INV门输出虽名为QN，不再额外取反|
|dst_gate_index|所属组合门的局部索引|
|dst_role|AND/OR/XOR的交换对称输入统一为COMM；NOT单输入；MUX明确DATA0、DATA1、SELECT|

一脚一条，重复输入保留重数，不将多引脚并为一条无类型边。每门保留已有规范化操作类别，根指向明确输出。现有池的门型由AND/OR/XOR/NOT/MUX覆盖；未支持的门、多输出或不闭合边界应报错，不自动当作已覆盖。门型定义只描述电路连接语义，没有把真值表/证明结果当作模型输入。

边界变量定义为`(PI,端口名,位索引)`或`(Q,物理寄存器名,位索引)`，变量名只用于离线验证和对应查找。实际学习接口使用中性槽位/向量，不传宿主名、信号名、源对象ID、proof、木马标签或反例输出。`context_lookup`/`cone_id`/`graph_rows`仅为加载地址，明确排除出特征。

映射必须按**整个同源查询上下文**生成，并对所有相关视图、所有锥及四个端点共享；禁止每个锥独立排序后各自从0编号，也不能在P组交换后重新对齐错误端点。视图间布局不一致时停止，不借木马标签补对应。这里的Q是自由物理状态边界，不代表已证明时序可达或全电路时序等价。

## 二、两个独立开关与已有反例

P表示输入引脚角色；B表示边界变量身份：P0忽略组合引脚角色，P1保留；B0只保留PI/Q类型与极性，B1保留共同上下文中的变量身份。

|接口|NOT(a)与NOT(b)|对称MUX选择端/数据端交换|
|---|---|---|
|P0+B0|仍无法区分|仍无法区分|
|P1+B0|仍无法区分|仍无法区分|
|P0+B1|可保留差别|仍无法区分|
|P1+B1|可保留差别|可保留差别|

“可保留差别”指带边界身份/角色的结构签名不同，**不代表GIN已学会，也不代表该签名能证明不同分解结构的布尔等价**。旧反例仍分别有4/8与2/8输入组合输出不同。对称MUX三条来源支路相同，没有变量身份时，只加引脚类型仍可能在重命名下不可区分。

附加一致性检查通过：AND交换两个输入不制造新语义；跨视图共同重命名变量并运输对应映射后签名一致；Q与QN可区分；QN与NOT(Q)表达一致。用导出后的纯数值引脚表和边界槽位回放已有68块验证证书，272个根输出全部与原证据一致，不调用新SAT，也没有用反例输出构造学习特征。

这说明组合接口保留了这些已核查功能信息；没有证明模型将利用它，也没有证明任何固定维度压缩均无碰撞。

## 三、下一轮只检验“边界输入对齐”

### 问题与主对照

在仍然不向消息传递加入引脚角色的P0条件下，只改变边界变量编码在不同视图间的对应关系：

- **B_shared**：同一上下文的同一PI/物理Q，在所有实现视图中使用同一编码。
- **B_viewshuffle**：每个视图内部仍区分所有变量、保留别名复用及Q/QN极性，但在PI/Q类型内对编码作视图特定错位。一张锚视图保持不动，其余视图使用无固定点轮换；只有单变量的类型组保持原样并记录。

两组使用相同编码词表、每变量单位范数、变量数、类型、极性、常量处理、维度和参数量。未保证逐节点向量协方差完全相同；共享的变量重排增强有助于避免某个编码偶然合适。**不把B0“所有同类变量一个编码”作为主训练对照**，否则同时混入变量区分粒度与数值分布变化。

这种错位控制只改模型侧辅助编码，不改网表或已有CEC证书。其作用是检验正确跨实现对齐是否有价值，不是假装给错误映射发等价证书。B_viewshuffle在单个视图内也应能区分NOT(a)/NOT(b)，不同之处只在跨视图是否对应同一物理变量。

### 接入方式与共用参数

保持存盘39v3、原有有向图、归一化和原编码器不变。计划增加共同的20维边界描述侧输入：4个直接输入引脚计数（PI、Q、常量0、常量1，log1p）+16维带极性的单位变量编码之和，并除以sqrt(max(1,边界输入引脚数))。

用无偏置20→39线性残差适配器注入原编码器输入，780个新增参数；六个条件完全相同，适配器初始为0，原46620参数与投影头初始化一致。基础39列不改写；模型因此新增边界信息通道，不能宣称“输入没有任何变化”。这是两组共同的接口底座，其因果比较依赖新跑的共享/错位对照，不能拿原无适配器检查点直接替代。

直接边界描述只给这32个可核查视图中的组合单元；DFF行保持零侧输入，因为此处Q为自由边界，不展开D/时钟状态方程。加载时必须逐行核对冻结图名字与原网表，不允许缺失映射静默补零。其他图区域的处理在两组一致，并明确不作为已覆盖边界。

20维求和是压缩摘要，不保证无损，也没有编码MUX端口角色；它只用于下一轮隔离边界对齐效应。完整引脚表仍作为权威接口。若压缩在其他反例上丢失信息，应在实施预检时报出，不用“覆盖成功”掩盖。

### 固定协议

|项目|合同|
|---|---|
|条件|B_shared/B_viewshuffle各Z、R、P，共6组|
|种子|仅seed42；不追加seed1/2|
|预算|每组50次功能预训练，共300次更新；本轮合同不含200次检测微调|
|模型|原改进双分支2+2+post1、hidden64、split29/10；共同残差适配器|
|预训练读出|原root64+mean64，128→64→32投影头|
|损失|原MSE+已证不同函数间隔+0.1方差；Z保留公共不同函数项|
|dropout/BN|dropout固定0.2，BN保持原训练行为|
|优化器|原Adam lr0.0002、weight_decay0.001、clip1|
|采样|原main/seed42冻结表，382唯一配对/500名额，10源各50名额；不扩大池|
|编码重排|seed42/更新编号确定的共同类型内槽位重排；所有相关视图与Z/R/P一致；错位组额外施加视图轮换；不用信号名或上下文字符串生成向量内容|
|选模|固定第50次；不按AP或测试指标选择|
|评估|复用68块；不新跑SAT，不用测试；报告小源限制|

16维编码只表示变量身份，是符号标识通道，**不表示变量在任何输入模式下的0/1值，也不是SAT数值或木马标签**。训练时跨视图共享的槽位重排应在每次更新统一生成，不能每条配对独立生成；验证使用预先固定映射及另一个预定共同重排作为稳健性诊断，不从结果挑映射。

## 四、实施预检与结果解释

下一轮若获执行指令，先补充模型接入与无优化器预检，再执行上述预训练预算；当前没有训练入口或队列。

实施预检必须确认：全部行映射合法；同一物理输入同码、QN极性一致；错位不塌缩变量；两组同词表与共同初始化；零适配器时原编码器输出一致；之后梯度能到适配器与编码器；未向特征传入证明结论/标签/真值表。当前仅完成数据/结构原型验证，尚未做模型梯度检查。

主要指标使用下游相关的root64，比较真实/错误均跨同一实现方向的同anchor排序与AUC，按源、配方、锥大小报告，同时给源内等权和合并口径。辅助报告concat128、投影32维、同视图函数区分、有效秩和第二个预定共同重排下的表现。

定义D_R=指标(shared,R)−指标(viewshuffle,R)，并同时计算D_P、D_Z。只有R相对于P/Z出现额外改善，才支持“正确对齐帮助了真实等价监督”；三组共同提高只能说明输入接口或一般正则化变化。不能仅凭投影变近或某个小源AUC很高作成功判断，单seed不作统计显著性宣称。

若root64仍无增益，不能推断完整P1+B1接口无效，因为本轮刻意保持P0且摘要有压缩。若只有头空间改善，不能认定下游已受益。之后才决定是否单独增加引脚角色或研究其他表示，不同时加微调保持项。

若预训练出现可用信号，检测迁移另立合同：需明确20维通道在检测中怎样保留、是否能覆盖原始侧及测试视图。不能无说明丢弃适配器，又宣称功能信息已传入检测；本次合同不评估检测AP。

## 五、证据入口

`_p0pilot/cec_interface_minimal_20261105/`中：

- `SCHEMA.json`、`cone_pin_incidence.jsonl.gz`、`boundary_maps_audit_only.json`：最小语义接口和离线映射。
- `interface_coverage.csv`、`EXPORT_COMPLETE.json`：10429锥、15上下文、32视图的覆盖和闭合核查。
- `fixture_matrix.csv`、`FIXTURE_CHECKS.json`：P/B拆分、合法重命名/交换、Q/QN验证。
- `EXPORTED_WITNESS_REPLAY.json`：68块272根输出复现。
- `BOUNDARY_ALIGNMENT_CONTROLS.json`：类型内错位不塌缩、词表保持和跨视图对照检查。
- `NEXT_SINGLE_FACTOR_CONTRACT.json`：下一轮机器可读合同，状态DESIGNED_NOT_EXECUTED；仍需实现和预检。
- `COMPLETE.json`：0训练/0前向/0SAT及读取输入哈希；`prepare.py`、`verify_export.py`为独立原型，未修改旧模型脚本。
'''
 (D/title).write_text(report,encoding='utf-8')
 note='''\n\n### 2026-11-05 引脚角色与边界输入对齐最小接口及单因素合同（未训练）

复用5238配对导出10429唯一锥/1158804条输入引脚关联，32视图、15源/查询上下文；完整PI/物理Q布局跨视图一致，导出叶与旧证明逐项匹配。一脚一关联，保留MUX A/B/S、交换对称输入及Q/QN极性；名字只用于离线映射，不作特征。已有反例显示B1单独能区分NOT(a)/NOT(b)，原对称MUX交换需P1+B1，P1单独不足。用数值接口回放68块既有证书、272根输出全部通过，仅证明信息保留，不是模型性能。下一轮设计为P0固定、B_shared与B_viewshuffle各Z/R/P：同变量区分粒度/词表/参数，仅改变跨视图对应；共同20→39零初始化残差适配器，seed42、每组50预训练共300更新，无检测微调/微调保持项/新SAT。合同仍需模型接入与加载梯度预检，未建训练队列；不能直接复用无适配器旧组充当新基线。详见[最小接口与合同](等价锥引脚角色与边界对齐_最小接口及单因素合同_20261105.md)。本轮0训练/0模型前向/0SAT/Yosys，旧图、特征、标签、证明与模型未变。
'''
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  p=D/name
  if '### 2026-11-05 引脚角色与边界输入对齐最小接口及单因素合同' not in p.read_text(encoding='utf-8-sig'):
   with p.open('a',encoding='utf-8') as f:f.write(note)
 handoff=D/'交接_等价锥现状_20261105.md';s=handoff.read_text(encoding='utf-8')
 if '## 11. 最小接口与下一轮合同' not in s:
  with handoff.open('a',encoding='utf-8') as f:f.write('\n\n## 11. 最小接口与下一轮合同（2026-11-05最新）\n\n已完成独立P/B接口与原反例验证，详细方案见《'+title[:-3]+'》。下一轮仅设计B_shared/B_viewshuffle×Z/R/P，固定P0、seed42，每组50预训练，无微调。此处更新第8节的候选优先级：先检验边界对齐本身，再另行考虑引脚角色。尚未实现模型接入、未训练、未建队列。\n')
 reg=R/'10.15/99_共用资产/运行登记/运行登记表.csv';key='等价锥最小引脚边界接口与单因素合同'
 if key not in reg.read_text(encoding='utf-8-sig'):
  with reg.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow(['2026-11-05',key,'cec_interface_minimal prepare/verify_export/publish','CPU;forward0;optimizer0;SAT0','seed42 planned only','existing5238pairs/32views/15contexts','39v3 unchanged;sidecar prototype','_p0pilot/cec_interface_minimal_20261105','10429closed cones;68blocks/272roots pass;P/B fixtures','接口验证完成；训练合同未执行','adapter/model integration and gradient preflight pending'])
 assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in done['input_sha256'].items())
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str((D/title).relative_to(R)),contract_sha=hashlib.sha256((O/'NEXT_SINGLE_FACTOR_CONTRACT.json').read_bytes()).hexdigest(),new_training=0,new_SAT=0,original_inputs_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
 print('PUBLISHED',D/title)
if __name__=='__main__':main()
