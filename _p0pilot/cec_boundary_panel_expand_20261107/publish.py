"""Publish expanded same-boundary evaluation evidence;no experiment execution."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(O/'VERIFIED.json')['passed'] and read(O/'VERIFIED.json')['model_forwards']==0
for name,h in read(O/'OUTPUT_MANIFEST.json').items():assert sha(O/name)==h,name
for p,h in read(O/'PANEL_COMPLETE.json')['protected_files'].items():assert sha(R/p)==h,p
report=S/'同边界功能困难评价面板扩充_20261107.md';heading='### 2026-11-07 复用5238配对扩充同边界功能困难评价面板（已完成，未训练）'
block='''

### 2026-11-07 复用5238配对扩充同边界功能困难评价面板（已完成，未训练）

全量复用5238条既有训练/验证配对，未训练、反向、模型前向、新SAT、新真实输入模式或测试读取。原模型初始化、训练池和32步采样合同、旧图/标签/证明保持；只新增评价数据与评价合同。

- 全端点同边界主面板：训练划分侧21评价单元（7三函数/14双函数，49上下文内观测函数类，7制造源/2家族/2宿主/4流程对，含MUX3）；验证98单元（55三函数/43双函数，251类，2制造源/1家族/1宿主/2流程对，含MUX23、根MUX6）。训练侧21评价单元不是旧21三函数预训练池，不能替换旧采样。
- 结构分层H3/H2/H1的训练侧支持为3/1/17，验证85/6/7。H3匹配根门型、精确规模/深度、操作/引脚/相位/重复脚统计；H2只精确规模/深度，H1为预定规模/深度分层。85个H3验证单元（44三函数、41双函数）作为新主要比较，98整体及其他层级扩展报告，不用有利子集替换主要结果。
- 验证主面板ctlmatchb34/injalpha64，H3为34/51；23个含MUX单元全来自ctlmatchb，独立MUX源仍不足。4个覆盖补充单元（训练3/验证1）增加nand流程、部分rs232源MUX和验证injepsilon；其中3个仅B0同边界，不并入严格主评价。合并后训练5流程对、验证3制造源，但后者不等于严格主评价3源。
- s35932的1763条既有配对、s15850ctlmatcha、验证injbeta/injzeta仍无可组成同边界不同函数竞争的组；主面板无所有端点≤16门且深度≤4的浅小单元。数量扩大不等于新独立宿主增加，验证仍仅s38417。
- 同边界主面板要求两实现全部端点的实际PI/Q集合一致。另29验证单元仅每侧候选集合相同、左右集合不同，单列边界化简迁移诊断，不并入98。原严格PO文件按字节保留（训练4/验证4双函数），新主面板内另有2/7双函数PO精确诊断，均与主体重叠，不简单相加。
- 核心同上下文/观测签名函数最多1次，含流程/MUX补充最多2次；跨制造源、视图和互逆查询不计新独立函数。主要按原生上下文家族等权，源等权及逐源/流程并报；双/三候选任务分开，缺失支持记NA。19个预定义分组权重归一化通过。
- 验证H3的门型/规模/深度/无极性边界集合距离基线均50%，但PO距离约92.16%家族等权；H1有剩余规模/深度线索。自由Q模型继续不读PO，不能将含PO旧模型高分直接归因于功能；面板也不证明全部结构代理线索已消失。
- 374条入选配对原证明/枚举及根映射核对，10条既有原生查询模型/规范化脚本文本/完整日志及准确成功块复核。294条不同函数见证全部通过独立原网表Boolean回放，30条直接旧见证、264条只回放既有输入位置，不是新SAT或新增等价证明。
- 实际导出770锥、8个25维数值分片、240651节点/308595引脚边；主119+补充4共123单元完成加载与查询构造检查，单锥/合批一致，无第三候选填充。数据接口可以复用，未做模型前向。首次核验错误采用旧哈希字段口径已修正，原证明文件未改，失败日志保留。
- 新评价合同与权重已冻结；下一轮应显式绑定新评价合同和原训练合同，再建立共同初始化基线/决定ZRP探索，不自动训练、扩SAT或修改旧结果。

详见[同边界评价面板扩充汇报](同边界功能困难评价面板扩充_20261107.md)。证据`_p0pilot/cec_boundary_panel_expand_20261107/`：MAIN_ALL_ENDPOINTS_SAME_BOUNDARY.json、FINAL_EVALUATION_POLICY.json、EVALUATION_WEIGHT_GROUPS.csv、FUNCTION_ALIAS_AUDIT.json、STRICT_PO_REFERENCE_UNCHANGED.json、DIFFERENT_FUNCTION_CERTIFICATES.json、panel_loader.py、ACTUAL_UNIT_LOADING.csv和VERIFIED.json。
'''
changes=[]
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=S/name;old=p.read_text(encoding='utf-8-sig');assert heading not in old
 backup=O/(name+'.before_round.bak');assert not backup.exists();shutil.copy2(p,backup)
 p.write_text(old.rstrip()+block+'\n',encoding='utf-8');new=p.read_text(encoding='utf-8');assert new.startswith(old.rstrip()) and new.count(heading)==1
 changes.append(dict(path=str(p.relative_to(R)),before_sha=sha(backup),after_sha=sha(p),append_only=True))
for p,h in read(O/'PANEL_COMPLETE.json')['protected_files'].items():assert sha(R/p)==h,p
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(report.relative_to(R)),report_sha=sha(report),evaluation_contract_sha=sha(O/'FINAL_EVALUATION_POLICY.json'),main_panel_sha=sha(O/'MAIN_ALL_ENDPOINTS_SAME_BOUNDARY.json'),verified_sha=sha(O/'VERIFIED.json'),docs=changes,training=0,SAT=0,model_forwards=0,old_experimental_files_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('EXPANDED_PANEL_REPORT_AND_TWO_LOGS_UPDATED')
