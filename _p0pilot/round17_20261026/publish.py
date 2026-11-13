"""Run CPU regressions, then publish round-17 evidence and append summaries."""
import ast
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_audit_round17'


def main():
    tests=[]
    for name,path in [('new_semantics','_p0pilot/round17_20261026/test_sat_semantics.py'),
                      ('native_context','_p0pilot/round10_20261025/test_context.py'),
                      ('historical_boundary','_p0pilot/round9_20261025/test_boundary_repr.py')]:
        result=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/path)],
                              cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        log=result.stdout+result.stderr
        (OUT/f'test_{name}.log').write_text(log,encoding='utf-8')
        assert result.returncode==0,log
        tests.append(dict(name=name,returncode=result.returncode,log=f'test_{name}.log'))
    files=[ROOT/'phase2/ys'/f for f in ['sat_boundary_semantics.py',
           'sat_functional_relations.py','sat_functional_relations_agnostic.py',
           'sat_functional_relations_v3.py']]
    for p in files:ast.parse(p.read_text(encoding='utf-8-sig'))
    existing=json.loads((OUT/'existing_evidence_audit.json').read_text(encoding='utf-8'))
    for path,sha in existing['code_hashes'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
    solver=json.loads((OUT/'solver_validation.json').read_text(encoding='utf-8'))
    v3=json.loads((OUT/'v3_path/validation.json').read_text(encoding='utf-8'))
    assert solver['actual_sat_queries']+v3['actual_sat_queries']==224
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    report=ROOT/'10.15/00_说明/SAT第十七轮_通用影响性审计与脚本修复_20261026q.md'
    body=f'''# 第十七轮：通用影响性审计与脚本修复

更新时间：{now}。本轮为脚本修复与有界验证；**训练0、工程网表新SAT查询0、测试标签读取0**。
新执行的224次SAT仅用于合成回归电路，不增加40条关系或11条配对，不提高工程覆盖率。

## 结论

目前训练所用18维摘要不是只依靠MUX：它对每个cut坐标做实际单比特翻转配对。
该算法在完整合法表上没有发现输入次序错误。旧四查询脚本和v3仍有缺陷，已修复。
当前influence表示**可行且输出被强制的可比较模式子集内的输出变化**，不是固定共同PI/状态的因果干预证明。
未观察到变化且比较覆盖不足时不能写成全局无影响。结构reach不是SAT传播或时序可达性。

## 已定位并修复

1. **旧cone超时假阳性**：`q3 != proved`会把unknown当反例；改为必须refuted。
   原四问仅证明特定条件对比，不能决定整个cut函数或通用逐输入影响。
   新legacy行保留`condition_contrast`，`influence=0/influence_valid=0`，明确scope，停止输出整体status=proved。
   历史CSV不追改，不把旧结果自动升级成新证据。
2. **v3输入位序错误**：原行号`j xor (1<<i)`与输入元组顺序相反，抽样/重排行时也会错配。
   改为实际模式字符串翻转第i位并查找配对；MUX/AND/OR/XOR/NAND统一处理，MUX的S0仅是额外角色统计。
   最小反例Y=S0原control_influence=0，修正后1（算法回归例，不是新增工程关系）。
3. **v3把MUX控制影响作为通用关系通过条件**：改为任一输入的有效变化，控制角色单列。
4. **结果错位**：旧解析器丢掉timeout/missing，后续成功结果会挤到前一问。
   三个新执行入口均输出唯一SATQ标记；解析器保留unknown/error槽位，重复标记拒绝。
   未标记历史日志只能作为旧格式读取，不能恢复丢失的查询绑定。
5. **不可行/未定/未知混用、抽样冒充完整函数**：双proved是不可行，双refuted是可行但未定；失败/超时是unknown。
   decided要求完整枚举、非空可行域且所有可行模式被强制。受限可行域显式计数；全不可行不算功能证明。
   抽样表只能提供子集证据。max-patterns现在是真正的查询模式上限。
6. **别名与自包含边界**：v3 direct-set路径在查询前拒绝重复cut bit、target属于cut、非标量或缺失边界；保留拒绝清单。
   不强行合并Q/QN；同bit边界未来应使用predicate提取器处理，不能重复-set覆盖。
7. **结构reach误计**：只计到达DFF的D输入，不把clock/reset/scan作为D端证据；同一信号扇出到两个DFF的D计两个端点。
   保留网名别名，并支持真实port_directions。
8. **性能与追溯**：结构图索引从逐候选重建改为每design一次复用；v3不再信任mtime-only raw缓存。
   新增source/raw/cell-map/script/log哈希、cut bit、target bit、query IDs和逐查询台账；默认拒绝覆盖已有证据目录。

## 验证

- 新增13项回归，其中独立穷举全部272个二/三输入布尔函数；含输入重排、稀疏模式、超时、不可行、别名、自cut、D端计数。
- 9种合成电路：MUX/AND3/OR3/XOR3/NAND3/单输入投影/同bit别名/未观测输入/Q-QN互补。
  144次SAT、72模式，与独立Python穷举环境oracle全部一致，约7秒Yosys墙钟。
- 实际v3 rename/keep/seq1路径5个有效电路、80次SAT全部通过；另1个target与cut同bit被拒绝。
- 原native上下文8项与历史boundary12项回归通过；合计33项测试（含272函数内部枚举）。
- 66条既有记录：40盲关系+4机制关系+22个双侧完整配对表，新共享摘要的18列与逐输入统计兼容；没有重写历史数组。
- 2000门/200候选合成结构索引基准：逐次建索引{existing['index_benchmark']['uncached_s']:.6f}s，
  一次建索引后复用{existing['index_benchmark']['cached_including_build_s']:.6f}s，结果一致。
  这只说明结构准备开销减少，不能外推成整体SAT求解或GPU训练加速倍率。

## 修改与产物

- 新增生产共享模块：`phase2/ys/sat_boundary_semantics.py`。
- 修改：`sat_functional_relations.py`、`sat_functional_relations_agnostic.py`、`sat_functional_relations_v3.py`。
- 原件备份后缀：`.bak_round17_20261026`；没有改训练入口、cell map或历史round9/10 native实现。
- 证据：`tables/sat_audit_round17/`；测试与审计脚本：`_p0pilot/round17_20261026/`。

## 使用边界与下一步

修复后的v3仍是legacy cell-map/seq1自由初态上下文；第10–16轮是native物理Q组合上下文，不能混表、不能静默把它当成新的全网表提取器。
旧`full_batch`仍调用四查询legacy入口，不推荐作为未来“通用SAT全覆盖”的执行入口。
若转向小网表逐节点提取，应沿native上下文建立独立、带预算的predicate边界提取入口，复用新共享语义模块，
先冻结设计组划分和cut规则，再试提取成本；不按木马名或测试正例挑候选。
本轮未实现共享环境因果干预、复位可达性、真实时序传播或检测收益。
'''
    report.write_text(body,encoding='utf-8')
    section=f'''
<!-- sat_audit_round17:start -->
## 27. 第十七轮：通用影响性审计与脚本修复

更新时间：{now}。详见[{report.name}]({report.name})。

- 当前18维摘要不是MUX专用；66条既有边界/双侧配对表重算兼容，历史训练数组未改。
- 修复旧cone把unknown当影响、v3输入翻转位序/抽样错配、MUX控制角色误作通用判据、超时日志错位、不可行/未知混用和抽样冒充完整域。
- legacy四问降为condition_contrast（influence_valid=0），不再作为通用影响性证明；结构reach只计DFF D端。
- 图索引每design复用，v3增加边界拒绝清单、源/raw/script/log绑定、query台账与防覆盖保护；不再用mtime缓存作为证据。
- 33项回归通过（内部含272布尔函数穷举）；224次合成电路SAT通过，工程网表新查询0、训练0、测试读取0。累计仍11/40、22个target支持。
- influence仅为可比较可行强制模式对的输出变化，不是共享环境因果干预。v3的legacy seq1与native物理Q上下文分开，不混表。
<!-- sat_audit_round17:end -->
'''
    for filename in ['SAT作用证明.md','SAT工作总结.md']:
        p=ROOT/'10.15/00_说明'/filename
        text=p.read_text(encoding='utf-8-sig')
        if '<!-- sat_audit_round17:start -->' not in text:
            p.write_text(text.rstrip()+'\n'+section,encoding='utf-8')
    index=ROOT/'10.15/99_共用资产/repro/index.csv'
    if 'sat_audit_round17_20261026' not in index.read_text(encoding='utf-8-sig'):
        with index.open('a',encoding='utf-8',newline='') as f:
            csv.writer(f).writerow(['table','sat_audit_round17_20261026',str(OUT.relative_to(ROOT)),
                                    '', '', 'SAT semantic repair; 224 synthetic queries; 66 compatibility records; no training'])
    manifest=dict(created=now,tests=tests,syntax_files=4,synthetic_sat_queries=224,
                  new_project_sat_queries=0,training_runs=0,test_labels_read=False,
                  historical_feature_records=66,code_hashes=existing['code_hashes'],
                  report=str(report.relative_to(ROOT)))
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
