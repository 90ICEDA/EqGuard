import csv,hashlib,json,shutil,zipfile
from pathlib import Path
from datetime import datetime
from docx import Document
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
target=ROOT/'10.15/完成工作.docx';backup=H/'完成工作_编辑前.docx';candidate=H/'完成工作_图表补充候选.docx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(target)==sha(backup),'用户文档在编辑期间又有更新，不能覆盖'
qa=json.loads((H/'版式检查.json').read_text(encoding='utf-8'))
assert qa['pages']==18 and not qa['blank_pages']
doc=Document(candidate)
assert len(doc.inline_shapes)==18 and len(doc.tables)==9
with zipfile.ZipFile(backup) as z: old={hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
with zipfile.ZipFile(candidate) as z: new={hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
assert old.issubset(new),'原有图片必须保留'
shutil.copy2(candidate,target)
assert sha(target)==sha(candidate)
now=datetime.now().astimezone().isoformat();tag='第三十六轮：完成工作图表补充与双分支独立审计'
note=f'''\n\n### {tag} {now}

按用户已保存的《10.15/完成工作.docx》原章节补充，原稿保存在 `_p0pilot/round36_20261029/完成工作_编辑前.docx`。第一章加入数据路线、方法框架、特征体系三幅说明图和特征分组表；第二章补历史增广、对象粒度、预测漂移、原语、泛化、真实木马与正常MUX连接和边界变换图，另补可靠对应及新版编码结果。新增17图、7表，连同原稿共18图、9表；Word导出18页，逐页核验，无空白页，原有图片完整保留。

SAT章节复用冻结证据：259训练视图全量覆盖审计与221视图分布快照分开，正负例、同宿主/视图/门型/cut匹配、跨宿主方向、摘要压缩碰撞和历史真实/置换/零内容训练分别报告。严格匹配条件变化率/最大变化率AUC0.6223/0.5427；s35932正例等权条件变化率0.3315，不能挑选节点对权重的0.5980代替；历史小样本AP差异不宣称稳定SAT增益。负例含未知背景、验证配对仅2对可信正常、测试对应缺失等限制均保留。未将正在补跑的验证/测试SAT混入冻结统计。

双分支原因分析另存 `_p0pilot/round36_20261029/双分支新旧配置审计_不入论文.md`，未加入论文。新版可信测试A/B为0.19893±0.02184/0.15820±0.05037，旧标签全节点也未逆转；旧mode4一致性、图方向、归一化、前向范围和选模均与新版不同。A4与B每支2层感受野不匹配，但旧B同样每支2层，不能误判为新引入的层数错误。现有证据不能隔离反转原因；建议将来同深度对照，再单独考察融合/一致性。

本轮0次训练、0次SAT查询；没有操作后台SAT、删除或移动旧结果。配图PNG/SVG与图源CSV、生成脚本及证据提取位于 `_p0pilot/round36_20261029`。
'''
for name in ('SAT作用证明.md','SAT工作总结.md'):
    p=ROOT/'10.15/00_说明'/name
    if tag not in p.read_text(encoding='utf-8-sig'):
        with p.open('a',encoding='utf-8') as f:f.write(note)
registry=ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv'
if tag not in registry.read_text(encoding='utf-8-sig'):
    with registry.open('a',encoding='utf-8',newline='') as f:
        csv.writer(f).writerow([now,tag,'make_figures.py;build_document.py;render_document.py;finalize_document.py','document only;read-only evidence','NA','frozen historical and round27/33/34/35','protocols separated','_p0pilot/round36_20261029','18pages;18figures;9tables','完成','0 training;0 SAT;original backup retained'])
report=dict(completed_at=now,target=str(target),target_sha=sha(target),backup=str(backup),backup_sha=sha(backup),pages=18,figures=18,new_figures=17,tables=9,new_tables=7,original_media_preserved=True,visual_qa='All 18 pages inspected; table splitting and circuit label size corrected',new_training=0,new_sat=0,dual_analysis_in_paper=False)
(H/'COMPLETE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
