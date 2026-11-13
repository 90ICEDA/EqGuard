"""Deterministic paper builder using the bundled document runtime.

No experiment, solver or training entry point is imported or executed.
"""
import csv
import datetime
import hashlib
import json
import re
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STEM='面向等价网表的图神经网络硬件木马检测模型研究'
SOURCE=HERE/(STEM+'.md')
ASSETS=HERE/'assets';ASSETS.mkdir(exist_ok=True)
BUILD=HERE/'构建与核验';BUILD.mkdir(exist_ok=True)


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def evidence():
    inputs=[
        '10.15/03_特征与模型/N2_双分支复核/tables/t13_per_seed.csv',
        '10.15/03_特征与模型/N2_双分支复核/tables/t13_summary.csv',
        '10.15/03_特征与模型/C6_区域级监督/tables/t12_region_loss_summary.csv',
        '10.15/06_统一评测协议/N4_三向泛化_100ep/tables/n4_seedagg.csv',
        '10.15/07_论文图表/tables/netlist_compare.csv',
        '10.15/03_特征与模型/C4_等价一致性/C4_lambda_table.csv',
        '10.15/02_弱监督检测/N1_对照诊断/a4/a4_triplet_seedwise_paired.csv',
        'generate_trans/folds/hosts_bt31/views.json',
        '_p0pilot/round27_20261027/result_reviews/review_00000/review.json',
        '_p0pilot/round27_20261027/result_reviews/raw_sample_00000/raw_sample.json',
        '10.15/06_统一评测协议/N4_三向泛化/tables/sat_round21/runs.csv',
        '10.15/00_说明/SAT第十八轮_小网表逐节点提取与三组GPU对照_20261026r.md',
        '10.15/00_说明/SAT第十九轮_摘要信息损失与跨插入失败诊断_20261026s.md',
        '10.15/00_说明/SATk4全量补跑与既有结果复核_20261028.md',
        '10.15/01_数据与标签/A6_训练集体检/说明.md',
        '10.15/原论文.docx','models/gin_net.py','phase2/ys/region_loss.py','train_test2.3.py',
        '_devcfg/dual.yaml','STAGE_REPORT.md','README_PIPELINE_2.3.md']
    records=[]
    detail=json.loads((BUILD/'详细修订取证.json').read_text(encoding='utf-8'))
    assert not detail['errors']
    for row in detail['inputs']:
        assert sha(row['path'])==row['sha256']
        records.append(row)
    legacy=json.loads((BUILD/'早期实验复核/历史实验复核.json').read_text(encoding='utf-8'))
    assert not legacy['errors']
    for row in legacy['inputs']:
        assert sha(row['path'])==row['sha256']
        records.append(row)
    for rel in inputs:
        p=ROOT/rel
        records.append(dict(path=rel,sha256=sha(p),bytes=p.stat().st_size))
        if p.suffix=='.csv':shutil.copy2(p,BUILD/p.name)
    rows=list(csv.DictReader((ROOT/inputs[0]).open(encoding='utf-8-sig')))
    summaries=list(csv.DictReader((ROOT/inputs[1]).open(encoding='utf-8-sig')))
    checks=[]
    for row in summaries:
        vals=np.array([float(r['view_ap']) for r in rows if r['model']==row['model']])
        assert len(vals)==3
        mean,std=float(vals.mean()),float(vals.std(ddof=1))
        assert abs(mean-float(row['view_ap_mean']))<1e-12
        assert abs(std-float(row['view_ap_std']))<1e-12
        checks.append(dict(model=row['model'],AP=mean,SD=std,n=3,per_seed=vals.tolist()))
    a2=next(r for r in checks if r['model'].startswith('A2'))
    a1=next(r for r in checks if r['model'].startswith('A1'))
    a3=next(r for r in checks if r['model'].startswith('A3'))
    a5=next(r for r in checks if r['model'].startswith('A5'))
    review=json.loads((ROOT/inputs[8]).read_text(encoding='utf-8'))
    raw=json.loads((ROOT/inputs[9]).read_text(encoding='utf-8'))
    assert not review['errors'] and not raw['errors']
    data=dict(frozen_at=datetime.datetime.now().astimezone().isoformat(),inputs=records,
        main_AP_recomputed=checks,dual_relative_change=a2['AP']/a1['AP']-1,
        region_relative_change=a5['AP']/a3['AP']-1,
        raw_sample_batches=sum(x['sampled_batches'] for x in raw['panels'].values()),
        raw_sample_queries=sum(x['sampled_queries'] for x in raw['panels'].values()),
        replayed_covered_records=sum(x['replayed_records'] for x in review['panels'].values()),
        training_metrics=review['training'],source_markdown_sha=sha(SOURCE),
        policy='Ongoing full SAT extraction is excluded from completed detection results')
    (BUILD/'证据冻结与数值复核.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def figures():
    for source,target in [('F5_ablation_main.png','图2_主模型消融.png'),
                          ('F4_granularity_regionloss.png','图3_区域监督.png')]:
        shutil.copy2(ROOT/'10.15/07_论文图表/figs'/source,ASSETS/target)
    im=Image.new('RGB',(2400,1260),'white');d=ImageDraw.Draw(im)
    font=lambda size:ImageFont.truetype('C:/Windows/Fonts/simsun.ttc',size)
    f=font(43);small=font(33);title=font(48)
    d.text((75,45),'等价网表的双分支检测与区域监督',font=title,fill='black')
    def box(xy,text):
        d.rectangle(xy,outline='#35556e',width=4)
        x0,y0,x1,y1=xy
        lines=text.split('\n');line_h=57
        y=(y0+y1-line_h*len(lines))/2
        for line in lines:
            w=d.textlength(line,font=f);d.text(((x0+x1-w)/2,y),line,font=f,fill='black');y+=line_h
    def arrow(start,end,dashed=False,color='#35556e'):
        x0,y0=start;x1,y1=end
        if dashed:
            length=((x1-x0)**2+(y1-y0)**2)**.5
            for k in range(0,int(length),32):
                a=k/length;b=min(k+18,length)/length
                d.line((x0+(x1-x0)*a,y0+(y1-y0)*a,x0+(x1-x0)*b,y0+(y1-y0)*b),fill=color,width=4)
        else:d.line((start,end),fill=color,width=5)
        import math
        a=math.atan2(y1-y0,x1-x0)
        d.polygon([(x1,y1),(x1-25*math.cos(a-.45),y1-25*math.sin(a-.45)),
                   (x1-25*math.cos(a+.45),y1-25*math.sin(a+.45))],fill=color)
    box((70,450,490,680),'等价视图与来源\nCEC记录与标签\n门级连接图')
    box((690,450,1050,680),'39维基础输入\n按列划分')
    box((1240,210,1690,420),'结构分支\n前29维  GIN')
    box((1240,700,1690,910),'拓扑上下文分支\n后10维与cone5')
    box((1850,450,2310,680),'门控融合\n节点风险分数')
    box((1760,1015,2330,1185),'区域最大值与BCE\n辅助监督')
    box((550,1020,1220,1195),'SAT边界与有效性掩码\n功能证据扩展  待验证')
    arrow((490,565),(690,565));arrow((1050,520),(1240,315));arrow((1050,610),(1240,805))
    arrow((1690,315),(1850,510));arrow((1690,805),(1850,620));arrow((2080,680),(2080,1015))
    arrow((1120,1020),(1350,910),dashed=True,color='#777777')
    d.text((75,1210),'实线为既有检测路径  虚线为功能证据扩展  本图为方法示意',font=small,fill='black')
    im.save(ASSETS/'图1_模型流程.png',dpi=(300,300))


def e(tag,*children,text=None,attrs=None):
    node=OxmlElement('m:'+tag)
    if attrs:
        for k,v in attrs.items():node.set(qn('m:'+k),str(v))
    if text is not None:node.text=text
    for child in children:node.append(deepcopy(child))
    return node


def mr(text):
    return e('r',e('rPr',e('sty',attrs={'val':'p'})),e('t',text=text))


def sub(base,index):return e('sSub',e('e',mr(base) if isinstance(base,str) else base),e('sub',mr(index)))
def sup(base,index):return e('sSup',e('e',mr(base) if isinstance(base,str) else base),e('sup',mr(index)))
def frac(a,b):return e('f',e('num',mr(a)),e('den',mr(b)))
def summation(lower,body):return e('nary',e('naryPr',e('chr',attrs={'val':'∑'}),e('limLoc',attrs={'val':'subSup'}),e('supHide',attrs={'val':'1'})),e('sub',mr(lower)),e('sup'),e('e',body))


def math_nodes(key):
    if key=='gin':return [sup(sub('h','v'),'(ℓ+1)'),mr(' = '),sup('MLP','(ℓ)'),mr('((1+ε)'),sup(sub('h','v'),'(ℓ)'),mr(' + '),summation('u∈N(v)',sup(sub('h','u'),'(ℓ)')),mr(')')]
    if key=='fusion':return [sub('g','v'),mr(' = σ('),sub('W','g'),mr('['),sup(sub('h','v'),'s'),mr(' ∥ '),sup(sub('h','v'),'f'),mr(']+'),sub('b','g'),mr('),  '),sub('h','v'),mr(' = '),sub('g','v'),mr('⊙'),sup(sub('h','v'),'s'),mr('+(1−'),sub('g','v'),mr(')⊙'),sup(sub('h','v'),'f')]
    if key=='loss':return [mr('L = '),sub('L','task'),mr(' + '),sub('λ','det'),sub('L','det'),mr(' + '),sub('λ','c'),sub('L','c'),mr(' + '),sub('λ','r'),sub('L','region')]
    if key=='region':return [sub('z','R'),mr(' = '),e('limLow',e('e',mr('max')),e('lim',mr('v∈R'))),mr(' '),sub('z','v,1'),mr(',  '),sub('Y','R'),mr(' = 𝟙(∃v∈R : '),sub('y','v'),mr('=1),  '),sub('L','region'),mr(' = '),sub('BCE','w'),mr('(σ('),sub('z','R'),mr('),'),sub('Y','R'),mr(')')]
    if key=='sat':return [sub('Q','a,b'),mr(' : ∀e,  C(e) ∧ cut(e)=a ⇒ t(e)=b')]
    if key=='influence':return [sub('I','i'),mr(' = '),frac('#{(a,a′):a∼ᵢa′, t(a)≠t(a′)}','#{(a,a′):a∼ᵢa′}'),mr('   分母大于0时有效')]
    if key=='macro':return [mr('MacroAP = '),frac('1','K'),summation('j=1,…,K',mr('AP('),),mr('Gⱼ)')]
    raise KeyError(key)


def font_run(run,size=None,bold=None):
    run.font.name='Times New Roman';run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
    run.font.color.rgb=RGBColor(0,0,0)
    if size:run.font.size=Pt(size)
    if bold is not None:run.bold=bold


def paragraph_text(p,text,size=None):
    # Markdown emphasis is authoring notation, not visible punctuation in Word.
    text=text.replace('**','').replace('`','')
    for part in re.split(r'(https?://\S+)',text):
        if part.startswith('http'):
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
            url=part.rstrip('。；')
            link=OxmlElement('w:hyperlink');link.set(qn('r:id'),p.part.relate_to(url,RT.HYPERLINK,is_external=True))
            r=OxmlElement('w:r');pr=OxmlElement('w:rPr');sz=OxmlElement('w:sz');sz.set(qn('w:val'),'20');pr.append(sz);r.append(pr)
            t=OxmlElement('w:t');t.text=part;r.append(t);link.append(r);p._p.append(link)
        else:font_run(p.add_run(part),size)


def table(doc,rows):
    n=len(rows[0]);t=doc.add_table(rows=1,cols=n);t.autofit=False
    if n==2:widths=[2.8,3.9] if rows[0][0]=='主张' else [2.05,4.65]
    elif n==3:widths=[.5,2.45,3.75] if rows[0][0]=='序号' else [1.9,2.4,2.4]
    elif n==4:widths=[2.45,1.45,1.45,1.35]
    else:widths=[2.30]+[1.10]*(n-1)
    for c,w in zip(t.columns,widths):c.width=Inches(w)
    borders=OxmlElement('w:tblBorders')
    for side in ('top','left','bottom','right','insideH','insideV'):
        node=OxmlElement('w:'+side)
        for k,v in [('val','single'),('sz','4'),('color','D9D9D9')]:node.set(qn('w:'+k),v)
        borders.append(node)
    t._tbl.tblPr.append(borders)
    for j,row in enumerate(rows):
        cells=t.rows[0].cells if j==0 else t.add_row().cells
        for i,(cell,text) in enumerate(zip(cells,row)):
            cell.width=Inches(widths[i]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr=cell._tc.get_or_add_tcPr();margins=OxmlElement('w:tcMar')
            for side in ('top','left','bottom','right'):
                m=OxmlElement('w:'+side);m.set(qn('w:w'),'75');m.set(qn('w:type'),'dxa');margins.append(m)
            tcpr.append(margins)
            shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E7EDF3' if j==0 else ('F7F9FB' if j%2==0 else 'FFFFFF'));tcpr.append(shade)
            p=cell.paragraphs[0];p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.line_spacing=1.1;p.paragraph_format.space_after=Pt(1);p.paragraph_format.space_before=Pt(1)
            p.paragraph_format.keep_with_next=(j==0 or ((len(rows)<=8 or rows[0][0]=='主张') and j<len(rows)-1))
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT if i==0 or n==2 or (n==3 and rows[0][0]=='序号' and i>0) else WD_ALIGN_PARAGRAPH.CENTER
            paragraph_text(p,text,9.5 if n>=4 else 10)
            for run in p.runs:run.bold=(j==0)
        trpr=t.rows[j]._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
        if j==0:trpr.append(OxmlElement('w:tblHeader'))
    gap=doc.add_paragraph();gap.paragraph_format.space_after=Pt(2);gap.paragraph_format.line_spacing=Pt(3);gap.paragraph_format.first_line_indent=Pt(0)


def build_docx():
    doc=Document();sec=doc.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11)
    sec.left_margin=sec.right_margin=Inches(.85);sec.top_margin=sec.bottom_margin=Inches(.75)
    sec.header_distance=sec.footer_distance=Inches(.30)
    for name in ('Normal','Title','Subtitle','Heading 1','Heading 2','Caption'):
        style=doc.styles[name];style.font.name='Times New Roman';style.font.color.rgb=RGBColor(0,0,0)
        style._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体' if name=='Normal' else '黑体')
    normal=doc.styles['Normal'];normal.font.size=Pt(11);normal.paragraph_format.line_spacing=1.35
    normal.paragraph_format.space_after=Pt(5);normal.paragraph_format.first_line_indent=Pt(22)
    for name,size in [('Title',22),('Heading 1',15),('Heading 2',12.5)]:
        s=doc.styles[name];s.font.size=Pt(size);s.paragraph_format.keep_with_next=True
        s.paragraph_format.space_before=Pt(13);s.paragraph_format.space_after=Pt(7);s.paragraph_format.first_line_indent=Pt(0)
    doc.styles['Caption'].font.size=Pt(9.5);doc.styles['Caption'].font.bold=False;doc.styles['Caption'].paragraph_format.first_line_indent=Pt(0)
    # The bundled default template contains a blue Title bottom border.
    for border in list(doc.styles.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
    header=sec.header.paragraphs[0];header.paragraph_format.first_line_indent=Pt(0)
    paragraph_text(header,'面向等价网表的图神经网络硬件木马检测模型研究',9)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER;footer.paragraph_format.first_line_indent=Pt(0)
    font_run(footer.add_run('阶段性论文　｜　'),9)
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
    lines=SOURCE.read_text(encoding='utf-8').splitlines();i=0;eqkey=None;eqn=0;in_english_abstract=False
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('<!-- eq:'):
            eqkey=line.split(':',1)[1].split('-->')[0].strip();i+=1;continue
        if line.startswith('$$'):
            eqn+=1;p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0)
            para=e('oMathPara',e('oMath',*math_nodes(eqkey),mr(f'     ({eqn})')));p._p.append(para)
            i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in cells):rows.append(cells)
                i+=1
            table(doc,rows);continue
        if line.startswith('!['):
            match=re.match(r'!\[(.*?)\]\((.*?)\)',line);p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.keep_with_next=True
            p.add_run().add_picture(str(HERE/match[2]),width=Inches(6.4));i+=1;continue
        if line.startswith('# '):
            p=doc.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;paragraph_text(p,line[2:]);i+=1;continue
        if line.startswith('## '):
            in_english_abstract=(line[3:]=='Abstract')
            doc.add_heading(line[3:],level=1);i+=1;continue
        if line.startswith('### '):
            doc.add_heading(line[4:],level=2);i+=1;continue
        iscaption=bool(re.match(r'^(?:表(?:\d+|[A-Z]\d+)|图\d+)\s',line))
        p=doc.add_paragraph(style='Caption' if iscaption else None)
        if iscaption:
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            if line.startswith('表'):p.paragraph_format.keep_with_next=True
        if line.startswith(('阶段性论文','关键词','[','注：')):
            p.paragraph_format.first_line_indent=Pt(0)
        if line.startswith(('研究范围','研究依据')):p.paragraph_format.first_line_indent=Pt(0);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        if line.startswith('阶段性论文'):p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        if line.startswith(('[D','[H')):p.paragraph_format.space_after=Pt(6)
        if in_english_abstract:
            p.paragraph_format.line_spacing=1.1;p.paragraph_format.keep_together=True
        paragraph_text(p,line,10 if in_english_abstract else (9.5 if iscaption or line.startswith(('[D','[H')) else None))
        i+=1
    doc.core_properties.title=STEM;doc.core_properties.subject='等价网表下GNN硬件木马检测的阶段性研究'
    doc.core_properties.author='';doc.core_properties.keywords='GNN; hardware Trojan; equivalent netlist; region supervision; SAT'
    output=HERE/(STEM+'.docx');doc.save(output)
    (BUILD/'文档构建清单.json').write_text(json.dumps(dict(output=output.name,sha256=sha(output),
        markdown_sha256=sha(SOURCE),figures={p.name:sha(p) for p in ASSETS.glob('*.png')},
        equations=eqn,source_script_sha=sha(__file__),equation_format='Native OMML',
        experiment_scripts_modified=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print(output)


if __name__=='__main__':
    evidence();figures();build_docx()
