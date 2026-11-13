"""Publish context-aligned, source-bound pairs; no training integration."""
import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
import pandas as pd
import native as N

DOC=N.ROOT/'10.15/00_说明'


def backed(path,text):
    if path.exists():
        b=path.with_name(path.name+'.bak_round10_20261025')
        if not b.exists():shutil.copy2(path,b)
    path.write_text(text,encoding='utf-8')


def main():
    audit=json.loads((N.OUT/'audit_manifest.json').read_text());plan=json.loads((N.OUT/'plan.json').read_text())
    original_hash=plan.pop('plan_sha256')
    assert hashlib.sha256(json.dumps(plan,ensure_ascii=False,sort_keys=True).encode()).hexdigest()==original_hash
    assert audit['subqueries']<=576 and audit['review_agreement']==audit['reviews']
    assert audit['validated_pairs']==6 and audit['feature_max_abs_diff']==0 and audit['independent_replays']==18
    rows=pd.read_csv(N.OUT/'queries_with_repairs.csv',dtype={'pattern':str})
    final=pd.read_csv(N.OUT/'final_outcomes.csv');attached=pd.read_csv(N.OUT/'proven_boundary_attachments.csv')
    proofs=[];payload=[]
    context=json.loads((N.OUT/'aligned_context.json').read_text())
    for row in final[final.status=='paired_validated'].itertuples():
        i=int(row.pair_index);item=plan['selected'][i]
        a=attached[(attached.pair_index==i)&(attached.side=='source')].sort_values('slot')
        b=attached[(attached.pair_index==i)&(attached.side=='partner')].sort_values('slot')
        for slot in range(5):
            good=rows[(rows.pair_index==i)&rows.kind.isin(['fresh_boundary_equivalence','alias_equivalence'])&
                      (rows.pattern==str(slot))&(rows.status=='proved')]
            # A repaired slot must reference its final alias, not a rejected old candidate.
            name=b.iloc[slot].net
            if name!=item['mapped_nets'][slot]:good=good[good.kind=='alias_equivalence'];assert (good.partner_alias==name).any()
            proof=good.iloc[-1]
            proofs.append(dict(pair_index=i,relation_id=item['relation_id'],slot=slot,
                source_view=item['source_view'],partner_view=item['partner'],source_net=a.iloc[slot].net,partner_net=name,
                source_pin=a.iloc[slot].output_pin,partner_pin=b.iloc[slot].output_pin,
                proof_folder=proof.folder,query_id=int(proof.query_id),status='proved',phase='equal',
                context_id=context['context_id'],training_pair_allowed=False,safety_label_transfer=False))
        payload.append(dict(pair_index=i,relation_id=item['relation_id'],role=item['role'],
            source_view=item['source_view'],partner_view=item['partner'],context_id=context['context_id'],
            source_sha=N.sha(N.WORK/'trans'/(item['source_view']+'.v')),
            partner_sha=N.sha(N.WORK/'trans'/(item['partner']+'.v')),
            source_nets=a.net.tolist(),partner_nets=b.net.tolist(),complete_truth_equal=True,
            old_context_boundary_table_equal=True,full_circuit_context_equivalence_not_inferred=True,
            fresh_PO_D_equivalence=row.global_equivalence,
            feature_transfer_validated=True,training_loader_compatible=False,
            training_pair_allowed=False,safety_role_status='not_transferred_or_certified'))
    pd.DataFrame(proofs).to_csv(N.OUT/'validated_signal_pairs.csv',index=False,encoding='utf-8-sig')
    (N.OUT/'validated_pairs.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    policy=dict(accepted_for_feature_transfer='fresh source-bound five-signal equality + aligned complete tables',
        legacy_P1_proved_alone_accepted=False,same_name_alone_accepted=False,
        global_CEC_inferred_from_boundary_equality=False,context_compatible_only_with=context['context_id'],
        original_legacy_context_globally_equivalent=False,old_boundary_summary_checked_only_on_six_pairs=True,
        old_40_training_features_overwritten=False,training_approved=False)
    (N.OUT/'pair_acceptance_policy.json').write_text(json.dumps(policy,indent=2),encoding='utf-8')
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    report=f'''# 第十轮：盲边界查询上下文对齐与同源跨实现配对

更新时间：{now}。训练0次，未评估测试集，未增加原40条以外的目标。先审计40条，再按证据可用性和固定hash冻结8条（train4/val4）；只在这8条内部做受限别名修复。新增460个SAT子查询，低于576上限。

## 结论

**本轮补齐并验证6/40条关系，train4、val2；不是全部40条已完成。** 五个边界位置逐项重新证明，共30个信号对应；每对两侧完整16模式×2 prove枚举，特征和逐输入统计差异均0。6个成功关系有6种不同特征组合，不再只是第九轮保留MUX样例的单一组合。

尚余：24条已有候选但本轮未求解；8条缺少完整五信号候选；2条试点中没有可用的局部同bit别名。未冒充已完成，也未为补数字扩大成全网搜索。

## 1. 对齐的上下文

统一使用native_unrestricted_combinational_physical_Q_v1：同一源实例、相同PI位、同名物理寄存器Q为共享自由状态，QN为Q互补；不加reset/test_mode/test_se运行模式限制。两侧PI、寄存器状态及观察端schema先核对，再进行新证明。源文件及raw快照均绑定SHA256。

这与第八轮带正常运行模式限制的机制案例分开。对于原40条的legacy cellmap/seq1上下文，本轮没有直接假定其与native整体等价：6个成功关系在native下重做原侧完整枚举，再与历史边界表比较，6/6完全一致。结论仅是这6条边界摘要的迁移一致，不是证明所有legacy电路模型与真实硬件或native模型全局等价。

始终是组合状态边界抽象；无复位可达性、自然协议触发或完整时序CEC结论。物理D比较不自动包含异步reset和扫描下一状态语义。

## 2. 配对方法与可靠对应

先从旧P1的630k proved和现存声明寻找候选；旧证明缺源快照/状态语义充分绑定，不能直接复用成最终证明。同名网也仅是候选。

冻结试点后逐一重证四个cut信号和目标在共享PI/Q环境下相同。源位置顺序保留到另一实现；不依赖真值签名相似来推断相等，也不从对应复制安全标签或整单元hidden embedding。

初次8条中2条直接成功。失败位置仅允许从源JSON中与原信号同bit、且在冻结partner里存在的名字选替代；原名优先再固定hash，每位置最多2个名字、修复查询最多24。本次实际6问，修复4条；未引入新源关系、新目标、新实现或仿真全网扫描。alias_repair_plan在新增修复查询前保存。

最终6对如下：

| 原关系 | 划分 | 另一实现 | 边界迁移 |\n|---|---|---|---|
'''
    for p in payload:
        report+=f'|{p["relation_id"]}|{p["role"]}|{p["partner_view"]}|完整表及18维特征一致|\n'
    report+='''
validated_signal_pairs.csv给出30个位置的最终alias、输出pin、证明目录与query_id。54/60条边界端点记录映射到真实门节点，另6条是实际PI锚（xmit_dataH[3]、TM1、g3230，双侧各一），没有人为创建驱动门或算成映射失败。

## 3. 发现的旧候选风险

初次候选共16个信号位置被反例拒绝，其中12个来自旧P1 proved候选、4个仅同名。拒绝的是“这些源快照、同PI/物理Q自由状态下的组合相等”，不能直接反推旧归纳/undef语义下的全部P1结果错误。

但这些候选绝不能不经语义对齐直接用于新的特征迁移或一致性监督。rejected_candidates.csv完整保留候选、来源及反例，原node_pairs_sat_node.csv未篡改；pair_acceptance_policy明确禁止直接信任旧proved或同名。6个初次失败关系各取一个反例独立三值回放，全部确认当前上下文中输出不同。

完整PO/物理D比较有2次5秒超时（unknown）：其中1条最终五信号和完整边界表已验证，仍不能写成该实例全局CEC新通过。所有成功配对的五个边界信号都有确定proved，完整枚举也无unknown。

## 4. 结果、预算与局限

- 原试点：48个跨实现证明查询+128个表查询+16个独立复核=192。
- 别名修复：6个证明+256个表查询+6个独立复核=268。
- 合计460：197 proved、261 refuted、2 unknown；refuted对等价问题表示有反例，对表查询表示反对某个强制值，不能一概视为实验失败。
- 22/22独立进程复核一致；18个独立三值回放通过（6个错误候选反例+成功配对两侧各1个可行表见证）。原始模型、脚本、日志哈希全部匹配。
- 8项回归检查覆盖位序、逻辑别名、无模式限制、X不强制0、Q/QN互补、错误位宽和未知原语拒绝。
- paired_features.npz保存6×18的双侧诊断特征，范围[0,1]，最大差异0；保留上下文和证明资格，不写入训练loader，不覆盖原40条全图特征。

这验证的是“在信号对应和查询上下文都正确时，边界表示能稳定迁移”。信号点态等价本来就要求完整关系表一致，因此这是表示/映射正确性的核验，不是独立的木马检测泛化或训练增益证明。试点按可用证明选择，不能将6/8成功率外推到所有实例。

本轮已有首批来自盲提取关系的迁移正证据，不再仅依赖指定机制样例；但6/40和2个val对仍不足以宣称正式训练已具备全部条件。后续优先分批验证余24个候选；8个缺信号和2个无局部alias的记录需单独处理可靠映射，不能靠增大covered或直接沿用旧P1填补。

## 5. 产物

目录：tables/sat_pair_round10。

- pair_inventory_40.csv、plan.json、alias_repair_plan.json：40条清单及冻结试点/修复范围。
- aligned_context.json、all_aligned_tables.json、paired_features.npz：统一语义下的完整表与诊断特征。
- validated_pairs.json、validated_signal_pairs.csv、proven_boundary_attachments.csv：6个同源配对、30个证明与图/PI落点。
- pair_coverage_40.csv、final_outcomes.csv：所有40条当前状态，不隐藏未完成项。
- rejected_candidates.csv、independent_replays.csv、queries_with_repairs.csv：错误候选、回放及460查询账本。
- audit_manifest.json、pair_acceptance_policy.json：核验及防误用规则。

求解代码_p0pilot/round10_20261025/inventory.py、native.py、run_pilot.py、repair_aliases.py；只读重审已有结果可运行audit.py和publish.py，回归检查运行test_context.py。不要为了看报告重跑求解；求解器拒绝覆盖已有证据。
'''
    backed(DOC/'SAT第十轮_上下文对齐与盲关系配对_20261025j.md',report)
    section=f'''\n\n<!-- sat_pair_round10:start -->
## 20. 第十轮：查询上下文对齐及盲关系配对（未训练）

更新时间：{now}。详见[SAT第十轮_上下文对齐与盲关系配对_20261025j.md](SAT第十轮_上下文对齐与盲关系配对_20261025j.md)。

- 审计40条，32条有完整候选；冻结8条train/val各4。源关系不增加，受限同bit alias修复后6/40成功（train4/val2），其余24候选待验证、8缺边界、2局部alias不可用。
- 统一到无模式限制、共享PI/物理Q的native组合上下文。6条原侧重新枚举与历史表相同，双侧完整表、18维特征及逐输入统计均一致；6种不同特征组合。仅验证所选边界摘要迁移，未证明legacy/native整体模型等价。
- 30个源快照绑定的新信号证明，54门节点落点+6真实PI锚；不复制安全标签、不自动建立整单元embedding一致性。
- 12个旧P1 proved候选、4个同名候选在当前上下文被反例拒绝，保留隔离记录，不篡改旧表或以它们填配对。完整PO/D比较2次unknown，未冒充CEC通过。
- 共460 SAT子查询，22独立复核全一致、18独立回放通过、8回归检查通过。未训练、未评估测试集，未覆盖旧训练特征。
- 已获得首批盲边界迁移正证据，但40条尚未全部补齐，当前仅诊断特征；后续分批验证其余候选，不宣称检测增益或全面可迁移。
<!-- sat_pair_round10:end -->\n'''
    for name in ['SAT作用证明.md','SAT工作总结.md','10.22完成情况_第七轮证据审计.md']:
        p=DOC/name;text=p.read_text(encoding='utf-8')
        if '<!-- sat_pair_round10:start -->' not in text:backed(p,text+section)
    index=N.ROOT/'10.15/99_共用资产/repro/index.csv';b=index.with_name(index.name+'.bak_round10_20261025')
    if not b.exists():shutil.copy2(index,b)
    with index.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;ids={r.get('id') for r in reader}
    if 'sat_pair_round10_20261025' not in ids:
        with index.open('a',encoding='utf-8',newline='') as f:
            csv.DictWriter(f,fieldnames=fields).writerow(dict(kind='audit',id='sat_pair_round10_20261025',path=str(N.OUT.relative_to(N.ROOT)),seed='',
                config='_p0pilot/round10_20261025',note='6/40 paired; 460 subqueries; 22/22 reviews; 18 replays; no training; contexts aligned'))
    (N.OUT/'provenance.json').write_text(json.dumps(dict(plan_sha256=original_hash,
        source_code_sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        output_sha={p.name:N.sha(p) for p in N.OUT.iterdir() if p.is_file() and p.name!='provenance.json'},training_runs=0),indent=2),encoding='utf-8')
    print('Round10 report, validated-pair registry, SAT summaries and repro updated.',flush=True)


if __name__=='__main__':main()
