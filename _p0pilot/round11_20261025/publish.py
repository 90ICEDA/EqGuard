"""Publish three-batch results, cumulative registry, and the next agent prompt."""
import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'10.15/00_说明'
TABLES=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'
OUT=TABLES/'sat_pair_round11';OLD=TABLES/'sat_pair_round10'


def backed(path,text):
    if path.exists():
        b=path.with_name(path.name+'.bak_round11_20261025')
        if not b.exists():shutil.copy2(path,b)
    path.write_text(text,encoding='utf-8')


def main():
    m=json.loads((OUT/'audit_manifest.json').read_text());assert m['new_sat_queries']<=576
    assert m['examined_candidates']==24 and m['cumulative_validated']==11
    assert m['reviews']==m['review_agree']==26 and m['feature_max_abs_diff']==0
    old=np.load(OLD/'paired_features.npz');new=np.load(OUT/'paired_features_new.npz')
    source=np.concatenate([old['source'],new['source']]);partner=np.concatenate([old['partner'],new['partner']])
    assert source.shape==(11,18) and np.array_equal(source,partner)
    payload=json.loads((OUT/'validated_pairs_cumulative.json').read_text())
    np.savez_compressed(OUT/'paired_features_cumulative.npz',relation_id=np.array([x['relation_id'] for x in payload]),source=source,partner=partner)
    policy=dict(context_id=payload[0]['context_id'],training_approved=False,training_loader_compatible=False,
        old_P1_proved_is_locator_only=True,same_temporary_name_is_not_a_correspondence=True,
        correspondence_failure_is_not_feature_instability=True,labels_must_not_be_transferred=True,
        no_original_40_targets_replaced=True,graph_coverage_gain_not_claimed=True)
    (OUT/'pair_acceptance_policy.json').write_text(json.dumps(policy,indent=2),encoding='utf-8')
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    report=f'''# 第十一轮：剩余候选三批核验、对应阻塞与累计迁移结果

更新时间：{now}。不增加原40条之外的目标或候选实现，不启动训练，不评估测试集。对第十轮尚待验证的24条已有候选，分3批、每批8条进行核验，合计408个新SAT子查询（统一上限576）。

## 结论

- 本轮24条已逐一核验：新增5条完整配对，均在train；另19条边界对应未证明，不能拿来评价特征迁移失败。
- 累计11/40条已配对：train9、val2。本轮未增加val成功对，四个val候选均卡在临时线名对应上。不是全部40条已补齐。
- 新增5条在统一上下文下，完整边界表、18维描述和逐输入统计全部一致，最大差异0；原侧迁移与历史边界表5/5一致。新增5条有4种特征组合，累计特征不作为训练增益证据。
- 25个边界信号证明（可含精确复用）有引用；48条门节点落点+2个真实PI锚。没有复制标签、创建虚构驱动门或改写旧训练特征。

## 三批结果

| 批次 | 候选 | 完整配对 | 对应未证明 | 新查询 |\n|---|---:|---:|---:|---:|
| 1 | 8（train4/val4） | 2 | 6 | 156 |
| 2 | 8（train） | 2 | 6 | 149 |
| 3 | 8（train） | 1 | 7 | 103 |

新增配对：rs232/injzeta/U6.Y、s15850/injepsilon/g8563、rs232/ctldup/CtrlDDUP3.Y、rs232/ctlmatcha/uart_XMIT_dataH、s15850/ctldup/g6920。逐源实例、另一实现和证明引用见validated_pairs_new.json及validated_signal_pairs.csv。

## 复用与查询上下文

沿用第十轮的native_unrestricted_combinational_physical_Q_v1：同一源实例、同PI位、同名物理Q自由状态，QN取互补，不加正常运行模式约束。源文件/raw快照SHA256、模型生成器版本、PI/状态/观察端schema均核验。

复用6份已绑定来源的证明：按同一源快照、同一上下文和实际bit对应复用，不按裸网名、函数签名或旧P1 proved复用。结构快照按源哈希读取，未重新跑全量P1或全网SAT sweeping。局部候选仅限固定partner中存在的源same-bit别名或此前候选，每位置最多两个；反例拒绝的同一对应不重新包装成成功。

成功关系两侧各做16模式×2 prove完整枚举；partner位序沿源cut槽位保留。使用单个pattern相等谓词处理逻辑别名约束，不依赖多次-set同一物理bit的覆盖行为。

这仍是组合状态边界，不是复位可达性、自然时序触发或完整时序CEC。原侧边界表迁移相等不代表所有legacy/native模型全局等价。没有把信号相同直接用于整单元embedding或安全角色一致性训练。

## 未完成项，分开记录

| 累计状态 | 条数 | 含义 |
|---|---:|---|
| paired_validated | 11 | 同源边界证明和完整表均通过 |
| temporary_alias_correspondence_unproved | 18 | 临时网名在不同实现不等价，尚无有效替代对应 |
| boundary_correspondence_unproved | 1 | 非临时边界候选未证明，需另查来源/区域/状态假设 |
| candidate_mapping_incomplete | 8 | 上轮就缺完整边界候选，未用本轮数字掩盖 |
| local_alias_unavailable | 2 | 上轮局部别名不足，保持未解决 |

原24条candidate_pending已全部处理，没有继续留在“待跑”；但29条仍是明确的阻塞项，不是成功配对。blocking_issues.csv记录失败槽位、源网名、尝试别名和固定partner，避免下一agent反复对相同临时线名做无依据重试。

重写可能真的消除了某个内部信号，也可能只是其名字/追踪元数据丢失。本轮没有证明这两者中的任一种，因此不能把“暂时没有别名”写成“没有功能等价信号”，也不能把原源锥复制进partner来伪造对应。

## 验证与一次恢复修复

408个查询：233 proved、175 refuted，0 unknown/error；refuted在对应问题上是反例，在表查询上是反对某个强制值，含义分开。

26/26独立进程复核一致；29个三值独立回放通过（19个失败对应的反例+新增5对两侧各1个表见证）；128个模式位序等细节另沿用上下文回归。实际磁盘408份逐查询日志与账本408条一一对应，哈希及脚本中的实际约束逐条核对。

第二批在保存账本前遇到复核目录编号冲突，覆盖保护拒绝写旧目录；没有重复求解。修复了循环变量覆盖批次编号的问题，保留原计划时间/hash，从144个已执行查询的不可变日志恢复账本。恢复必须同时匹配模型、完整脚本、查询约束和原批次日志块，不能仅信任一个status文本。已增加复核前检查点。恢复4项回归及原上下文8项回归均通过。

下一阶段不再“继续跑剩余24条”：它们已核验。重点是29条阻塞的正确映射，特别是val临时线名；先检查变换map/源锚/状态上下文，小额验证，不能扩大为全网搜索，更不能拿旧P1 proved填空。再下一轮可复制prompt已生成。

## 产物

目录tables/sat_pair_round11：三份冻结plan、三批查询账本/证明/复用引用、pair_coverage_40.csv、blocking_issues.csv、all_outcomes.csv、independent_replays.csv、validated_pairs_new.json、validated_pairs_cumulative.json、paired_features_cumulative.npz（11×18双侧稀疏诊断）、boundary_attachments.csv、audit_manifest.json及pair_acceptance_policy.json。

只核对已有结果：ginvenv/Scripts/python.exe -B -X utf8 _p0pilot/round11_20261025/audit.py；测试：test_batch_recovery.py及round10/test_context.py。不要为了阅读报告重跑batch.py。原第十轮证据和旧P1表保留不变，未写训练loader。
'''
    # Avoid implying a count of additional tests that was not actually executed.
    report=report.replace('128个模式位序等细节另沿用上下文回归。','位序、逻辑别名和Q/QN等细节另通过上下文回归检查。')
    backed(DOC/'SAT第十一轮_候选批验与对应阻塞_20261025k.md',report)
    section=f'''\n\n<!-- sat_pair_round11:start -->
## 21. 第十一轮：24候选三批核验（未训练）

更新时间：{now}。详见[SAT第十一轮_候选批验与对应阻塞_20261025k.md](SAT第十一轮_候选批验与对应阻塞_20261025k.md)。

- 第十轮剩余24条已有候选分3批全部核验；新增5条train配对，累计11/40（train9/val2），没有新增val成功对。未扩大目标或候选实现，未训练/评估测试集。
- 新增408问（≤576），复用6份源/上下文绑定证明；26复核全一致，29反例/表见证独立回放通过。新增5条完整表、18维特征及逐输入统计双侧差异0，原侧迁移5/5一致。
- 累计未解决：18临时网名对应未证明、1其他边界对应未证明、8缺边界候选、2缺局部别名。不是特征不稳定，也不是29条已解决；单列blocking_issues.csv。
- 新增25个边界位置证明引用，48个门节点落点+2个真实PI锚；不复制标签，不创建虚构驱动门，不写训练loader。累计双侧诊断特征11×18。
- 第二批目录冲突由保护机制阻止覆盖；修复编号变量并从144个原查询记录恢复，无重复求解。全部磁盘日志与账本408条一一核对，恢复4回归+上下文8回归通过。
- 下一轮转向29条映射阻塞，优先val，不能直接沿用旧P1 proved或重复同名线兜圈；可复制prompt已生成。
<!-- sat_pair_round11:end -->\n'''
    for name in ['SAT作用证明.md','SAT工作总结.md','10.22完成情况_第七轮证据审计.md']:
        path=DOC/name;text=path.read_text(encoding='utf-8')
        if '<!-- sat_pair_round11:start -->' not in text:backed(path,text+section)
    prompt='''请在 C:\\Users\\91344\\Desktop\\GraphSAINT\\GIN_train 继续下一轮。先读 SAT作用证明、SAT工作总结、SAT第十一轮_候选批验与对应阻塞_20261025k.md，以及 tables/sat_pair_round11 的 pair_coverage_40.csv、blocking_issues.csv、validated_pairs_cumulative.json、pair_acceptance_policy.json。

当前11/40配对已验证（train9/val2）。原24个待验候选已全部核验，不能再按“剩余24待跑”安排。29条阻塞分别为：18临时网名对应未证明、1其他边界对应未证明、8缺完整边界候选、2缺局部别名。

本轮只解决映射阻塞，优先验证集；不新增原40之外的目标，不扩大为全网SAT sweeping，不训练。
1. 先离线审计变换map、源网表/JSON、源锚和旧日志的源哈希/上下文，区分名字丢失、候选不等价、真实信号被优化掉、状态假设不同。旧P1 proved和同名只能作线索，不能作最终证明；已反例拒绝的同一源/上下文/候选不要无依据重试。
2. 冻结最多4条阻塞样本（优先2 val+2 train），只在固定partner的原始锚和小局部区域内找候选。选样不看标签或正例位置。源/partner缺少快照绑定时先补来源，不把裸网名当身份。
3. 允许用真实区域输入输出边界处理拆分/合并；但不能复制源电路进partner、制造虚拟输出后宣称找到物理节点。不存在可靠节点对应时明确标区域对应/未对应，不计节点覆盖。
4. 沿用第十、十一轮相同的无模式约束、共享PI/物理Q native组合上下文，先证明4个cut位置和目标。若需反相，必须单独证明极性并显式转换坐标；改变时序/可达假设必须另立上下文，不能混入当前配对。
5. 最多完成2条新的完整配对，优先val。两侧各16模式×2prove；原侧若有同上下文、同源哈希、同边界的完整表可复用。检查完整表、逐输入统计和18维特征；签名相同不能替代信号证明，不复制安全标签或hidden embedding对应。
预算：对应验证≤48问、两条双侧完整表≤128问、独立复核≤16问，总计≤192实际SAT子查询，超时/错误/重跑均计入；单查询优先5秒，查询墙钟≤30分钟。达到上限整理结果，不扩预算或扫全图。
优先复用第十、十一轮已经绑定源快照、上下文和实际bit的证明，不重新跑已验证11对。CPU用ginvenv；未来获准训练才用ginvenv_gpu。新产物版本化；不得覆盖旧求解文件，复核前保存检查点，恢复必须核对完整脚本/模型/约束/批次日志，所有实际查询只计一次。

完成后更新SAT作用证明、SAT工作总结、repro/index.csv及全40条累计状态。明确哪些只是新候选、哪些已证明、哪些仍阻塞；若确实无法节点对应就停止强配，不虚增covered。最后给出后续建议并停止，不自动训练或继续扩搜索。
'''
    prompt=prompt.replace(chr(92)*2,'/')
    backed(DOC/'再下一轮prompt_阻塞边界映射_20261025.txt',prompt)
    index=ROOT/'10.15/99_共用资产/repro/index.csv';backup=index.with_name(index.name+'.bak_round11_20261025')
    if not backup.exists():shutil.copy2(index,backup)
    with index.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;ids={r.get('id') for r in reader}
    if 'sat_pair_round11_20261025' not in ids:
        with index.open('a',encoding='utf-8',newline='') as f:
            csv.DictWriter(f,fieldnames=fields).writerow(dict(kind='audit',id='sat_pair_round11_20261025',path=str(OUT.relative_to(ROOT)),seed='',
                config='_p0pilot/round11_20261025',note='24 candidates/3 batches; 5 new,11 cumulative;408 queries;26 reviews;29 replays;no training'))
    provenance=dict(new_queries=408,training_runs=0,
        code_sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        output_sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='provenance.json'})
    (OUT/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    print('Round11 reports, cumulative registry, summaries, repro and next-round prompt updated.',flush=True)


if __name__=='__main__':main()
