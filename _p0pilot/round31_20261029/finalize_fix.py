import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
now=datetime.now().astimezone().isoformat()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
v=json.loads((HERE/'verification.json').read_text());assert v['passed']
approval=ROOT/'_p0pilot/round29_20261029/acceleration_approval.json'
shutil.copy2(approval,HERE/'acceleration_approval.before.json')
a=json.loads(approval.read_text())
key=next(k for k in a['support_files'] if k.endswith('k4_fast_support.py'))
assert a['support_files'][key]==v['old_sha']
a['support_files'][key]=v['new_sha']
a['constant_lexer_correction']=dict(time=now,previous_support_sha=v['old_sha'],
    corrected_support_sha=v['new_sha'],offline_evidence=str((HERE/'verification.json').relative_to(ROOT)),
    exhaustive_fixture_output_comparisons=20,new_solver_calls=0,
    note='Original 18 miter cases are historical; this correction was validated offline, not by new SAT proofs.')
write(approval,a)
# Keep old live-state records before marking them paused; no scheduler is launched.
for base in ('durable_runs/run_00000','queue_runs/run_00001'):
    p=ROOT/'_p0pilot/round29_20261029'/base/'state.json'
    shutil.copy2(p,HERE/(base.split('/')[0]+'_state.before.json'))
    state=json.loads(p.read_text());state.update(time=now,phase='paused_by_user',
        pause_reason='Stop SAT, fix constant dependency parsing, await later resumption',
        paused_processes_terminated=True)
    write(p,state)
run=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_validation_round29/runs/run_00000'
(run/'STOP').write_text('User requested pause; existing successful batches retained. '+now,encoding='utf-8')
failed=[]
for p in run.glob('result_*.json'):
    r=json.loads(p.read_text())
    if not r.get('verified_complete'):failed.append(r['view'])
affected=sum(x['old_failure_batches'] for x in v['views_detail'])
text=f'''# 第三十一轮：SAT常量依赖解析修复与暂停

时间：{now}。

按用户要求停止后台supervisor、队列、协调器、worker及其求解子进程；停止后检查WSL无yosys进程。不重启SAT、不训练、不删除或移动任何文件。被中断的最后批次保留为未完成尝试，后续可重试，不能算成功批次重算。

根因：k4_fast_support.compile_logic旧正则 `\\bb(\\d+)\\b` 会把Verilog常量 `1'b0` / `1'b1` 中的b0/b1识别成依赖节点0/1。原始native模型未驱动这些虚构节点，COI闭包因此抛错。不是证实源网表存在未驱动信号。

修复：只把独立b数字标识符识别为信号，排除单引号前缀；保留真实未驱动依赖的报错。原始native上下文、cut、查询、超时、节点坐标不变。旧脚本及旧hash许可文件保存在本轮目录。

离线验证：20项全模型/裁剪模型的穷举输出比较通过；真实未驱动节点仍拒绝。全部{v['views']}份已取得且绑定正确的验证集raw快照，生成{v['generated_batches']}个批次模型，均不再产生虚构依赖错误；其中{affected}个批次可复现旧错误。核对{v['existing_models_identical']}个已有成功模型，重新生成后字节一致，模型/日志哈希与结果记录匹配，结果文件前后哈希不变。未准备快照的视图不在此验证范围；没有追加SAT求解，因此新失败批次的最终SAT结果仍待补跑。

验证集已有{len(failed)}个返回失败的视图；暂停时另外1个视图尚未完成。训练集259/259已完成提取及收尾审计，验证集15/65完整视图，测试集0/64。此前自动说明“全量完成”指训练集，并非三个划分全部完成。

恢复准备：已同步加速支持文件的hash校验记录，并保留修复前记录及历史18项形式miter证据的适用范围说明。恢复时继续原冻结划分，先复用成功批次，仅重试失败/未完成批次；不使用旧state的PID认定任务存活。当前保持暂停，尚未补跑。

证据：verification.json、verification.log、evidence_baseline.json、test_constant_dependencies.py、processes_before_stop.json。本轮新增SAT调用0、训练0。
'''
(HERE/'第三十一轮_SAT常量依赖错误修复.md').write_text(text,encoding='utf-8')
for name in ('SAT作用证明.md','SAT工作总结.md'):
    with (ROOT/'10.15/00_说明'/name).open('a',encoding='utf-8') as f:
        f.write('\n\n'+text.replace('# 第三十一轮','### 第三十一轮',1))
with (ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:
    csv.writer(f).writerow([now,'第三十一轮 SAT常量依赖修复与暂停','verify_constant_fix.py; test_constant_dependencies.py',
        'offline only; solver0; training0','--','frozen validation; no label selection','native_Q unchanged',
        str(HERE.relative_to(ROOT)),f"{v['views']}raw/{v['generated_batches']}batches/{v['existing_models_identical']}existing models PASS",
        '已修复；按用户要求暂停','old files/logs retained; hash contract updated'])
print(text)
