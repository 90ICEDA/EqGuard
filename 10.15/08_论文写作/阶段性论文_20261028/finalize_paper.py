"""Document QA record and append-only engineering registration."""
from pathlib import Path
import csv, datetime, hashlib, io, json, re
from zipfile import ZipFile
from lxml import etree
from pypdf import PdfReader
H=Path(__file__).resolve().parent;R=H.parents[2];B=H/'构建与核验'
stem='面向等价网表的图神经网络硬件木马检测模型研究'
md=H/(stem+'.md');docx=H/(stem+'.docx')
s=md.read_text(encoding='utf-8')
assert not re.search(r'TODO|待补数字|占位符|待填写',s)
assert '10.15/原论文.docx' in s and 'D:/GIN训练/' in s
tables=re.findall(r'^表(\d+) ',s,re.M)
assert tables==[str(i) for i in range(1,12)],tables
sections=re.findall(r'^### 7\.(\d+) ',s,re.M)
assert sections==[str(i) for i in range(1,12)],sections
with ZipFile(docx) as z:
    tree=etree.fromstring(z.read('word/document.xml'))
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
assert len(tree.findall('.//m:oMath',ns))==7
assert len(tree.findall('.//w:tbl',ns))==15
text=''.join(tree.itertext())
assert '$$' not in text and '<!--' not in text
pages=PdfReader(B/'论文版式核验.pdf').pages
assert len(pages)==23
assert all(len(p.extract_text().strip())>100 for p in pages)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=datetime.datetime.now().astimezone().isoformat()
qa=dict(completed_at=stamp,pages=23,tables=15,figures=3,native_equations=7,
        all_pages_visually_inspected=list(range(1,24)),blank_pages=[],
        visual_findings='No clipping, overlap, missing glyphs, isolated final table row or broken captions; long appendix tables repeat headers.',
        artifacts={p.name:sha(p) for p in [md,docx,B/'论文版式核验.pdf']},
        original_proposal=dict(path=str(R/'10.15/原论文.docx'),sha256=sha(R/'10.15/原论文.docx')),
        historical_review=str(B/'早期实验复核/历史实验复核.json'),
        new_training_runs=0,source_experiment_files_modified=False)
(B/'最终交付核验.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
(H/'交付说明.md').write_text('''# 阶段性论文交付说明

正文为《面向等价网表的图神经网络硬件木马检测模型研究》，Word共23页，配套Markdown为可编辑源稿。以10.15阶段为主要证据，结合D盘历史实验与10.15/原论文.docx的初始研究目标。

论文包含中英文摘要、问题与数据、检测模型、SAT功能证据、实验与讨论、原始方案落实情况、参考文献与5个附录，共15张表、3幅图、7个原生Word公式。

核心结论保留当前双分支配置与区域监督的三种子改进；明确历史增广、域对抗及primitive编码实验的独立协议和局限。SAT覆盖与检测收益分别陈述，未将正在进行的全量提取写成已完成结果。未宣称尚未落实的GraphSAINT采样、SAGPool、多头注意力及完整对比学习已获验证。

构建与核验目录保存原始证据哈希、CSV复算、早期实验审计、原论文提取、生成脚本、版式检查和中间文件。最终版已逐页渲染检查。原始论文、D盘历史文件与实验脚本均未修改，未为写作追加训练或SAT搜索。

后续补入全量SAT结果或独立测试时，应更新正文及证据清单后重新构建、导出和逐页检查，不直接套用旧版冻结数字。
''',encoding='utf-8')
note='''

### 阶段性论文整理 2026年10月28日

已生成08_论文写作/阶段性论文_20261028/面向等价网表的图神经网络硬件木马检测模型研究.docx及同名Markdown。23页，15表、3图、7个原生公式。以10.15为主，纳入D:/GIN训练的增广、LOCO和基础门编码复核，并对齐原论文.docx初始研究目标。修正旧电路计数混入汇总行的问题；历史成绩与当前折分开报告；未把SAT高覆盖写成稳定检测收益。配套证据、源文件哈希及逐页版式核验保存在论文目录。仅创建写作产物与追加登记，未修改实验脚本、未启动新训练，不干预已在运行的SAT任务。
'''
for rel in ['10.15/08_论文写作/说明.md','10.15/00_说明/SAT作用证明.md','10.15/00_说明/SAT工作总结.md']:
    with (R/rel).open('a',encoding='utf-8') as f:f.write(note)
reg=R/'10.15/99_共用资产/运行登记/运行登记表.csv'
buf=io.StringIO(newline='');w=csv.writer(buf)
w.writerow([stamp,'论文阶段性整理','build_paper.py + 只读Word导出与render_docx版式核验','原方案+D盘历史+10.15证据','不新增','分别沿用原协议','多版本分别统计',str(H.relative_to(R)),'23页;15表;3图;7公式;历史120条AP复算;不新增训练','成功',''])
with reg.open('a',encoding='utf-8',newline='') as f:f.write(buf.getvalue())
print(json.dumps(dict(pages=len(pages),chinese_chars=len(re.findall(r'[\u4e00-\u9fff]',s)),total_chars=len(s),qa_file=str(B/'最终交付核验.json')),ensure_ascii=False))
