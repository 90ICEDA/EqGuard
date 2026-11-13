
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
from pathlib import Path
from zipfile import ZipFile
import re, json, hashlib
from lxml import etree
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from guide_text import TEXT, GLOSSARY, PROTOCOLS

ROOT=Path(_eqguard_path(''))
BASE=ROOT/'10.15/08_论文写作/中期答辩_20261105'
PPT=BASE/'面向等价网表变体鲁棒的GNN木马检测_中期答辩_已验证成果重点修订版_20261105.pptx'
FINAL=BASE/'中期答辩逐页详细讲解_对应34页成果重点修订版_20261106.docx'
WORK=ROOT/'_p0pilot/midterm_ppt_20261105/guide_20261106'
WORK.mkdir(exist_ok=True,parents=True)
sha=hashlib.sha256(PPT.read_bytes()).hexdigest()
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
slides=[]
with ZipFile(PPT) as z:
 for n in range(1,35):
  root=etree.fromstring(z.read(f'ppt/slides/slide{n}.xml'))
  shapes=root.findall('.//p:spTree/p:sp',ns)
  title_shape=shapes[0] if n==2 else shapes[1]
  title=''.join(title_shape.itertext()) if False else ''.join(title_shape.xpath('.//a:t/text()',namespaces=ns))
  full='\n'.join(root.xpath('.//a:t/text()',namespaces=ns))
  slides.append({'page':n,'title':title,'text':full,'explanation':TEXT[n]})
assert set(TEXT)==set(range(1,35))
assert slides[10]['title']=='Inspection-hard改善预算内检出'
assert '64.89%' in slides[22]['text'] and '0.5472' in slides[7]['text']

doc=Document()
sec=doc.sections[0]
sec.page_width=Cm(21);sec.page_height=Cm(29.7)
sec.top_margin=Cm(2.15);sec.bottom_margin=Cm(2.05)
sec.left_margin=Cm(2.25);sec.right_margin=Cm(2.25)
sec.header_distance=Cm(.9);sec.footer_distance=Cm(.9)
def font(style,name,size,bold=False):
 style.font.name=name;style.font.size=Pt(size);style.font.bold=bold;style.font.italic=False;style.font.color.rgb=RGBColor(0,0,0)
 rp=style.element.get_or_add_rPr();rf=rp.find(qn('w:rFonts'))
 if rf is None:rf=OxmlElement('w:rFonts');rp.insert(0,rf)
 for a in ['ascii','hAnsi','eastAsia','cs']:rf.set(qn('w:'+a),name)
 for a in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme']:rf.attrib.pop(qn('w:'+a),None)
font(doc.styles['Normal'],'宋体',12)
normal=doc.styles['Normal'].paragraph_format
normal.line_spacing=Pt(20);normal.space_after=Pt(9)
normal.first_line_indent=Pt(24);normal.widow_control=True
for name,size in [('Title',25),('Subtitle',12),('Heading 1',14),('Heading 2',12)]:
 font(doc.styles[name],'微软雅黑',size,name!='Subtitle')
 pf=doc.styles[name].paragraph_format;pf.first_line_indent=Pt(0);pf.space_before=Pt(14 if 'Heading' in name else 0);pf.space_after=Pt(8)
 pf.keep_with_next=True
 if name.startswith('Heading'):pf.keep_together=True
font(doc.styles['Header'],'宋体',9)
font(doc.styles['Footer'],'宋体',9)
header=sec.header.paragraphs[0];header.text='面向等价网表变体鲁棒的GNN木马检测 逐页理解稿'
header.paragraph_format.first_line_indent=Pt(0)
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER;footer.paragraph_format.first_line_indent=Pt(0)
footer.add_run('第 ')
def field(p,code):
 r=p.add_run();f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),code);r._r.addnext(f)
field(footer,'PAGE');footer.add_run(' 页')

title=doc.add_paragraph('中期答辩逐页详细讲解',style='Title')
sub=doc.add_paragraph('对应已验证成果重点修订版 34页PPT',style='Subtitle')
date=doc.add_paragraph('编写日期 2026年11月6日')
date.paragraph_format.first_line_indent=Pt(0);date.paragraph_format.space_after=Pt(12)
doc.add_paragraph('本文用于帮助你理解最新版答辩PPT的每一页，不是要求逐字照读的发言稿。正文按PPT第1页至第34页一一对应，每页用一段详细解释串起研究目的、方法设置、表格读法、结论和适用范围。文中的“第几页”均指PPT页码，与本Word文档页码不同。本文复用PPT及其已有证据，没有修改PPT，也没有新增训练或SAT。')
doc.add_paragraph('建议先阅读每页讲解，再回到对应PPT对照表格。遇到较高或较低的AP，先确认是不是相同数据、标签、训练预算与评价单位；遇到“稳定”，再确认说的是对应预测接近、跨种子增益同向，还是实际检测保持。三个概念不能混用。功能证据是否正确、模型输入是否保留信息和加入后是否提高检测，也需要分别判断。')

def add_table(headers,rows,widths):
 table=doc.add_table(rows=1,cols=len(headers));table.alignment=WD_TABLE_ALIGNMENT.CENTER;table.autofit=False
 for i,w in enumerate(widths):table.columns[i].width=Cm(w)
 allrows=[headers]+list(rows)
 for rid,vals in enumerate(allrows):
  cells=table.rows[0].cells if rid==0 else table.add_row().cells
  for c,(val,w) in enumerate(zip(vals,widths)):
   cell=cells[c];cell.width=Cm(w);cell.text=str(val);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   tcPr=cell._tc.get_or_add_tcPr();shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'E7E6E6' if rid==0 else ('F7F7F7' if rid%2==0 else 'FFFFFF'));tcPr.append(shd)
   margins=OxmlElement('w:tcMar')
   for a in ['top','left','bottom','right']:
    m=OxmlElement('w:'+a);m.set(qn('w:w'),'100');m.set(qn('w:type'),'dxa');margins.append(m)
   tcPr.append(margins)
   borders=OxmlElement('w:tcBorders')
   for a in ['top','left','bottom','right']:
    b=OxmlElement('w:'+a);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'5');b.set(qn('w:color'),'D9D9D9');borders.append(b)
   tcPr.append(borders)
   for par in cell.paragraphs:
    pf=par.paragraph_format;pf.first_line_indent=Pt(0);pf.line_spacing=Pt(16);pf.space_after=Pt(0);pf.keep_with_next=rid==0
    if c==0 and len(headers)==2:par.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for r in par.runs:
     r.font.name='宋体';r.font.size=Pt(10.5);r.font.bold=rid==0;r.font.color.rgb=RGBColor(0,0,0)
     r._r.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
  trPr=table.rows[rid]._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trPr.append(cant)
  if rid==0:
   repeat=OxmlElement('w:tblHeader');trPr.append(repeat)
 doc.add_paragraph().paragraph_format.space_after=Pt(2)
 return table

add_table(['PPT范围','阅读重点'],[
('第1至5页','研究目标和有效成果如何对应'),('第6至11页','等价多视图与检查预算方面的有效结果'),('第12至19页','原语表示 双分支 区域监督与特征校准'),('第20至24页','相似正常监督的公平实验与局部收益'),('第25至30页','功能证据 目标闭环与后续安排'),('第31至34页','适用边界 预训练探索与指标备份')],[3.4,13.1])
doc.add_page_break()
for a in slides:
 clean=re.sub(r'[：:，,。；;（）()＋+／/—–\-\n]+',' ',a['title']).strip()
 clean=re.sub(r'\s+',' ',clean)
 doc.add_heading(f"PPT第{a['page']}页 {clean}",level=1)
 p=doc.add_paragraph(a['explanation']);p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY

doc.add_page_break()
doc.add_heading('附录一 常用术语速查',level=1)
add_table(['术语','理解方式'],GLOSSARY,[3.2,13.3])
doc.add_page_break()
doc.add_heading('附录二 实验版本不能混用',level=1)
add_table(['实验阶段','主要设置','理解边界'],PROTOCOLS,[3.2,6.8,6.5])
doc.add_heading('附录三 证据查阅入口',level=1)
sources=[
('PPT及本轮成果回查','10.15/08_论文写作/中期答辩_20261105；10.15/00_说明/中期答辩_有效成果回查与主讲建议_20261105.md'),
('历史多视图与恒等对照','D:/GIN训练/9.26/GIN_train/results/ALLFOLDS_groups_macro_amp.csv；identity_control_vs_real_transform.csv'),
('Inspection hard','D:/GIN训练/10.5/results/phase2/task5_viewpolicy/single_to_composed_d2_per_view.csv'),
('历史原语配置','D:/GIN训练/10.13/step4_3seed_compare.csv；第四步_四组对比.md'),
('双分支与区域监督','10.15/03_特征与模型/N2_双分支复核/tables/t13_per_seed.csv；C6_区域级监督/t12_region_loss.md'),
('当前v3与正常对照','10.15/00_说明/39维v2_v3单因素基线_三种子汇总_20261104.md；39维v3合格池等预算HC分角色监督_三种子_20261104.md'),
('功能证据与接口','10.15/00_说明/等价锥联合证明扩充_review恢复与小范围补证_20261105.md；等价锥交接修正与公平离线评价_20261105.md；等价锥引脚角色与边界对齐_最小接口及单因素合同_20261105.md'),
('正常对照覆盖','10.15/00_说明/正常对照配方与PO可达口径澄清_20261105.md；新版五组加载预检_PO分层评价及正常区域不可达核查_20261105.md'),
]
for label,src in sources:
 pp=doc.add_paragraph();pp.paragraph_format.first_line_indent=Pt(0);pp.paragraph_format.line_spacing=Pt(14);pp.paragraph_format.space_after=Pt(5);pp.paragraph_format.keep_together=True
 labelrun=pp.add_run(label+'\n');labelrun.bold=True;labelrun.font.size=Pt(10)
 rr=pp.add_run(src);rr.font.size=Pt(9.5)

doc.core_properties.title='中期答辩逐页详细讲解'
doc.core_properties.subject='面向等价网表变体鲁棒的GNN木马检测 34页配套理解文档'
doc.core_properties.author=''
for st in doc.styles:
 for border in list(st.element.iter(qn('w:pBdr'))):
  border.getparent().remove(border)
for border in list(doc.element.iter(qn('w:pBdr'))):
 border.getparent().remove(border)
doc.save(FINAL)
assert hashlib.sha256(PPT.read_bytes()).hexdigest()==sha
extracted=Document(FINAL)
heads=[p.text for p in extracted.paragraphs if p.style.name=='Heading 1' and p.text.startswith('PPT第')]
assert len(heads)==34
report={'docx':str(FINAL),'pptx':str(PPT),'ppt_sha256_unchanged':sha,'slide_count':34,'explanation_chars':sum(len(v) for v in TEXT.values()),'per_slide_chars':{str(k):len(v) for k,v in TEXT.items()},'headings':heads}
(WORK/'binding_and_content_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
(WORK/'explanations.json').write_text(json.dumps(slides,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False))
