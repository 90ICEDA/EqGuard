"""Validate/publish round8; append corrections, retain all earlier evidence."""
import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'10.15/00_说明'
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_cases_round8'


def backup_write(path,text):
    if path.exists():
        b=path.with_name(path.name+'.bak_round8_20261025')
        if not b.exists():shutil.copy2(path,b)
    path.write_text(text,encoding='utf-8')


def main():
    q=pd.concat([pd.read_csv(OUT/f,dtype={'pattern':str}) for f in
                 ['queries.csv','large_host_queries.csv','review_queries.csv','boundary_queries.csv']],ignore_index=True)
    assert len(q)==152 and set(q.status)=={'proved','refuted'}
    errors=[]
    for r in q.itertuples():
        folder=ROOT/r.folder
        if hashlib.sha256((folder/'model.v').read_bytes()).hexdigest()!=r.model_sha:errors.append('model:'+r.folder)
        script=(folder/'run.ys').read_text(encoding='utf-8')
        if hashlib.sha256(script.encode()).hexdigest()!=r.script_sha:errors.append('script:'+r.folder)
        if hashlib.sha256((folder/'run.log').read_bytes()).hexdigest()!=r.log_sha:errors.append('log:'+r.folder)
        if r.status=='refuted' and (pd.isna(r.witness) or not (ROOT/r.witness).exists()):errors.append('witness:'+r.folder)
    assert not errors
    local=q[q.kind=='local_truth']
    truth=[]
    for (view,pat),g in local.groupby(['view','pattern']):
        st=g.set_index('prove').status.to_dict()
        assert set(st)=={0,1}
        forced=0 if st[0]=='proved' and st[1]=='refuted' else 1 if st[1]=='proved' and st[0]=='refuted' else None
        assert forced is not None
        expected=int(not all(c=='1' for c in pat)) if view.startswith('s38417') else int(pat[2] if pat[0]=='1' else pat[1])
        assert forced==expected
        truth.append(dict(view=view,pattern=pat,feasible=1,forced=forced,
                          function='NAND3' if view.startswith('s38417') else 'MUX(S,A,B)'))
    pd.DataFrame(truth).to_csv(OUT/'functional_relations.csv',index=False,encoding='utf-8-sig')
    correspondence=pd.read_csv(OUT/'signal_correspondence.csv')
    assert (correspondence.status=='proved').all()
    for inst in ('injalpha','injepsilon'):
        a=[r['forced'] for r in truth if r['view']==f'rs232t1000__{inst}_d1_s42__ys_id']
        b=[r['forced'] for r in truth if r['view']==f'rs232t1000__{inst}_d1_s42__ys_abc']
        assert a==b
    edges=[]
    for inst,prefix in [('injalpha','TrojanA'),('injepsilon','TrojanE')]:
        for recipe in ('ys_id','ys_abc'):
            view=f'rs232t1000__{inst}_d1_s42__{recipe}'
            for pin in ['S0','A','B']:
                edges.append(dict(view=view,source=prefix+'HJ.'+pin,target=prefix+'HJ.Y',
                    relation='conditional_mux_function',status='proved_all_8_patterns',evidence='queries.csv/local_truth'))
            edges.append(dict(view=view,source=prefix+'HJ.Y',target='rec_readyH',relation='same_bit_alias',status='raw_JSON_bit_identity',evidence=view+'/raw.json'))
    pd.DataFrame(edges).to_csv(OUT/'functional_graph_edges.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame([dict(instance=inst,role=role,safety_label='not_transferred',evidence='native inserted source + functional checks')
                  for inst in ('injalpha','injepsilon') for role in ('inserted_control','payload_boundary','modified_host_output')]).to_csv(OUT/'case_role_scope.csv',index=False,encoding='utf-8-sig')
    source_rows=[]
    for host,inst in [('rs232t1000','injalpha'),('rs232t1000','injepsilon'),('s38417t100','injalpha')]:
        p=ROOT/f'generate_trans/hosts_bt/{host}/{host}__{inst}_d1_s42.v'
        relevant=[dict(line=i+1,text=s) for i,s in enumerate(p.read_text().splitlines()) if 'TrojanAHJ (' in s or 'TrojanEHJ (' in s or 'TrojanAT1 (' in s or 'TrojanETM' in s]
        source_rows.append(dict(source=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),inserted_source_lines=relevant))
    (OUT/'insertion_source_evidence.json').write_text(json.dumps(source_rows,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=dict(sat_subqueries=152,solver_batches=q.folder.nunique(),query_status=q.status.value_counts().to_dict(),
        new_cross_implementation_proofs=12,independent_process_review=14,independent_process_agreement=14,
        independent_replays=20,source_bound_local_patterns=40,training_runs=0,test_evaluated=False,
        script_log_model_hash_errors=errors,regression_tests=5,
        semantics='combinational physical-Q state boundary; no reset/protocol reachability; fixed-boundary and global-wire interventions separated',
        preparation_invocations_including_preflight_retries=7,
        code_sha256=hashlib.sha256((ROOT/'_p0pilot/round8_20261025/case_chain.py').read_bytes()).hexdigest())
    (OUT/'validation_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    report=f'''# 第八轮：两例功能链、共享环境干预与跨实现对应

完成时间：{now}。训练0次，未评估测试集。152个SAT子查询、25个求解批次；另7次结构准备调用（含两次在求解前拒绝不支持原语后的适配重试），总Yosys调用32。所有预算均≤192，CPU使用ginvenv。14个独立进程复核全部一致，20个正向/反例见证独立Boolean回放通过，5个回归检查通过。

## 已完成

- rs232t1000的injalpha、injepsilon：各ys_id/ys_abc，四个真实源文件均记录SHA256，逐个新解析；每设计58个有名物理寄存器Q作为自由状态，同一PI/状态明确共享。没有用按网名相同代替功能证明。
- 每设计8个(S,A,B)模式全部可行，16个查询验证全部强制值符合MUX；共32个模式。模式附加sys_rst_l=1、test_mode=0、test_se=0，只是运行模式约束，不能称完整UART合法协议。
- 四个设计、控制值0/1均有同一环境的原电路可行赋值，干预后rec_readyH改变，共8个共享环境见证。另两个ys_id的A=B反例也独立回放，解释共享别名导致的额外影响。
- 固定自然A/B、只翻转功能边界S：8个正向见证、8个A=B阻断证明全部成立。target和rec_readyH在本案例是同一个bit，明确写为端点别名，不虚构额外下游门。
- 两例各5个信号(control/A/B/target/rec_readyH)逐项跨实现证明，加各1个全PO及物理D引脚的组合等价证明，共12个新证明。对应使用同名物理Q状态和同PI位；这不是重新完成所有初态/时钟/复位条件下的时序CEC。旧CEC PASS只是辅助记录，没有冒充当前源哈希绑定的证明。
- 大宿主s38417t100/injalpha/ys_id：1564个寄存器状态，真实劫持函数是NAND3，不能套rs232的MUX接口。8模式全可行；两个控制方向均有端点g5629变化见证；A=0的两个阻断上下文均可行且被证明阻断。大宿主没有新做跨实现对应，不能称第三案例跨实现闭环。

## 一个关键修正：内部网线故障与功能边界干预不同

在两个rs232的ys_id中，自然S=0、A=B=0时，全局把S网线强制为1还会使B从0变为1，于是输出变化。两个ys_abc在相同自然A=B约束下则阻断。这不否定自然功能等价：同名自然信号的函数相同，不保证其全局物理干预范围相同。

若保持自然A/B不变，只在已验证MUX功能边界替换选择端，四个设计均得到相同的变化/阻断规律。因此跨实现学习应对齐明确功能边界和角色，不能把全局内部故障可观测性当作天然不变量。此结论来自10个全局网线变化见证（含大宿主）+2个反例回放，以及8个固定边界回放，不是由AP变化推断。

## 图数据

functional_graph_edges.csv对应四个实际网表的控制/数据输入→目标→PO别名；每条边标明验证状态。以下为单例实际关系模板（两例分别使用TrojanAHJ和TrojanEHJ）。它是功能关系图，不是门级改写或风险预测图。

```mermaid
flowchart LR
  S[HJ.S0: 已验证控制] -->|8模式MUX关系| Y[HJ.Y]
  A[HJ.A: 自然数据边界] --> Y
  B[HJ.B: 自然载荷边界] --> Y
  Y -->|原始JSON同一bit| PO[rec_readyH: 顶层PO]
```

## 语义与完成边界

只证明组合状态边界、模式条件下的函数和干预；所有寄存器Q任意且对应，QN取互补。未证明复位可达、自然时序触发、UART协议完整合法性；自由状态不能冒充可达状态。模型不展开扫描/异步复位时序，不用旧async reset近似声称真实复位。源插入代码的控制/载荷/修改输出角色已留证，但不向对应节点复制Trojan标签，机制案例不自动进入盲提取训练集。

P0指定两例现在具备组合语义闭环及大宿主单实现验证；P0全语义仍有自然触发/可达性缺项。P1只补齐两例选定功能边界的对应，非全体节点或四类安全角色闭环。P2/P3/P4/P5不因此完成。两份总结及10.22审计已追加本轮状态，旧5行consistent=0表保留历史，不混写分母。

下一阶段应把“带上下文的边界关系”表示成可迁移的节点/区域注释，再做train/val无标签候选映射审计；暂不开展长训练或继续随机扩关系。已知两例MUX/NAND3本身并非超出门类型的新信息，本轮价值是完整约束、见证和对应语义，不能宣称已经证明SAT带来训练增益。

## 产物与复现

表目录tables/sat_cases_round8包含sources.csv、queries.csv、large_host_queries.csv、review_queries.csv、boundary_queries.csv、functional_relations.csv、signal_correspondence.csv、all_independent_replays.csv、boundary_replays.csv、functional_graph_edges.csv、case_role_scope.csv、insertion_source_evidence.json和各查询模型/脚本/日志。validation_manifest.json核对152个查询全部哈希及反例模型。

脚本_p0pilot/round8_20261025：case_chain.py、validate_extra.py、boundary_intervention.py、test_case_chain.py、publish.py。阅读已有结果只需publish.py；不要为查看报告重跑SAT。重新运行求解前应建立新执行目录，保留原证据。发布器不写模型参数或训练特征。
'''
    backup_write(DOC/'SAT第八轮_两例功能链与对应_20261025h.md',report)
    sec=f'''\n\n<!-- sat_cases_round8:start -->
## 18. 第八轮：两例功能链和跨实现对应（未训练）

更新时间：{now}。详见[SAT第八轮_两例功能链与对应_20261025h.md](SAT第八轮_两例功能链与对应_20261025h.md)。

- injalpha/injepsilon各ys_id/ys_abc：32个模式全可行且MUX强制值一致；12个跨实现新证明（10个选定信号+2个全PO/物理D组合比较）。共享同名物理Q和同PI，不是完整时序CEC。
- 8个共享环境全局控制干预见证；发现两个ys_id中自然A=B仍可因干预改变B而传播，不能把物理网线干预当作跨实现不变量。固定A/B功能边界后，8变化见证和8阻断证明在四实现一致。
- s38417/injalpha单实现按真实NAND3验证，2方向传播和2可行阻断；未声称大宿主跨实现闭环。
- 共152SAT子查询，25求解批次；14独立复核全一致、20独立回放、5回归检查；0训练，未评估测试。
- P0组合语义两例闭环，P1选定边界对应补齐；复位可达/自然时序触发仍未证明，P2–P5未完成。插入记录案例不自动用于盲提取训练，不复制安全标签。
<!-- sat_cases_round8:end -->\n'''
    for name in ['SAT作用证明.md','SAT工作总结.md','10.22完成情况_第七轮证据审计.md']:
        p=DOC/name;s=p.read_text(encoding='utf-8')
        if '<!-- sat_cases_round8:start -->' not in s:backup_write(p,s+sec)
    p=ROOT/'10.15/99_共用资产/repro/index.csv'
    b=p.with_name(p.name+'.bak_round8_20261025')
    if not b.exists():shutil.copy2(p,b)
    with p.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;ids={r.get('id') for r in rd}
    if 'sat_cases_round8_20261025' not in ids:
        with p.open('a',encoding='utf-8',newline='') as f:
            csv.DictWriter(f,fieldnames=fields).writerow(dict(kind='audit',id='sat_cases_round8_20261025',path=str(OUT.relative_to(ROOT)),seed='',
                config='_p0pilot/round8_20261025',note='152 SAT subqueries; 14/14 review; 20 replays; two-case boundary correspondence; no training'))
    print(json.dumps(manifest,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
