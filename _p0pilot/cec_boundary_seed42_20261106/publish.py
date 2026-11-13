"""Publish only independently verified boundary-alignment experiment results."""
from pathlib import Path
import json,csv,collections,datetime
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 assert read(O/'VERIFIED.json')['passed']
 ss=rows(O/'evaluation_summary.csv');cc=rows(O/'alignment_contrasts.csv');mapping=rows(O/'row_mapping_audit.csv')
 get=lambda alignment,arm,tag=9000,space='root64':next(r for r in ss if r['alignment']==alignment and r['arm']==arm and int(r['remap'])==tag and r['space']==space)
 lines=[]
 for arm in ['Z','R','P']:
  a,b=get('shared',arm),get('viewshuffle',arm)
  lines.append(f"|{arm}|{float(a['cross_auc']):.4f}|{float(b['cross_auc']):.4f}|{float(a['source_macro_auc']):.4f}|{float(b['source_macro_auc']):.4f}|{float(a['source_macro_anchor_win']):.2%}|{float(b['source_macro_anchor_win']):.2%}|")
 contrast=[]
 for tag in [9000,9001]:
  for metric in ['cross_auc','source_macro_auc','source_macro_anchor_win']:
   q=next(r for r in cc if int(r['remap'])==tag and r['space']=='root64' and r['metric']==metric)
   contrast.append(f"|{tag}|{metric}|{float(q['D_R']):+.4f}|{float(q['D_P']):+.4f}|{float(q['D_Z']):+.4f}|{float(q['R_minus_P']):+.4f}|{float(q['R_minus_Z']):+.4f}|")
 histories=[read(O/(a+'_'+t)/'history.json') for a in ['shared','viewshuffle'] for t in ['Z','R','P']];times=[r['seconds'] for hh in histories for r in hh];peaks=[read(O/(a+'_'+t)/'COMPLETE.json')['peak_bytes']/2**30 for a in ['shared','viewshuffle'] for t in ['Z','R','P']]
 certs=read(R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json');count=collections.Counter(c['source'] for c in certs)
 # Positive difference alone is insufficient if it disappears under the fixed second remap.
 contrasts=[r for r in cc if r['space']=='root64' and r['metric']=='source_macro_auc']
 robust=all(float(r['R_minus_P'])>0 and float(r['R_minus_Z'])>0 for r in contrasts)
 decision='正确边界对齐只带来极小变化：R的源等权AUC额外于P的差分在两种预定重排下分别约0.00049/0.00093；合并AUC的相应差分还发生符号变化。共享R未优于共享P，本轮未确立真实等价监督的独立收益，暂不进入检测微调。' if robust else '源等权AUC的差分未在两个预定映射下同时保持R相对P/Z优势，本轮不支持正确边界对齐已带来可靠的真实等价监督独立增益。'
 sens=read(O/'CHANNEL_SENSITIVITY.json');sensrows=[]
 for s in sens['results']:
  sensrows.append(f"|{s['mode']}|{s['root_rms_change']:.6f}|{s['relative_to_root_std']:.3%}|{s['cross_auc']:.4f}|{s['source_macro_auc']:.4f}|")
 strata=rows(O/'evaluation_strata.csv');srctable=[]
 for source,n in sorted(count.items()):
  vals=[next(r for r in strata if r['alignment']=='shared' and r['arm']==t and r['remap']=='9000' and r['space']=='root64' and r['stratum']=='source' and r['value']==source) for t in ['Z','R','P']]
  srctable.append('|'+source+'|'+str(n)+'|'+ '|'.join(f"{float(v['cross_auc']):.4f}" for v in vals)+'|')
 name='等价锥边界对齐单因素预训练_seed42_20261106.md'
 text=f'''# 等价锥边界输入对齐单因素预训练（seed42，2026-11-06）

## 本轮结论

{decision}

本轮只检验功能表示，不训练检测器、不报告新检测AP。当前约0.30的检测AP仍是此前检测实验的结果，不能与这里的函数距离AUC混写。输入身份编码只是中性符号，不是真值表、SAT输出或木马标签。

## 执行合同

- ginvenv_gpu；B_shared/B_viewshuffle各Z/R/P，6组各50更新，共300次优化器更新。额外1次无优化器的梯度预检；0次检测微调、0新增SAT/Yosys、0测试集特征/标签读取。
- 39维v3、原有向图与训练集归一化保留；同改进双分支2+2+post1、hidden64。共同新增20→39无偏置零初始化残差适配器780参数；原模型46620，合计47400。投影仍root64+mean64→128/64/32。
- 相同原始初始化、投影初始化、每步随机种子、冻结采样表；382唯一配对，每组500配对名额，10个训练源各50名额。固定第50步，不按验证/测试选检查点。
- 原MSE+已有不同函数负对间隔+0.1方差，dropout0.2、BN训练行为、Adam lr0.0002/wd0.001/clip1保持。Z关闭关联正项而保留公共不同函数与方差；R拉近真实等价，P拉近错配。
- 两种边界编码都区分视图内变量，使用相同单位范数词表、类型、常量与Q/QN相位。shared跨实现同物理变量同码；viewshuffle保留一个锚视图，其余视图在PI/Q类型内循环错位；不修改电路或CEC证书。
- 训练每步统一重排槽位。验证只用预先确定的9000与9001两个共同重排，不根据表现选择。

## 加载与正确性检查

32视图、15源/查询上下文均完成直接边界输入消费者的逐行核对：训练23403行、验证34462行；其余区域两组都无新增通道，DFF行零侧输入。不是全388视图边界接口覆盖。

旧锥members按名称顺序、graph_rows按数值排序，两者不是可直接zip的逐项对应。入口通过网表实例名→冻结图名字建立映射，并核对每个锥成员集合和根；没有改旧证书或图。另有{sum(int(r['auxiliary_nodes_verified']) for r in mapping)}个连续赋值辅助门，按操作类型、输出bit及全部有序输入bit匹配到v2辅助行，不凭raw门名顺序猜测。

20维通道为PI/Q/常量0/1四类直接输入脚计数的log1p，以及16维带相位的变量码求和，除以sqrt(max(1,全部直接边界与常量输入脚数))。它没有加入MUX的A/B/S角色，仍是压缩摘要，不能证明完整功能信息已无损进入模型。

零适配器时注入前后输入逐位完全相等、原权重逐项相同；GPU两次散射求和的输出最大差1.45e-7，通过浮点容差检查。适配器梯度范数0.03213，原编码器梯度范数和3.59666；未断梯度。六组均完成50步、优化器实际step=50、权重有限、分类头未更新；检查点与旧输入哈希已独立复核。

开发预检的4次中断都发生在优化器更新之前，失败日志和当时合同保留。除上面的排序/辅助坐标处理外，还修正了旧inventory没有split字段时应从锥读取划分，以及GPU输出不能要求逐位一致的预检判据；这些不是额外训练或重算成功批次。

## 主结果：检测入口root64（验证映射9000）

|预训练组|共享 合并AUC|错位 合并AUC|共享 源等权AUC|错位 源等权AUC|共享 源等权同anchor正确排序|错位 源等权同anchor正确排序|
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

这里AUC的正样本是同函数真实跨实现距离，负样本是已有不同函数证书构造的错误跨实现距离；两类均跨相同实现方向，用负距离打分，0.5为随机排序参考。它不是木马分类AUC或AP。同anchor排序在各块比较同一左根的真实与错误右根，平局半分。

## 对齐的额外作用：差分与预定重排复核

D_R=共享R−错位R，P/Z同理。R−P/R−Z列是D_R−D_P、D_R−D_Z，避免把六组共同的输入改善归功于真实等价监督。

|验证映射|root64指标|D_R|D_P|D_Z|D_R−D_P|D_R−D_Z|
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(contrast)}

## 证据范围与限制

68块验证证书、{read(O/'ANALYSIS_COMPLETE.json')['unique_cones']}个唯一验证锥，全部与训练配对端点不重叠；既有272根反例回放全部通过，本轮复用证明，不做新SAT。验证仅5个独立源、同一宿主，各源块数为：{'; '.join(f'{k}: {v}' for k,v in sorted(count.items()))}。重复锥和同源块不视为独立样本，不把单seed写为统计显著；配方/锥大小是分层报告，未实现精确门型/大小联合匹配。

完整root64、concat128、projection32的方差、有效秩、同视图不同函数及源/配方/大小结果见evaluation_summary.csv、evaluation_strata.csv。不能只看投影空间距离或挑一个表现好的源。

共享编码下逐源root64 AUC（映射9000）：

|独立验证源|证书块数|Z|R|P|
|---|---:|---:|---:|---:|
{chr(10).join(srctable)}

ctlmatchb接近0.5，injalpha较可分但P仍高于R；其余三源只有2/1/1块，不能把源等权平均约0.66理解为全面泛化。共享R的root64有效秩约3.26，投影32维约1.81：不是常量坍缩，但仍偏低秩；投影合并AUC约0.586也未优于P约0.593。

## 同一检查点的通道敏感度（事后诊断）

固定共享R第50步权重与BN，复用相同验证锥，另做3次纯前向：重复共享、故意错位、关闭整个20维通道。没有重新训练，也不据此选择检查点。

|固定权重下的输入|相对原共享root的RMS变化|相对原root整体标准差|函数合并AUC|源等权AUC|
|---|---:|---:|---:|---:|
{chr(10).join(sensrows)}

重复共享行给出BF16/散射的数值重复性参考；关闭通道同时去掉计数和身份，错位行只改对应。适配器权重范数约0.04746且梯度已通过，所以不是未接入或永久为零；这些诊断只能量化当前权重对通道的敏感性，不能证明完整引脚接口无价值。

六组训练步内用时中位数{np.median(times):.3f}秒、合计{sum(times):.1f}秒（不含启动、检查点落盘和评价）；训练峰值显存最大{max(peaks):.2f}GiB。失败预检、全部成功检查点和日志保留，未删除或移动任何文件，未修改历史训练脚本。

## 下一步

先以本轮差分、两个预定重排和逐源结果决定是否有功能表示信号。若收益不稳定，优先在相同边界底座上检验引脚角色输入，使用相同参数/预算的真实角色与角色错位对照；不继续扩大SAT池或追加种子来掩盖输入缺口。当前P0没有MUX选择端语义，且root感受野与大锥深度不匹配，因此本轮不足以否定完整引脚+边界接口。

如以后进入检测迁移，须另立公平合同，明确新增通道在原始侧、变换侧及留出视图的提取和保留方式，不能丢弃适配器后宣称已验证功能信息提高AP。本轮未自动开始下一组实验。

证据目录：`_p0pilot/cec_boundary_seed42_20261106/`；EXECUTION_CONTRACT.json、MAPPING_VERIFIED.json、PREFLIGHT.json、六组FIRST_STEP/COMPLETE/checkpoint、evaluation_*.csv、alignment_contrasts.csv、ANALYSIS_COMPLETE.json及VERIFIED.json。
'''
 (D/name).write_text(text,encoding='utf-8')
 mainr=get('shared','R');controlr=get('viewshuffle','R')
 entry=f'''\n\n### 2026-11-06 等价锥边界对齐单因素预训练（已完成）

ginvenv_gpu完成共享/视图错位边界各Z/R/P，6×50=300预训练更新；额外1次无优化器梯度预检，0检测微调、0新SAT、0测试读取。同39v3/有向图/原初始化/损失/dropout0.2/BN/382唯一配对500名额；共同新增20→39零适配器780参数，仅改变跨视图变量编码对应，MUX引脚角色仍未加入。32视图逐行映射通过，训练23403/验证34462直接边界消费者；成员列表与数值排序图行不能zip，{sum(int(r['auxiliary_nodes_verified']) for r in mapping)}辅助门按输出/输入bit和类型核对。预检输入权重完全一致、输出误差1.45e-7，梯度通畅；六组50步与旧资产哈希、分类头不变经独立核验。主验证root64共享Z/R/P合并AUC={float(get('shared','Z')['cross_auc']):.4f}/{float(mainr['cross_auc']):.4f}/{float(get('shared','P')['cross_auc']):.4f}，错位={float(get('viewshuffle','Z')['cross_auc']):.4f}/{float(controlr['cross_auc']):.4f}/{float(get('viewshuffle','P')['cross_auc']):.4f}。{decision}两个预定重排、源等权和逐源/配方/大小证据单列；68块仅5验证源/1宿主，不作检测AP提升或显著性结论。优先分析角色接口，不自动微调/扩SAT/补种子；保留旧图、SAT、模型及全部失败预检日志。详见[{name[:-3]}]({name})，证据`_p0pilot/cec_boundary_seed42_20261106/`。
'''
 for n in ['SAT作用证明.md','SAT工作总结.md']:
  p=D/n
  if '### 2026-11-06 等价锥边界对齐单因素预训练（已完成）' not in p.read_text(encoding='utf-8-sig'):
   with p.open('a',encoding='utf-8') as f:f.write(entry)
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str((D/name).relative_to(R)),updated=['SAT作用证明.md','SAT工作总结.md'],time=datetime.datetime.now().isoformat()),ensure_ascii=False,indent=2),encoding='utf-8')
 print(name)
if __name__=='__main__':main()
