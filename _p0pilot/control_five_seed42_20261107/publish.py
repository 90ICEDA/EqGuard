from pathlib import Path
import csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明';ARMS=['G0','GB','GM','GBM','GAll']
def read(n):return json.loads((O/n).read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read('VERIFIED.json')['passed'];m=rows('source_macro_metrics.csv');r=rows('role_source_macro.csv');whole=rows('whole_normal_macro.csv');source=rows('per_source_scope_PO.csv');role_source=rows('role_per_source.csv');rank=rows('region_rank_per_source.csv')
def metric(arm,key,scope,col,op='val_recall80'):
 row=next(x for x in m if x['arm']==arm and x['key']==key and x['scope']==scope and x['PO_bin']=='all' and x['operation']==op and (x['kind']=='trojan' if scope in ['trusted_all','trojan_positive'] else True));return float(row[col]) if row[col] else None
def role(arm,key,cl,op='val_recall80'):
 row=next((x for x in r if x['arm']==arm and x['key']==key and x['operation']==op and x['role_class']==cl),None);return float(row['recall']) if row else None
def alarm(arm,key,op='val_recall80'):return float(next(x['alarm'] for x in whole if x['arm']==arm and x['key']==key and x['operation']==op))
def pct(x):return 'NA' if x is None else f'{100*x:.2f}%'
summary=[]
for key in ['orig_val','orig_test','trans_val','trans_test']:
 for arm in ARMS:
  for op in ['historical_fpr5','val_recall80','val_recall90']:
   summary.append(dict(arm=arm,key=key,operation=op,node_AP_source_macro=metric(arm,key,'trusted_all','AP',op),normal_added_FPR=metric(arm,key,'normal_primary_added','FPR',op),normal_all_FPR=metric(arm,key,'normal_all','FPR',op),whole_normal_view_alarm=alarm(arm,key,op),all_positive_recall=metric(arm,key,'trojan_positive','recall',op),traceable_trigger_recall=role(arm,key,'trigger',op),traceable_payload_recall=role(arm,key,'payload',op),traceable_payload_select_recall=role(arm,key,'payload_select',op)))
with (O/'KEY_RESULTS.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
name='正常对照五组seed42_200次公平实验_20261107.md'
text='''# 正常对照五组公平实验：seed42，各200次

2026-11-07。**已完成新版加载器接入、2000条监督记录核验及五组1000次实际更新。**本轮支持：相似正常区域M的监督在当前共同支持集上降低局部误报，并提高变换侧节点AP；普通背景B及剩余U的额外收益较小。但木马角色召回有代价，原始侧AP下降，整图报警未改善，不能宣称正常对照整体问题已解决。

## 1. 配置和公平性

- ginvenv_gpu、39维v3、改进双分支dual_mix_post_cat，split29/hidden64/2+2+post1，46,620参数；五组严格加载同一旧seed42初始化，初始文件SHA一致。
- Adam lr0.0002、weight_decay0.001、clip1、BF16；原始侧反向后变换侧反向，再统一更新一次，共每组200步。原ASL+1.4软漏检平方损失、图及标签不改，不加SAT、等价约束、正例保护或角色权重。
- 显式调用FiveGroupLoader.step取得监督索引，训练图不提供默认mask；实际2000条索引哈希与已冻结预检逐条一致。正例、负例条目、独立数和重复次数分布、源曝光上限沿用严格main_fanout05合同。
- 所有组仍看相同完整图，改变的是正常对照**负标签监督来源**，不是正常图是否进入消息传递。G0没有正常对照标签；替换未启用的槽位由配对H补足。

|域|正例/步|公共负例/步|B/M/U槽位|负例合计/步|
|---|---:|---:|---|---:|
|原始|136|8192|48/48/8|8296|
|变换|829|8192|48/48/48|8336|

同一步节点不重复，200步负节点曝光≤128；各组原始/变换独立负节点总数分别28,896/96,031。B/M同为48条/域/步，但B用9600个独立节点，M仅原始93/变换173，不能将条目等量解释成独立样本多样性也相等。

|组|B槽位|M槽位|U槽位|选中更新|旧规则验证AP|
|---|---|---|---|---:|
'''
modes={'G0':('H','H','H'),'GB':('B','H','H'),'GM':('H','M','H'),'GBM':('B','M','H'),'GAll':('B','M','U')}
for arm in ARMS:
 e=read(arm+'/EVALUATED.json');text+=f'|{arm}|'+ '|'.join(modes[arm])+f'|{e["selected"]["epoch"]}|{e["selected"]["score"]:.4f}|\n'
text+='''
每5步沿用旧可信__inj变换验证视图平均AP选模，测试不选模、不调阈值。训练与各组最终预测耗时约467秒（约7.8分钟，加载预检/后处理另计），峰值已分配显存约4.79 GiB。

首次执行在首步更新前CUDA归约出现内存分配错误；保留原日志，预热小型归约后重启，随后五组均完成。预热没有模型/优化器更新，失败前无已提交步骤，因此没有重复成功更新；未改模型、预算或启用有BN重算风险的梯度检查点。具体驱动/编译内存原因尚未完全定位，不能称已根治硬件问题。

## 2. 主要结果：变换侧

下表使用冻结的“变换验证可信正例0.2分位”阈值规则，记作val_recall80。它校准的是节点池，**不是保证每源或测试召回精确80%**，因此同时列实际源宏召回。每视图先算，再源内等视图平均，最后等源平均；AP为可信木马视图节点AP的源宏平均，整图报警覆盖正常视图全部物理节点。整图报警只评估分数，不扩大原不可信节点的训练标签。

新增正常区域验证/测试各6个源、130/142个节点；木马正例覆盖各5个源。角色召回仅限既有可追溯制造角色，覆盖见后文，不假称全部正例都有角色。

'''
for key,label in [('trans_val','变换验证'),('trans_test','变换测试（探索性）')]:
 text+=f'### {label}\n\n|组|节点AP|新增正常区域FPR|正常全视图可信节点FPR|全部木马正例召回|触发召回*|载荷召回*|整图报警|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
 for arm in ARMS:
  values=[pct(metric(arm,key,'normal_primary_added','FPR')),pct(metric(arm,key,'normal_all','FPR')),pct(metric(arm,key,'trojan_positive','recall')),pct(role(arm,key,'trigger')),pct(role(arm,key,'payload')),pct(alarm(arm,key))];text+=f'|{arm}|{metric(arm,key,"trusted_all","AP"):.4f}|'+ '|'.join(values)+'|\n'
 text+='\n'
text+='''
*角色是制造来源角色，不等同于新SAT证明其当前实现的实际功能必要性。

GM相对G0：变换验证新增区域FPR下降22.66个百分点，测试下降13.65个百分点；测试AP提高约0.0236。GB的测试AP只提高约0.0012，新增区域误报反而略升；GBM相对GM有较小AP/正常背景FPR增量，新增区域FPR不变。GAll相对GBM未显示额外优势；U多数为追踪不完整的已有可信负标，不能将结果归为某种明确正常功能有用/无用。

代价不能忽略：GM测试源宏全部正例召回81.50%→81.39%，追溯触发61.67%→60.00%、载荷88.92%→86.92%；验证触发不变，载荷略升。不能只报告AP和正常误报改善而省略这些损失。

## 3. 高召回操作点的代价

变换测试，使用冻结的验证正例0.1分位（val_recall90），仍不保证测试宏召回90%。

|组|新增区域FPR|实际全部正例召回|触发召回*|载荷召回*|
|---|---:|---:|---:|---:|
'''
for arm in ARMS:text+=f'|{arm}|{pct(metric(arm,"trans_test","normal_primary_added","FPR","val_recall90"))}|{pct(metric(arm,"trans_test","trojan_positive","recall","val_recall90"))}|{pct(role(arm,"trans_test","trigger","val_recall90"))}|{pct(role(arm,"trans_test","payload","val_recall90"))}|\n'
text+='''
GM在更高召回操作点依然降低误报，但全部正例及触发召回损失扩大。载荷选择角色在五组间未见改善，测试val_recall80下均约16.67%、val_recall90下均约26.67%，仅对应有追溯支持的子集。

## 4. 原始侧不能省略

与变换侧复用同一全局校准阈值算法与数值，不按原始侧重新挑阈值。

|划分|组|节点AP|新增区域FPR|全部正例召回|触发召回*|载荷召回*|
|---|---|---:|---:|---:|---:|---:|
'''
for key,label in [('orig_val','验证'),('orig_test','测试')]:
 for arm in ARMS:text+=f'|{label}|{arm}|{metric(arm,key,"trusted_all","AP"):.4f}|{pct(metric(arm,key,"normal_primary_added","FPR"))}|{pct(metric(arm,key,"trojan_positive","recall"))}|{pct(role(arm,key,"trigger"))}|{pct(role(arm,key,"payload"))}|\n'
text+='''
原始测试GM相对G0，区域FPR58.87%→42.62%，但AP0.3458→0.3171、全部正例召回76.82%→72.82%、追溯触发源宏45%→25%。该20个百分点角色损失集中于injalpha，源数和角色节点数很小，仍需明确报告。当前结果不能表述为“两侧都无代价改善”。

## 5. 独立源：哪些区域改善、哪些角色下降

以下比较G0→GM，val_recall80，所有源保留，不按预测剔除源。完整五组/所有操作点及PO档见per_source_scope_PO.csv、role_per_source.csv和paired_source_deltas.csv。

|变换划分|正常源|G0区域FPR|GM区域FPR|差值（百分点）|
|---|---|---:|---:|---:|
'''
for key,label in [('trans_val','验证'),('trans_test','测试')]:
 aa={x['source']:float(x['FPR']) for x in source if x['arm']=='G0' and x['key']==key and x['scope']=='normal_primary_added' and x['PO_bin']=='all' and x['operation']=='val_recall80'};bb={x['source']:float(x['FPR']) for x in source if x['arm']=='GM' and x['key']==key and x['scope']=='normal_primary_added' and x['PO_bin']=='all' and x['operation']=='val_recall80'}
 for s,a in sorted(aa.items()):text+=f'|{label}|{s}|{pct(a)}|{pct(bb[s])}|{100*(bb[s]-a):+.2f}|\n'
text+='''
验证6/6和测试6/6个可评价新增区域源FPR均下降，说明不是仅由一个正常源拉低均值；同宿主内的6个源及其变换并非6个独立宿主重复。

|木马划分|源|角色|G0召回|GM召回|
|---|---|---|---:|---:|
'''
for key,label in [('trans_test','变换测试'),('orig_test','原始测试')]:
 aa={(x['source'],x['role_class']):float(x['recall']) for x in role_source if x['arm']=='G0' and x['key']==key and x['operation']=='val_recall80' and x['role_class'] in ['trigger','payload']};bb={(x['source'],x['role_class']):float(x['recall']) for x in role_source if x['arm']=='GM' and x['key']==key and x['operation']=='val_recall80' and x['role_class'] in ['trigger','payload']}
 for (s,cl),a in sorted(aa.items()):text+=f'|{label}|{s}|{cl}|{pct(a)}|{pct(bb[s,cl])}|\n'
text+='''
变换测试epsilon触发召回下降，delta触发略升但载荷下降；原始测试alpha触发下降。不是所有木马角色同步改善，也没有通过正例保护掩盖该冲突。

## 6. 误报下降是不是只因阈值变化

保留了统一校准规则之外的固定G0阈值诊断。变换验证在G0阈值下，GM新增区域FPR仍由68.44%降至50.03%；测试69.71%→57.07%，说明降分不是仅靠GM阈值更高。测试区域平均分数约0.703→0.616，最佳风险名次占比约0.77%→1.84%（占比增大表示排名后移），也支持这些正常区域被降分。

这是离线辅助诊断，不替换冻结主操作点；相同阈值不自动保证不同模型具有相同召回。整张正常电路“任意物理节点过阈值”的报警在所有五组仍为100%，意味着局部改善没有转化为电路级报警消除。节点阈值校准不等于整图假警率校准，不在本轮偷偷改报警规则。

## 7. 覆盖与结论边界

|划分|可信物理正例|角色已分类|未分类|混合血缘|
|---|---:|---:|---:|---:|
'''
for x in rows('role_coverage.csv'):text+=f'|{x["key"]}|{x["positive_nodes"]}|{x["classified_nodes"]}|{x["unclassified_nodes"]}|{x["mixed_nodes"]}|\n'
text+='''
全部正例召回覆盖完整可信正例，角色召回只覆盖上述可追溯子集；变换验证86/215、测试106/243可分类，不能把角色子集冒充全部触发/载荷。未分类正例独立报告，没有删除或重新标注。制造角色后代集合的联合成功另存manufacturing_joint_per_source.csv，不称SAT等价配对。

正常新增验证区域是PO不可达的死线制造；测试仅少量同源可达后代。PO分层保留固定−1/0/1—2/3—5/≥6，新增区域标准化FPR因缺少训练正权重档而报NA，未删档重归一化。普通正常背景大量PO可达，不能与新增区域混为一谈。当前收益仅说明这批共同支持集上正常负标签监督有作用，不证明独立于位置、血缘或宿主的功能区分能力。

这是seed42单种子、单一验证宿主及单一测试宿主；测试此前已被审视，本轮测试结论为探索性，不作独立显著性声明。普通B与相似M虽然同条目剂量，独立节点多样性/剩余PO差异仍不同，不据效应大小宣称某类语义普遍优越。

## 8. 核验与建议

独立复核2000实际监督步骤、1000次连续更新、所有活跃参数Adam步数200（未使用fn_head保持0）、BN计数两域每步各一次、每5步选模与验证阈值；复算23,850个视图比例、2,775组AP、45,345个源聚合、4,185个整图报警及5,475个角色视图召回，均通过，旧绑定文件哈希不变。

下一步优先复用预测分析原始alpha触发、变换epsilon触发和delta载荷的降分原因，并按独立源检查误报/召回曲线；先不引入正例保护或改变权重。若机制审查仍支持保留该方案，再补种子1/2确认M/GBM的收益和代价是否稳定。当前不追加SAT或等价约束，也不把GAll默认设为最优。

证据目录：`_p0pilot/control_five_seed42_20261107/`。EXECUTION_CONTRACT.json、LOADER_INTEGRATION_VERIFIED.json、TRAINING_COMPLETE.json、VERIFIED.json、KEY_RESULTS.csv、source_macro_metrics.csv、per_source_scope_PO.csv、paired_source_deltas.csv、whole_normal_sources.csv、role_per_source.csv、role_coverage.csv、PO_standardized.csv；五组best/resume检查点、历史、六划分预测和全部失败/恢复日志均保留。
'''
(D/name).write_text(text,encoding='utf-8')
entry='''

### 2026-11-07 新加载器五组seed42/200次公平实验（完成）

ginvenv_gpu显式接入FiveGroupLoader，main_fanout05的2000监督记录与冻结预检哈希一致。G0/GB/GM/GBM/GAll各200步共1000更新，同39v3、改进双分支46620参数、旧seed42初始化、ASL+软漏检损失、BF16、正负预算与曝光；0新增SAT/0等价约束/0正例保护，旧结果保留。首步CUDA归约分配失败未提交更新，预热后从共同初始化恢复，五组全部成功，失败日志保留。

变换侧val_recall80操作点（源宏，阈值只由验证校准）：测试G0/GB/GM/GBM/GAll节点AP=0.2338/0.2350/0.2574/0.2585/0.2581，新增区域FPR=69.71/70.99/56.06/56.06/56.06%；验证AP=0.2445/0.2445/0.2577/0.2605/0.2577，区域FPR=68.44/67.94/45.78/45.78/45.78%。验证6/6、测试6/6正常区域源的GM误报均下降；固定G0阈值下测试也69.71→57.07%，不是仅阈值改变。B单独收益小，U未见额外优势，不能据此普遍否定其语义。

代价：变换测试GM全部正例召回81.50→81.39%，追溯触发61.67→60%、载荷88.92→86.92%；90%校准操作点损失更明显。原始测试GM的AP0.3458→0.3171、正例召回76.82→72.82%、追溯触发源宏45→25%（集中alpha），不能宣称两侧无代价改善。全部组整张正常图任意节点报警仍100%，局部FPR降低未解决图级报警。

角色分类覆盖原始验证35/40、测试40/45；变换验证86/215、测试106/243，其余正例未分类但仍计入全部召回。新增区域验证PO可达档缺支持，标准化FPR按冻结规则NA；不提升可信标签。独立复核2000监督步骤、选模/阈值、23850视图比例、2775AP、45345源聚合、4185整图报警、5475角色召回通过。本轮仅seed42、单留出宿主，测试探索性。建议先复用预测核查alpha/epsilon触发及delta载荷降分，再考虑补种子，暂不加保护/调权/SAT。

详见[五组公平实验结果](正常对照五组seed42_200次公平实验_20261107.md)，证据`_p0pilot/control_five_seed42_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();assert '新加载器五组seed42/200次公平实验（完成）' not in b.decode('utf-8-sig');(O/(n+'.before')).write_bytes(b);p.write_bytes(b+entry.replace('\n','\r\n').encode('utf-8'))
manifest={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.suffix in ['.py','.json','.csv','.npy','.pt'] and '__pycache__' not in p.parts and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,updates=1000,SAT=0,EQ=0),ensure_ascii=False,indent=2),encoding='utf-8');print('Five-group report and both summaries updated.')
if __name__=='__main__':pass
