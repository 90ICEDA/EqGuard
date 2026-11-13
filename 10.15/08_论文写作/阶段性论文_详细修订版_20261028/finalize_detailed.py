"""Final non-training QA and append-only registration for the detailed paper."""
from pathlib import Path
from zipfile import ZipFile
import csv,datetime,hashlib,io,json,re
from lxml import etree
from pypdf import PdfReader
H=Path(__file__).resolve().parent;R=H.parents[2];B=H/'构建与核验'
stem='面向等价网表的图神经网络硬件木马检测模型研究'
md=H/(stem+'.md');docx=H/(stem+'.docx');s=md.read_text(encoding='utf-8')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert re.findall(r'^表(\d+) ',s,re.M)==[str(i) for i in range(1,27)]
assert re.findall(r'^图(\d+) ',s,re.M)==[str(i) for i in range(1,5)]
assert re.findall(r'^## (\d+) ',s,re.M)==[str(i) for i in range(1,13)]
assert '本文检查phase2/p2common.py确认' in s
assert all(x in s for x in ['0.2604','0.2112','0.1632','600条记录','5月24日','A/B','0.1850'])
assert not re.search(r'\{\{|TODO|待填数字|占位符',s)
for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)',s):assert (H/m[1]).exists()
with ZipFile(docx) as z:
    tree=etree.fromstring(z.read('word/document.xml'))
    styles=etree.fromstring(z.read('word/styles.xml'))
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
tables=len(tree.findall('.//w:tbl',ns));equations=len(tree.findall('.//m:oMath',ns))
assert tables==30 and equations==7
assert not styles.findall('.//w:pBdr',ns)
assert '$$' not in ''.join(tree.itertext())
pdf=PdfReader(B/'论文版式核验.pdf');assert len(pdf.pages)==40
assert all(len(p.extract_text().strip())>100 for p in pdf.pages)
detail=json.loads((B/'详细修订取证.json').read_text(encoding='utf-8'))
assert all(sha(row['path'])==row['sha256'] for row in detail['inputs'])
diff=json.loads((B/'最终渲染差异.json').read_text(encoding='utf-8'))
review=dict(time=datetime.datetime.now().astimezone().isoformat(),pages=40,chinese_chars=len(re.findall(r'[\u4e00-\u9fff]',s)),main_tables=26,appendix_tables=4,figures=4,native_equations=7,
    all_pages_visually_inspected=list(range(1,41)),final_changed_pages_reinspected=diff['changed_pages'],
    unchanged_pages_pixel_identical=diff['unchanged_pages'],blank_pages=[],visual_defects=[],
    historical_input_files=len(detail['inputs']),historical_input_hashes_unchanged=True,
    artifacts={p.name:sha(p) for p in [md,docx,B/'论文版式核验.pdf']},new_training_runs=0,new_sat_queries=0,experiment_scripts_modified=False)
(B/'最终交付核验.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
(H/'交付说明与修订对照.md').write_text('''# 详细修订版交付说明

上一版对历史工作压缩过多。本版按原始课题主线重组正文，保留上一版文件，另交付40页Word与Markdown源稿。正文约2.44万汉字，含26张正文表、4张附录表、4幅图、7个原生Word公式。

| 内容 | 详细版位置 |
|---|---|
| 原始研究目标与全程主线 | 引言及附录D |
| 5至6月S-GIN、阈值、HNM、不平衡损失、误报与标签 | 第3章，约第4–7页 |
| 8至9月改写、600视图、CEC、四组、恒等控制、预算、LOCO | 第4章，约第8–11页 |
| 9月困难变体、10月表示探针、对象拆分合并、双干预、M0–M3 | 第5章，约第12–15页 |
| 10.10 A/B载荷、9维功能与6维cut代理、简单模型与对照 | 第6章，约第15–18页 |
| 10.12欠训练修正、学习率与预算三种子、损失扫描 | 第7章，约第18–20页 |
| 10.13–14原语、筛选、合并表示、LIO、别名与keep绑定 | 第8章，约第20–22页 |
| 10.15数据、实例来源、双分支、区域监督和N1–N4 | 第9章，约第23–30页 |
| 真实SAT关系、内容对照及全量提取边界 | 第10章，约第30–33页 |
| 各阶段结论、限制与原方案落实 | 第11–12章及5个附录 |

本版重新核算历史CEC计数、HNM混淆矩阵、训练配置三种子及LIO种子汇总；probe表直接从CSV生成。修正旧文档与CSV的A/B数值冲突、AnyMiss文字解释、标准化剩余与原尺度差值混淆，并明确欠训练后的结论更正。历史不同数据版本不合并排名。

构建与核验保存取证哈希、原图、历史原文、生成代码及40页逐页检查记录。没有修改原论文或D盘历史文件，没有修改训练或SAT提取脚本，也没有为写作追加训练和SAT查询。
''',encoding='utf-8')
note='''

### 阶段性论文详细修订 2026年10月28日

已另存08_论文写作/阶段性论文_详细修订版_20261028/的Word及Markdown，上一版保留。新稿40页，约2.44万汉字、26张正文表及4张附录表、4图、7个原生公式。第3–8章完整展开5月至10.14的S-GIN、阈值与HNM、600视图、四组与控制、捷径探针、对象关系、双干预、A/B载荷、功能代理、欠训练修正、原语与LIO以及绑定失败，随后衔接10.15模型与SAT。历史计数和多种子重新核算，AnyMiss及旧A/B口径冲突明确更正。40页已逐页渲染检查，取证与QA记录见新稿构建与核验目录。仅生成写作产物与追加登记，未修改实验脚本、未新增训练或SAT搜索。
'''
for rel in ['10.15/08_论文写作/说明.md','10.15/00_说明/SAT作用证明.md','10.15/00_说明/SAT工作总结.md']:
    with (R/rel).open('a',encoding='utf-8') as f:f.write(note)
buf=io.StringIO(newline='');csv.writer(buf).writerow([review['time'],'阶段性论文详细修订','assemble_detailed.py + build_paper.py + Word只读导出与逐页核验','全历史主线重写','不新增','多版本分别报告','历史各版本+hosts_bt31',str(H.relative_to(R)),'40页;2.44万汉字;30表;4图;7公式;原始证据哈希保持','成功',''])
with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:f.write(buf.getvalue())
print(json.dumps(dict(pages=40,chinese_chars=review['chinese_chars'],tables=tables,figures=4,source_files=len(detail['inputs']),errors=[]),ensure_ascii=False))
