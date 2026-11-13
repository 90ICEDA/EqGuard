"""Finalize audited artifacts and append honest progress notes; no training."""
import os,json,csv,hashlib,datetime,re,ctypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;PRE=H.parent/'round29_20261029';OUT=ROOT/'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2';V=H/'validation'
def stamp():return datetime.datetime.now().astimezone().isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    done=json.loads((OUT/'COMPLETE.json').read_text());validation=json.loads((V/'final_validation.json').read_text());assert validation['passed']
    before=json.loads((PRE/'encoding_error_audit_v2/source_bindings.json').read_text())
    unchanged={p:sha(ROOT/p)==h for p,h in before['hashes'].items()};assert all(unchanged.values())
    oldlaunch=json.loads((H.parent/'round27_20261027/resume_runs/run_00000/launch.json').read_text());old_success={r['path']:sha(ROOT/r['path'])==r['sha256'] for r in oldlaunch['old_success_samples']};assert all(old_success.values())
    baseline=json.loads((V/'resume_batch_baseline.json').read_text());partial={r['path']:sha(ROOT/r['path'])==r['sha256'] for r in baseline['successful_files']};assert all(partial.values())
    logpath=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_alltrain_round27/runs/run_00002/s35932t200__injalpha_d1_s42__ys_nand.log'
    log=logpath.read_text(encoding='utf-8',errors='replace') if logpath.exists() else ''
    reused=re.findall(r'\[EVIDENCE\] reused (.*)',log);solved=re.findall(r'\[EVIDENCE\] solved (.*)',log)
    reuse=dict(time=stamp(),production_source_hashes_unchanged=unchanged,old_success_sample_hashes_unchanged=old_success,interrupted_view_old_success_batches=len(partial),old_success_batches_unchanged=all(partial.values()),restart_reused_batches_observed=len(reused),restart_solved_batches_observed=len(solved),log_path=str(logpath.relative_to(ROOT)),restart_preserved_log='run_00001 result_0008.json rc=3221225786 and attempt_00000 evidence retained',new_training_runs=0)
    write(V/'preservation_and_resume_check.json',reuse)
    consumption=dict(time=stamp(),contract=done['contract'],verified=True,validation_report=str((V/'final_validation.json').relative_to(ROOT)),original_feature_file='features39_v2.npy',original_shape=[done['nodes'],39],virtual_feature_file='virtual_features39_v2.npy',virtual_shape=[done['virtual_nodes'],39],graph_shape=[done['total_graph_nodes'],39],input_formula='concatenate original features then virtual features on axis 0; no standardization fitted in this round',directed_edge_file='edge_index_directed_v2.npy',edge_shape=[2,done['edges']],edge_roles_file='edge_roles_v2.npy',virtual_node_map='virtual_node_map.jsonl',original_ids='All original global ids 0..3220145 unchanged',virtual_ids=f"{done['nodes']}..{done['total_graph_nodes']-1}",virtual_supervision='unknown: all training/validation/test supervision masks false; never assign trusted negative labels',SAT_attachment='Existing real SAT rows attach only to unchanged original cell ids; append zero content and covered=0 on virtual rows; do not reinterpret covered=0 as proved absence',split_contract='Use frozen 388-view split; the original 3071-node unlisted view remains excluded; virtual context inherits its source view but has no label',feature_semantics='Columns 31/32/35/36 intentionally remain exactly-two-step; unreachable distance=-1; constants are not primary inputs',region_contract='No region or old cache changed; future directed regions need separate validation and hash binding',source_contract_sha=sha(OUT/'contract.json'),completion_manifest_sha=sha(OUT/'COMPLETE.json'),loader_integrated=False,training_started=False)
    write(OUT/'CONSUMPTION_CONTRACT.json',consumption)
    unit=json.loads((V/'unit_results.json').read_text());independent=validation['independent_yosys'];newparses=sum(r['raw_origin']=='new_readonly_verilog_parse' for r in independent)
    changes=done['changes_by_column'];report=f'''# 第三十轮 PI PO别名修复与SAT恢复

完成时间 {stamp()}。本轮生成独立v2输入并核验，恢复原合同SAT补跑，没有启动训练或模型前向。没有删除、移动或覆写现有图、旧特征、SAT成功证据与失败日志。

## 独立v2产物

路径：`{OUT.relative_to(ROOT)}`。

- 原有单元 {done['nodes']:,} 个，389视图，全部保持原全局ID及按视图排列的单元名。
- 连续assign中的实际运算单独显式化为 {done['virtual_nodes']:,} 个辅助节点；附加ID从{done['nodes']}开始。原有单元特征与辅助特征分开存盘；完整有向图共{done['total_graph_nodes']:,}节点、{done['edges']:,}条边。
- `features39_v2.npy`：原有节点的39维修正特征；`virtual_features39_v2.npy`：辅助节点特征；`edge_index_directed_v2.npy`：完整图有向边；`edge_roles_v2.npy`：数据、时钟、扫描、复位及使能等边角色位掩码；`virtual_node_map.jsonl`：辅助节点与源表达式。
- `CONSUMPTION_CONTRACT.json`明确读取顺序、形状、ID、标签与SAT附着合同。旧训练加载器尚未接入，未以新输入训练；辅助节点没有可信标签或SAT证据，不能当成可信负例。既有3071个未列入正式划分的节点仍不进入监督集合。

修复采用按位别名等价类，PI/PO声明与单元连接使用同一归一化；处理向量拼接、位选、区间方向与长别名链。连续布尔运算和MUX不再被当作普通别名删除。Q与QN保持独立信号，不按名称合并。

## 验证结果

全量核对特征有限值、一热完整性、原始ID和单元顺序、输出和源文件哈希、每视图缓存与全局数组一致性、边角色与图边界、无跨视图边，全部通过。原有门类型和输入端口列0至25完全保留；旧graph、旧parser、训练脚本和区域函数哈希或冻结文件stat均未变化。

另以独立Yosys解析核对5个宿主、4种配方中的固定木马与正常对照，共{validation['independent_views']}视图、{validation['independent_nodes']:,}个原有节点；有向边、全部39列和连续运算的输入端操作数均一致。优先复用已绑定raw快照；缺少的{newparses}个参考只调用read_verilog/hierarchy/proc/write_json，没有sat命令或搜索。单元验证共{len(unit['cases'])}项，包含30张随机图的恰好两跳参考检查，均通过。

原有节点中{done['changed_any_node']:,}个至少一列变化。第27列PI标记变化{changes[27]:,}个，第28列PO标记变化{changes[28]:,}个，第29列PI距离变化{changes[29]:,}个，第30列PO距离变化{changes[30]:,}个。变化包括边界修复、按位连接修复和补回连续逻辑的影响，不能全部归为单一bug。第31/32/35/36列保持恰好两步语义，没有默默改成两跳以内。所有新距离均为原始值，未拟合归一化。

早期两个未完成构建目录仍保留且没有COMPLETE标记：`bitwise_alias_20261029`和`bitwise_alias_20261029_v1`。唯一经过本轮全量验证的交付为`bitwise_alias_20261029_v2`。新构建曾遇到Windows短时文件共享拒绝，已对状态原子替换加入有限重试，并从完成缓存续建，没有重算已完成特征。

## SAT退出原因与恢复

旧run_00001最后一项返回3221225786，即0xC000013A。Windows本机ntdll对该状态的消息为“使用CTRL+C终止应用程序”。因此可确认是控制中断退出；现有记录无法确认中断发起者，不能归因于某个用户操作、工具或内存不足。对应时段没有检出Python应用崩溃或资源耗尽事件；Windows未重启。失败批次及日志原样保留。

恢复通过Win32_Process.Create启动隐藏后台总控，由WmiPrvSE服务创建，避免依附当前终端；总控及阶段包装忽略SIGINT/SIGBREAK，stdin接DEVNULL。原STOP文件、内存和磁盘保护仍有效。管线按训练补跑、严格收尾审计、验证和测试补齐顺序执行；初始1路、上限2路。已有成功视图先严格校验后跳过，未完成视图按绑定的模型、脚本、源文件和日志重放成功批次，只有未完成或无有效证据的批次另建attempt。

本轮启动记录在`_p0pilot/round29_20261029/durable_runs/run_00000`，总控由WMI父进程创建已核实。原冻结SAT提取器、查询语义与既有图未改动；收尾阶段使用独立安全副本，将重试并发限制在1至2路，不更改求解合同。后台管线尚未全部完成，不能把恢复运行表述为全量提取完成。

校验旧成功样本4个及中断网表原117个成功批次，哈希均未变化。当前观察到中断网表重放{len(reused)}批、产生新求解{len(solved)}批，详见`preservation_and_resume_check.json`；若仍为0，表示快照时恢复队列尚未调度到该视图，应在它开始后补验。旧中断批次03744没有结果及执行完成标记，重试该批不属于重复计算已验证成功批次。

## 下一步

待原SAT后台收尾后，先按新读取合同接入v2图并验证辅助节点监督屏蔽、原SAT坐标附着、归一化和有向区域，再准备同预算的v1/v2及真实SAT/置换对照。当前没有检测增益结论，也没有启动训练。
'''
    (H/'第三十轮_别名与向量修复及SAT恢复.md').write_text(report,encoding='utf-8')
    note=f'''\n\n### 第三十轮 PI PO别名与向量拼接修复及SAT恢复 {stamp()}

已生成独立v2输入，389视图、原有3220146节点ID不变，新增1829个连续运算辅助节点，完整有向图5060187边。按位别名与主端口同步；保留恰好两跳合同。全量坐标、哈希和无跨视图边检查通过；40个固定木马及正常对照视图、423173节点与独立Yosys解析的有向边、39列及表达式操作数一致，未运行SAT验证命令或训练。辅助节点没有可信标签和SAT覆盖；新输入尚未接入旧训练加载器。旧图与旧成功证据保留。

SAT旧退出码0xC000013A经本机ntdll确认是CTRL+C类控制中断，发起者无法确定。已由WMI服务独立创建后台总控，阶段包装隔离终端控制中断，保留资源/STOP保护；按原合同复用成功视图和批次补跑，后接严格审计及验证测试补齐。已有4个旧成功样本与中断网表117个成功批次哈希不变。全量后台尚未完成，详见实时日志，不声称已完成全量提取。

v2交付：`{OUT.relative_to(ROOT)}`；报告：`_p0pilot/round30_20261029/第三十轮_别名与向量修复及SAT恢复.md`；后台：`_p0pilot/round29_20261029/durable_runs/run_00000`。未删除或移动文件，未训练。
'''
    marker='### 第三十轮 PI PO别名与向量拼接修复及SAT恢复'
    for name in ['SAT作用证明.md','SAT工作总结.md']:
        p=ROOT/'10.15/00_说明'/name
        if marker not in p.read_text(encoding='utf-8'):
            with p.open('a',encoding='utf-8') as f:f.write(note)
    registry=ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv'
    if '第三十轮 PI PO修复与SAT恢复' not in registry.read_text(encoding='utf-8-sig'):
        with registry.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([stamp(),'第三十轮 PI PO修复与SAT恢复','build_v2_features.py; validate_v2_features.py; WMI sat_durable_supervisor.py','v2 standalone; original ids; no training','--','hosts_bt31',done['contract'],str(OUT.relative_to(ROOT)),'389views/3220146cells/1829aux/5060187edges; 40 independent references PASS','v2完成；SAT后台恢复中','previous SAT control interrupt 0xC000013A; initiator unknown'])
    print(json.dumps(dict(report=str(H/'第三十轮_别名与向量修复及SAT恢复.md'),reused_batches=len(reused),new_solved=len(solved),all_preservation_checks=True),ensure_ascii=False))
if __name__=='__main__':main()
