"""Five-part progress report authoring; no experiment imports or execution."""
from pathlib import Path
import importlib.util,json,hashlib,re,shutil,datetime
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

H=Path(__file__).resolve().parent;ROOT=H.parents[2];OLD=H.parent/'阶段性论文_详细修订版_20261028'
STEM='面向等价网表的GNN木马检测研究阶段报告'
B=H/'构建与核验';B.mkdir(exist_ok=True);A=H/'assets';A.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('existing_paper_format',OLD/'build_paper.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    sources=[OLD/'面向等价网表的图神经网络硬件木马检测模型研究.md',OLD/'面向等价网表的图神经网络硬件木马检测模型研究.docx',
        OLD/'构建与核验/最终交付核验.json',OLD/'构建与核验/详细修订取证.json',ROOT/'10.15/原论文.docx',ROOT/'10.15/10.22新说明.txt',
        ROOT/'_p0pilot/round27_20261027/feature_distribution_reviews/review_00002/distribution.json',
        ROOT/'_p0pilot/round27_20261027/label_distribution_reviews/review_00000/comparison.json',
        ROOT/'_p0pilot/round27_20261027/matched_feature_reviews/review_00000/report.json',
        ROOT/'_p0pilot/round27_20261027/matched_feature_reviews/review_00000/sensitivity_validation.json',
        ROOT/'_p0pilot/round27_20261027/status_reviews/review_00003/status.json',
        ROOT/'_p0pilot/round27_20261027/status_reviews/review_00003/incremental_audit.json']
    source_manifest=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in sources]
    oldqa=json.loads((OLD/'构建与核验/最终交付核验.json').read_text(encoding='utf-8'))
    for p in sources[:2]:assert sha(p)==oldqa['artifacts'][p.name]
    shutil.copy2(OLD/'assets/图2_主模型消融.png',A/'主模型消融.png')
    shutil.copy2(ROOT/'_p0pilot/round27_20261027/matched_feature_reviews/review_00000/严格匹配区分能力.png',A/'SAT严格匹配.png')
    md=H/(STEM+'.md');s=md.read_text(encoding='utf-8');headings=re.findall(r'^## (.+)$',s,re.M)
    assert headings==['一 已完成研究工作','二 拟完成研究工作','三 如期完成论文工作的可能性','四 存在的困难与解决方案','五 后期工作计划']
    assert not re.search(r'TODO|待填|\{\{',s)
    doc=Document();sec=doc.sections[0];sec.page_width=Inches(8.2677);sec.page_height=Inches(11.6929)
    sec.left_margin=sec.right_margin=Inches(.75);sec.top_margin=sec.bottom_margin=Inches(.75);sec.footer_distance=Inches(.3)
    for n in ['Normal','Title','Heading 1','Heading 2','Caption']:
        st=doc.styles[n];st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0)
        st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体' if n in ['Normal','Caption'] else '黑体')
    for border in list(doc.styles.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
    normal=doc.styles['Normal'];normal.font.size=Pt(11);pf=normal.paragraph_format;pf.line_spacing=1.35;pf.space_after=Pt(5);pf.first_line_indent=Pt(22);pf.widow_control=True
    for n,size in [('Title',18),('Heading 1',15),('Heading 2',12.5)]:
        st=doc.styles[n];st.font.size=Pt(size);st.paragraph_format.keep_with_next=True;st.paragraph_format.first_line_indent=Pt(0);st.paragraph_format.space_before=Pt(12);st.paragraph_format.space_after=Pt(7)
    for n in ['Heading 1','Heading 2']:doc.styles[n].paragraph_format.page_break_before=False
    doc.styles['Caption'].font.size=Pt(9.5);doc.styles['Caption'].paragraph_format.first_line_indent=Pt(0)
    foot=sec.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.CENTER;foot.paragraph_format.first_line_indent=Pt(0)
    F.font_run(foot.add_run('第 '),9);fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');foot._p.append(fld);F.font_run(foot.add_run(' 页'),9)
    lines=s.splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in cells):rows.append(cells)
                i+=1
            F.table(doc,rows);continue
        if line.startswith('# '):
            p=doc.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;F.paragraph_text(p,line[2:])
        elif line.startswith('## '):doc.add_heading(line[3:],level=1)
        elif line.startswith('### '):doc.add_heading(line[4:],level=2)
        elif line.startswith('!['):
            m=re.match(r'!\[(.*?)\]\((.*?)\)',line);p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.keep_with_next=True
            shape=p.add_run().add_picture(str(H/m[2]),width=Inches(6.4));shape._inline.docPr.set('descr',m[1])
        else:
            caption=bool(re.match(r'^[图表]\d+ ',line));p=doc.add_paragraph(style='Caption' if caption else None)
            if caption:
                p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=line.startswith('表');p.paragraph_format.keep_together=True
            if line.startswith('阶段研究报告'):
                p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_after=Pt(12)
            F.paragraph_text(p,line,9.5 if caption else None)
        i+=1
    doc.core_properties.title='面向等价网表的图神经网络硬件木马检测模型研究阶段报告';doc.core_properties.subject='已完成研究与后期计划';doc.core_properties.author=''
    target=H/(STEM+'.docx');doc.save(target)
    manifest=dict(time=datetime.datetime.now().astimezone().isoformat(),headings=headings,chinese_chars=len(re.findall(r'[\u4e00-\u9fff]',s)),tables=len(doc.tables),figures=len(doc.inline_shapes),sources=source_manifest,markdown_sha256=sha(md),docx_sha256=sha(target),new_sat_queries=0,new_training_runs=0,experiment_scripts_modified=False)
    (B/'来源冻结与构建.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='sources'},ensure_ascii=False));print(target)

if __name__=='__main__':main()
