"""Publish frozen-checkpoint cause audit and correct prior index-only control scope."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(O/'VERIFIED.json')['passed'] and read(O/'VERIFIED.json')['training']==0
for n,h in read(O/'OUTPUT_MANIFEST.json').items():assert sha(O/n)==h,n
for p,h in read(O/'FROZEN_EXECUTION.json')['protected_files'].items():assert sha(R/p)==h,p
report=S/'自由Q编码反转与MUX困难原因审计_20261107.md';heading='### 2026-11-07 自由Q编码反转、公共项与MUX原因审计及对照解释更正（已完成，未训练）'
block='''

### 2026-11-07 自由Q编码反转、公共项与MUX原因审计及对照解释更正（已完成，未训练）

复用上一轮INIT/Z/R/P检查点和表示，缓存分析后做固定检查点诊断：278次冻结前向、84次无更新自动微分，初始化梯度直接复用；优化器对象/参数更新/SAT/真实网表新输入模式/测试读取均0。受保护旧文件与模型哈希保持，旧主指标不改写。

- 反转不是R绝对胜率整体下降：9000→9001 R增加0.78个百分点、P增加2.55，两组差值净变-1.76；约-0.59来自ctlmatchb、-1.18来自injalpha。R约25.29%单位加权方向比较改变胜负，初始化也有25.59%。代码映射维持共享双射，拓扑/操作/角色/极性不变；未发现边界对应错乱。
- 验证变量16维编码内积随重排变化，非对角Gram差RMS约0.354，中性不等于几何不变。R真假距离差随编码变化RMS0.2198，是9000下R/P差RMS0.0512的4.29倍；重复同输入最大根差仅约1.1e-6，不能归因数值噪声。
- 固定追加9002—9005映射，原9000/9001复用。6套R-P差（百分点）+1.18/-0.59/+0.29/-1.18/-0.69/-1.57，R-Z差+0.39/+0.10/-0.10/-0.10/-0.20/-0.78；R只在2/6优于P、2/6优于Z。六编码均值INIT/Z/R/P=77.25/76.94/76.83/77.25%。这是事后编码敏感性，不是六种子重复或新主要指标。
- 训练/评价难度错位：原21训练单元无一个全候选同边界，仅用PI/Q输入集合Jaccard距离即100%配对胜率；85H3该基线50%。它证明存在无须门级功能组合的捷径，不直接证明模型实现Jaccard。冻结R去掉身份编码后主胜率78.33→48.09，确实依赖身份信息，但不能据此宣布已学会函数组合。
- 【更正前轮对照审计范围】63训练真配对中，s35932的36对具有相同的类型/变量/角色/极性递归计算表达式，当前共享根编码器在理想实数计算下必然给相同表示；四状态两编码实测真距离最大约6.2e-7。其占192/576查询、实际权重1/3，P无法把错误候选严格排在零距离真候选之前。仅索引正负图检查R/P均0冲突，但加入编码器强制相等后P有72/126唯一公共负边落入冲突分量，R仍0。此前“无正负冲突”只适用于索引，模型层可实现性审计不完整。本轮程序/预算/数值仍有效，R-P解释降级，不删除旧结果，也不作为新增功能学习收益证据。详见AUDIT_CORRECTION.json。
- 分项梯度：初始化公共/真实范数比1.69—2.47，末次R仅0.53—0.82，不能说真实项始终被压没。16组固定检查的公共项下降方向均降低真实CE、提高错误CE；Z可间接改善真实关联，P受牵制。末次R同点反事实R/P总梯度余弦约-0.42至-0.10，方向已分开；实际参数位移R/Z余弦0.984、P/Z0.972。局部梯度和轨迹描述不是Adam因果贡献百分比，未改权重。
- 同源同流程ctlmatchb abc/aig中，R的MUX23单元47.83%、非MUX11单元51.52%，问题不只MUX。训练仅4个含MUX单元（abc/aig仅2个），全部允许集合捷径；验证MUX全部是一侧原生、另一侧展开。训练/验证最大端点门数中位442.5/160、深度35/31，不能简单归因验证更深更大。
- 已有16个合成输入位置检查MUX=NOT/AND/OR展开恒等式，PI/Q版本Boolean正确；冻结R真假排序PI为16.67/25%、Q为50/41.67%（两编码），没有掌握可泛化组合恒等式。只作小压力测试，不替代网表指标。错置MUX角色，R的9000由47.83→44.93、9001由50→50.36，无一致方向；有角色反应不代表已正确学会组合，也不支持删除角色。
- 下一步先重订候选与对照准入：控制输入集合捷径、检查编码器隐含相等及P可实现性；结构上无需学习已相同者单列先验诊断。三组共用资格掩码/家族支持/候选数/曝光，不能静默替换旧池。再研究共享重编码下的关系排序一致性，不直接要求单锥向量对任意身份重排不变，以免抹去NOT(a)/NOT(b)区分；最后才决定损失调权或新训练。暂不追加训练、种子、检测微调或SAT。

详见[编码反转与MUX原因审计](自由Q编码反转与MUX困难原因审计_20261107.md)。证据`_p0pilot/cec_freeq_encoding_audit_20261107/`：VERIFIED.json、AUDIT_CORRECTION.json、six_code_metrics.csv、BOUNDARY_SHORTCUT_BASELINE.csv、root_encoder_hardties.csv、encoder_augmented_target_conflicts.csv、component_gradient_summary.csv、MUX_matched_source_metrics.csv与MUX_boolean_identity_stress.csv。CPU独立复核24组编码指标、16组完整梯度及另一种编码器等价类构造通过。
'''
changes=[]
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=S/name;old=p.read_text(encoding='utf-8-sig');assert heading not in old
 backup=O/(name+'.before_round.bak');assert not backup.exists();shutil.copy2(p,backup)
 p.write_text(old.rstrip()+block+'\n',encoding='utf-8');new=p.read_text(encoding='utf-8');assert new.startswith(old.rstrip()) and new.count(heading)==1
 changes.append(dict(path=str(p.relative_to(R)),before_sha=sha(backup),after_sha=sha(p),append_only=True))
for p,h in read(O/'FROZEN_EXECUTION.json')['protected_files'].items():assert sha(R/p)==h,p
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(report.relative_to(R)),report_sha=sha(report),verified_sha=sha(O/'VERIFIED.json'),control_correction_sha=sha(O/'AUDIT_CORRECTION.json'),docs=changes,model_forwards=278,autograd_calls=84,training=0,SAT=0,test_reads=0,protected_old_assets_unchanged=True,old_metrics_preserved=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('ENCODING_MUX_CAUSE_AUDIT_AND_CORRECTION_PUBLISHED')
