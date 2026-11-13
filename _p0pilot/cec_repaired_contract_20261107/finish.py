from pathlib import Path
import collections,gzip,hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'10.15/00_说明';P=R/'_p0pilot/cec_boundary_panel_expand_20261107'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
v=read(O/'VERIFIED.json');assert v['passed'];train=read(O/'TRAIN_TRIPLES.json');byid={u['unit_id']:u for u in train};schedule=read(O/'SCHEDULE_SEED42.json')
with gzip.open(P/'local_graphs.json.gz','rt',encoding='utf-8') as f:z=json.load(f)
graphs=dict(zip(z['cone_ids'],z['graphs']));ctx=dict(zip(z['cone_ids'],z['contexts']));counts=collections.Counter()
for u in train:
 assert len({ctx[c] for c in u['cones']})==1 and len({tuple(sorted(s for s in graphs[c]['slot'] if s>=0)) for c in u['cones']})==1
for step in schedule:
 assert len(step['units'])==2 and abs(sum(r['query_weight']*6 for r in step['units'])-1)<1e-12
 for r in step['units']:
  assert r['cone_ids']==byid[r['unit_id']]['cones'];counts[r['unit_id']]+=1
  mass={k:collections.Counter(c[t] for c,t in zip(r['candidates'],r[k])) for k in ['real_targets','permuted_targets']};assert mass['real_targets']==mass['permuted_targets']==collections.Counter(r['anchors'])
  for a,c,t in zip(r['anchors'],r['candidates'],r['permuted_targets']):j=r['anchors'].index(c[t]);assert r['candidates'][j][r['permuted_targets'][j]]==a
assert max(counts.values())<=16
for p,h in v['protected_files'].items():assert sha(R/p)==h,p
files=['TRAIN_TRIPLES.json','TRAIN_PAIRS_DIAGNOSTIC.json','VAL_H3_NONFORCED.json','SCHEDULE_SEED42.json','BUDGET.json','REPAIRED_CONTRACT.json']
(O/'FROZEN_INDICES.json').write_text(json.dumps({n:sha(O/n) for n in files},indent=2),encoding='utf-8')
report=S/'等价锥候选准入与对照合同修订_20261107.md'
text='''# 等价锥候选准入与对照合同修订

已复用现有面板修订候选，未训练、未做模型前向或追加SAT。

- 准入要求：全部候选使用同一实际PI/Q集合；真实对应不是当前编码器强制相同的计算表达式；复用原等价证明与不同函数反例；加入编码器隐含相等后R/P均无已知正负冲突。
- 可用三函数训练池：7单元、21函数类、4制造源、2家族（rs232与s15850），含MUX3单元。另14个双函数训练候选单独保留，不补造第三候选。
- 去除无需学习已相同的配对后，H3验证保留73单元；旧85单元和PO诊断原样保留，新子集不改写旧结果。
- 新Z/R/P合同：沿用47,360参数模型、共同初始化、损失、FP32和优化器设置；拟各32步，每步每家族1个三函数单元。每组64单元名额、384查询、1,152候选距离、384公共负项，单函数最多16次。
- 这不是旧三家族/576查询协议的单因素修正版。s35932目前没有进入合格池；若比较新旧训练难度，必须先将双方限制到共同家族，并重新匹配预算。
- 此轮只修候选。共享重编码下的排序一致性留作后续单因素，不同时改模型和损失；不直接强求单锥向量对任意身份重排不变。

必要条件检查、同边界、目标双射、反向逆置换及索引预算检查通过；尚未证明P一定可拟合。下一步先做实际加载和无更新梯度预检，再决定训练。

证据：`_p0pilot/cec_repaired_contract_20261107/`中的REPAIRED_CONTRACT.json、TRAIN_TRIPLES.json、VAL_H3_NONFORCED.json、SCHEDULE_SEED42.json、FROZEN_INDICES.json和VERIFIED.json。原实验资产保持，准备脚本的两次语法失败日志保留。
'''
assert not report.exists();report.write_text(text,encoding='utf-8')
heading='### 2026-11-07 等价锥候选准入与对照合同修订（未训练）'
block='\n\n'+heading+'\n\n已复用既有面板排除输入集合捷径与编码器强制相等配对，并复用原不同函数见证；三函数训练池7单元/21函数类/4制造源/2家族，含MUX3；另14个双函数候选单列。H3去强制相等后验证73单元，旧85及PO诊断保留。新Z/R/P方案各32步、64单元名额/384查询/1152候选距离/384公共负项，最大函数曝光16；与旧三家族预算不同，不作直接单因素前后比较。模型、初始化、损失和编码暂不改；编码稳定性留后续单因素。同边界、必要可实现性、隐含冲突、目标双射/逆置换与预算检查通过，但不保证P一定可拟合。下一步加载及无更新梯度预检。当前0训练/0模型前向/0SAT，旧资产保持。\n\n详见[合同修订汇报](等价锥候选准入与对照合同修订_20261107.md)，证据`_p0pilot/cec_repaired_contract_20261107/`。\n'
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=S/name;old=p.read_text(encoding='utf-8-sig');assert heading not in old;shutil.copy2(p,O/(name+'.before_round.bak'));p.write_text(old.rstrip()+block,encoding='utf-8')
for p,h in v['protected_files'].items():assert sha(R/p)==h,p
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(report.relative_to(R)),report_sha=sha(report),training=0,SAT=0,actual_loading_pending=True,independent_schedule_checks=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('REPAIRED_CONTRACT_AND_TWO_LOGS_UPDATED')
