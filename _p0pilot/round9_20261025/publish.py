"""Publish the offline boundary-transfer audit and update living summaries."""
import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'10.15/00_说明'
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_boundary_round9'


def write_backed(path,text):
    if path.exists():
        backup=path.with_name(path.name+'.bak_round9_20261025')
        if not backup.exists():shutil.copy2(path,backup)
    path.write_text(text,encoding='utf-8')


def main():
    m=json.loads((OUT/'manifest.json').read_text());q=json.loads((OUT/'quality_checks.json').read_text())
    assert m['sat_queries']==m['training_runs']==0
    assert q['permutation_checks']==960 and q['max_case_descriptor_difference']==0
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    expanded=pd.read_csv(OUT/'expanded_region_pairs.csv')
    report=f'''# 第九轮：功能边界表示、可靠对应与离线迁移验证

更新时间：{now}。**不新增SAT、不扩大候选、不运行GNN或训练、不评估测试集。** 全部复用第八轮两例证据和已有40条盲提取关系；CPU使用ginvenv。

## 结论

功能边界已整理成可比较、可追溯的候选表示。在两例已有证明支持的8个角色对应上，18维描述量及逐输入比较统计跨实现差异均为0；16条角色记录全部映射到图节点。它可以作为后续可迁移SAT特征的基础，但**目前不能称为已验证可用于盲提取训练的特征**，也没有证明训练增益。

主要限制：四个局部样例都保留单个MUX，只有一种特征组合；真实多门重写区域的等价已由既有根信号证明支持，但其6–17个共享输入变量尚无紧凑完整函数特征。40条盲关系没有同源跨实现配对，查询上下文也与机制样例不同；不能用样例稳定性替代全体迁移验证。

## 1. 两层边界，不能混淆

**局部功能边界**：selector/data_A/data_B→target，target与rec_readyH同bit。保存模式可行性、强制0/1、未定、不可行、查询上下文、来源哈希、原始bit和角色。两例各ys_id/ys_abc的最小区域都是单个MX2X1_RS；这类局部稳定性不是1:N重写实验。

**PI/状态边界区域**：在固定的既有角色根上向前展开，停在PI或有名物理寄存器Q；QN明确记录为同一Q的反相。复用第八轮共享PI/物理Q环境下的根等价证明，不新增求解，不从功能表相似推断证明。得到8组区域对应，其中6组为非平凡多门重写，所有区域成员均映射成功。区域可重叠，不能将成员数当作独立样本数。

| 实例 | 根角色 | ys_id门数 | ys_abc门数 | 共享边界变量数 |\n|---|---|---:|---:|---:|
'''
    for r in expanded.itertuples():
        report+=f'|{r.instance}|{r.role}|{r.cells_a}|{r.cells_b}|{r.boundary_variables}|\n'
    report+='''
这里的对应是“共同环境到根的区域函数相同”，不是内部每个门一一对应，更不是隐藏表示或安全标签相同。没有把局部MUX的18维特征复制到整片重写区域。

## 2. 候选特征与规范化

- 关系层18维全部在[0,1]：输入数、可行/强制/未定/不可行比例、可行域决定性、已强制输出中的1比例、可比较模式对覆盖率、条件变化比例、最大输入变化比例，以及明确的有效/完整/受限域/partial/unknown掩码。
- 比较覆盖率是可行且两侧都被强制的邻接模式对比例；条件变化不是共享环境因果干预证明，0必须与有效性和覆盖率一起解释。
- 真值表按输入排列规范化，签名只用于去重/比较，绝不作为有序数值输入，也不作为等价证明。40条中27条有多个同样有效的输入排列，保留全部槽位候选，不强行制造一一对应。
- 节点层把endpoint与input通道分开。端点仅贴到已验证目标驱动单元，不复制到接收DFF；输入节点只带该输入自身的可比覆盖率、变化比例及有效掩码。无可比对的输入不作为新增功能覆盖。
- 同一节点按(endpoint/input)角色独立聚合，以唯一(relation,input-index)为单位求均值；避免max聚合制造不一致组合，也避免同一DFF的Q/QN参与多个输入时被最后一条覆盖。原始bit/输出pin仍保存在审计记录，节点聚合不创建训练对应。

产物：case_descriptors.npz是四个机制边界的18维诊断量；blind_annotations_sparse.npz是132×23的节点稀疏注释（40个端点驱动、92个有效输入驱动）。不是新增132个SAT证明或新增132个覆盖节点；没有重算或宣称正例覆盖提高。该文件明确标注不兼容现有训练loader，未写全图训练特征。

## 3. 可靠对应与上下文门槛

- 8个唯一角色对（两例×selector/A/B/target）都有原始查询引用；target/PO别名不重复算一组。对应的源文件和raw JSON哈希已核对，16个角色节点映射成功。比如选择端可以从单元Q映射到另一单元QN：使用已证明的信号值关系，不能仅凭pin名称自动取反或对齐整单元embedding。
- 共同真值签名不能证明两个信号等价；信号等价也不能复制可信木马/正常标签。本轮所有训练一致性对均设为不可用，安全角色/盲提取资格未因此自动获批。
- 机制样例上下文是native组合物理Q边界，并限制sys_rst_l=1、test_mode=0、test_se=0。原40条为seq1任意初态、legacy cellmap、无该模式约束。两类上下文不可直接混合。
- 展开区域证明的上下文另列为“同PI/有名物理Q、未限制PI的组合根等价”，比机制样例运行模式更宽，但不是完整时序CEC。没有把复位可达或自然协议触发写成已完成。
- 全局内部网线干预结果保留在excluded_wire_intervention.csv，明确不进入可迁移特征。第八轮已发现该物理干预范围随实现变化，不能以它监督跨实现一致性。

## 4. 既有40条关系的离线审计

重新核验1280个既有查询：当前源文件哈希、pattern/prove、cut顺序与bit、目标、状态和查询键绑定均一致；真值表从显式(pattern,prove)重建，未依赖CSV行序。当前图的132个节点索引/名字/视图也全部核对。

40条关系产生31种描述组合；在相同driver_type、k及查询上下文下，AND、INV、MUX、OR四组仍有多个不同组合，说明这些条件统计不只是直接门类型one-hot。但它仍可能被更大范围结构解释；没有据此宣称不可由GNN学习或已能区分木马。

这40条在同一源实例上没有多种实现的边界配对，跨实现迁移验证数为0。不能把第八轮两例的8个机制角色对冒充为这40条盲关系的验证集。

## 5. 验证和下一步

12项回归检查通过：输入重编号不变性、对称歧义、partial不误判常量、不可行不误判强制0、unknown有效掩码、错误模式拒绝、上下文不匹配拒绝、功能相似不能代替证明、安全标签不复制、库输出pin白名单及有界性。

另对40条四输入关系进行960次排列验证；规范签名与描述量全部不变。8个已证明角色对的描述差异和逐输入统计差异为0；132节点特征有限且在[0,1]，未建立任何训练一致性对。

下一步应优先利用这6组真实重写区域，明确紧凑的功能摘要及可用安全角色，再在相同查询上下文下补齐已有盲边界的跨实现配对。那是下一阶段的独立决策，本轮没有开展搜索、生成新标签或启动训练。不能先把当前机制样例或无配对的40条关系接入正式训练。

## 6. 产物与复现

目录：10.15/06_统一评测协议/N4_三向泛化/tables/sat_boundary_round9/。

- boundary_records.json、contexts.json、feature_schema.json：表示与语义协议。
- proven_boundary_pairs.csv、case_graph_attachments.csv、mapped_role_pairs.csv：逐角色证明和节点落点。
- region_boundary_pairs.csv：保留单MUX的局部边界。
- expanded_region_records.json、expanded_region_pairs.csv、expanded_region_membership.csv、expanded_region_anchors.csv：共享PI/Q状态边界的真实重写区域及证明引用。
- case_descriptors.npz、blind_annotations_sparse.npz：分离的稀疏诊断量，不是训练输入。
- evidence_binding_audit.csv、driver_conditioned_information.csv、manifest.json、quality_checks.json：核验与限制。

复现均不调用SAT或训练：
```powershell
.\\ginvenv\\Scripts\\python.exe -B -X utf8 _p0pilot/round9_20261025/prepare.py
.\\ginvenv\\Scripts\\python.exe -B -X utf8 _p0pilot/round9_20261025/test_boundary_repr.py
.\\ginvenv\\Scripts\\python.exe -B -X utf8 _p0pilot/round9_20261025/verify.py
.\\ginvenv\\Scripts\\python.exe -B -X utf8 _p0pilot/round9_20261025/publish.py
```
'''
    write_backed(DOC/'SAT第九轮_功能边界与迁移表示_20261025i.md',report)
    section=f'''\n\n<!-- sat_boundary_round9:start -->
## 19. 第九轮：功能边界表示与可靠对应（离线，未训练）

更新时间：{now}。详见[SAT第九轮_功能边界与迁移表示_20261025i.md](SAT第九轮_功能边界与迁移表示_20261025i.md)。

- 0新增SAT、0候选扩展、0训练；复核1280个既有查询绑定。
- 四个局部边界的18维描述在8个已证明角色对上差异0，16条角色记录全映射；但局部区域均保留单MUX，只有一种特征组合，不能夸大迁移验证。
- 向共同PI/物理Q状态展开，整理8组根函数已有证明支持的区域对；6组真实多门重写：injalpha控制20→10、载荷43→28、目标44→30；injepsilon控制11→10、载荷35→39、目标36→41。区域成员全映射，不创建内部节点一一对应或复制标签。
- 40条盲关系有31种描述组合、27条输入排列歧义；与机制样例上下文不同且没有同源跨实现配对，故盲迁移验证0、训练一致性对0。
- 诊断注释132节点（40端点驱动+92有效输入），角色通道分开；不把整条函数复制给输入/区域全体，不把签名编号或物理网线干预作为可迁移特征。不宣称覆盖或正例改善。
- 12回归检查及960输入重编号验证通过；产物tables/sat_boundary_round9。当前是可迁移候选表示与区域对应基础，尚非可用于正式训练的增益证据。
<!-- sat_boundary_round9:end -->\n'''
    for name in ['SAT作用证明.md','SAT工作总结.md','10.22完成情况_第七轮证据审计.md']:
        p=DOC/name;text=p.read_text(encoding='utf-8')
        if '<!-- sat_boundary_round9:start -->' not in text:write_backed(p,text+section)
    provenance=dict(phase='round9_offline',new_sat_queries=0,training_runs=0,
        input_plan_sha=hashlib.sha256((OUT/'plan.json').read_bytes()).hexdigest(),
        code_sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        output_sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='provenance.json'})
    (OUT/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    index=ROOT/'10.15/99_共用资产/repro/index.csv'
    backup=index.with_name(index.name+'.bak_round9_20261025')
    if not backup.exists():shutil.copy2(index,backup)
    with index.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;ids={r.get('id') for r in reader}
    if 'sat_boundary_round9_20261025' not in ids:
        with index.open('a',encoding='utf-8',newline='') as f:
            csv.DictWriter(f,fieldnames=fields).writerow(dict(kind='audit',id='sat_boundary_round9_20261025',
                path=str(OUT.relative_to(ROOT)),seed='',config='_p0pilot/round9_20261025',
                note='offline; 1280 existing bindings; 8 role pairs; 6 rewritten regions; 960 permutations; no SAT/training'))
    print('Round9 report, SAT summaries and repro updated.',flush=True)


if __name__=='__main__':main()
