"""Edit saved user manuscript in place structurally; bundled Python DOCX authoring."""
import json,hashlib,copy,re
from pathlib import Path
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;FIG=H/'figures'
SOURCE=H/'完成工作_编辑前.docx';OUT=H/'完成工作_图表补充候选.docx'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
D=Document(SOURCE);P=list(D.paragraphs);ORIGINAL_TABLES=list(D.tables);WIDTH=(D.sections[0].page_width-D.sections[0].left_margin-D.sections[0].right_margin)/914400
def font(run,size=11.5,bold=False):
    run.font.name='Times New Roman';run.font.size=Pt(size);run.bold=bold;run.font.color.rgb=RGBColor(0,0,0)
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
def place(anchor,element):anchor.addnext(element);return element
def para(anchor,text,style=None,size=11.5,bold=False):
    p=D.add_paragraph(style=style);p.paragraph_format.line_spacing=1.15;p.paragraph_format.space_after=Pt(6)
    if style and 'Heading' in style:p.paragraph_format.keep_with_next=True
    font(p.add_run(text),size,bold);return place(anchor,p._p)
def heading(anchor,text,level=2):return para(anchor,text,'Heading '+str(level),14 if level==2 else 12.5,True)
def picture(anchor,name,caption,source):
    p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.paragraph_format.space_after=Pt(3)
    p.add_run().add_picture(str(FIG/(name+'.png')),width=Inches(WIDTH));anchor=place(anchor,p._p)
    p=D.add_paragraph(style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.paragraph_format.line_spacing=1.0;p.paragraph_format.space_after=Pt(2);font(p.add_run(caption),10.5);anchor=place(anchor,p._p)
    p=D.add_paragraph();p.paragraph_format.line_spacing=1;p.paragraph_format.space_after=Pt(8);font(p.add_run('数据与证据来源：'+source),9);return place(anchor,p._p)
def table(anchor,caption,headers,rows,widths=None):
    p=D.add_paragraph(style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;font(p.add_run(caption),10.5);anchor=place(anchor,p._p)
    t=D.add_table(rows=1,cols=len(headers));t.autofit=False
    widths=widths or [WIDTH/len(headers)]*len(headers)
    for i,h in enumerate(headers):t.rows[0].cells[i].text=str(h)
    for row in rows:
        for c,value in zip(t.add_row().cells,row):c.text=str(value)
    for rowi,row in enumerate(t.rows):
        trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
        if rowi==0:trpr.append(OxmlElement('w:tblHeader'))
        for j,c in enumerate(row.cells):
            c.width=Inches(widths[j]);tcpr=c._tc.get_or_add_tcPr();m=OxmlElement('w:tcMar')
            for tag in ('top','bottom','left','right'):
                v=OxmlElement('w:'+tag);v.set(qn('w:w'),'90');v.set(qn('w:type'),'dxa');m.append(v)
            tcpr.append(m)
            for p in c.paragraphs:
                p.alignment=WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.keep_with_next=rowi<len(t.rows)-1
                p.paragraph_format.space_after=Pt(2);p.paragraph_format.line_spacing=1.08
                for r in p.runs:font(r,10.5,rowi==0)
    pr=t._tbl.tblPr;b=OxmlElement('w:tblBorders')
    for tag in ('top','bottom','insideH'):
        e=OxmlElement('w:'+tag);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'5');e.set(qn('w:color'),'AAB2B8');b.append(e)
    pr.append(b);anchor=place(anchor,t._tbl);return para(anchor,'',size=2)
def settext(p,text):
    for r in p.runs:r.text=''
    font(p.add_run(text),11.5)
for name in ('Title','Heading 1','Heading 2','Heading 3','Caption'):
    s=D.styles[name];s.font.color.rgb=RGBColor(0,0,0)
    for border in list(s.element.xpath('.//w:pBdr')):border.getparent().remove(border)
for p in P:
    if re.match(r'^\d\.\d',p.text):p.style=D.styles['Heading 2']
    elif p.text.startswith('2  '):p.style=D.styles['Heading 1']
    for r in p.runs:r.font.color.rgb=RGBColor(0,0,0)
title=D.add_paragraph(style='Title');title.alignment=WD_ALIGN_PARAGRAPH.CENTER;font(title.add_run('面向等价网表的图神经网络木马检测研究'),17,True);D.element.body.insert(0,title._p)
# Correct only local wording needed by the new feature/version captions.
settext(P[7],P[7].text.replace('当前固定折三种子实验中','既有旧版固定折三种子实验中'))
settext(P[29],P[29].text.replace('如与非门在AND、INV特征上标1','如与非门的AND与INV构成归一化后各为1/2'))
settext(P[28],P[28].text.replace('实验实验','实验'));P[28].style=D.styles['Heading 2']
settext(P[17],P[17].text.replace('表1','表2-1'));settext(P[18],'表2-1 历史等价增广与一致性实验')
settext(P[33],P[33].text.replace('同一正式折','同一旧版正式折').replace('表4','表2-4'));settext(P[34],'表2-4 旧版固定折主模型消融')
settext(P[38],'图2-6 旧版固定折主模型消融。误差棒为三个随机种子的样本标准差；本图沿用既有实验，不与新版v2协议或历史600视图实验直接排名。')
a=picture(P[2]._p,'图1_数据路线','图1-1 数据构建从规则表到真实综合的演进','原文1.2；固定划分清单 [S1]。600视图历史矩阵与当前388视图为不同版本。')
a=picture(P[7]._p,'图1_方法框架','图1-2 网表输入与GNN检测方法框架','模型实现与阶段实验配置 [S2]。双分支、区域和SAT模块并非所有实验同时启用。')
a=picture(P[12]._p,'图1_特征体系','图1-3 基础结构拓扑 原语构成与SAT内容的关系','v2特征合同与原语脚本 [S3]。组合环已计入14维，不重复增加。')
a=table(a,'表1-1 基础39维结构拓扑特征分组',['列号 从0开始','维数','内容'],[['0–24',25,'库单元门型one-hot'],['25–28',4,'输入引脚数 连接度 PI/PO接触标记'],['29–32',4,'PI/PO方向距离及恰好两步扇入扇出规模'],['33–36',4,'寄存器边界处理后的距离与两步邻域'],['37–38',2,'组合环标记及SCC规模']],widths=[1.2,.45,WIDTH-1.65])
a=para(a,'这里的距离与邻域描述实现结构，不等于逻辑可控性或因果影响。PI/PO接触标记表示单元连接到边界网络，不能仅凭该标记断定其输出能沿数据路径影响功能PO。')
picture(ORIGINAL_TABLES[0]._tbl,'图2_增广与泛化','图2-1 历史增广策略在同源与跨宿主任务上的表现','原表2-1 [S4]。两套任务独立报告，误差棒为三种子样本标准差。')
picture(P[21]._p,'图2_恒等视图增益','图2-2 恒等视图与真实变换的增益分解','历史恒等对照 [S4]。图中是相对G1的AP差值，无未报告的误差棒。')
picture(P[25]._p,'图2_对象粒度与漂移','图2-3 节点拆分合并与预测漂移','历史G1对象统计 [S5]。41.99%为rs232木马相关对象拆分比例，不是漏检率。')
a=picture(P[26]._p,'图2_域对抗与一致性','图2-4 检测性能与配对一致性可以出现不同方向','历史seed42 LOCO [S5]。单种子探索，不能作为新协议的因果消融。')
a=table(a,'表2-2 面向检查预算的历史困难视图策略',['策略','节点AP','首次命中比例','配对MAE'],[['Random','0.5958','0.0038','0.0276'],['CE-hard','0.5981','0.0048','0.0292'],['Inspection-hard','0.5895','0.0022','0.0280']])
para(a,'首次命中比例越低，表示检查到第一个木马所需查看的节点比例越小。Inspection-hard在这一历史诊断中降低首次命中成本，但AP未提高；这两个目标应分别评价。[S5]')
a=picture(P[29]._p,'图2_历史原语编码','图2-5 历史原语编码的跨实现开发结果','10.13开发诊断 [S6]。旧原语配置同时改变门型表示和结构列筛选，不能归因于单一因素。')
a=table(a,'表2-3 编码收益在不同任务上的适用边界',['任务','39维','对照配置','解释'],[['rs232 ys_rt','0.0554±0.0164','原语 0.3824±0.1308','三种子开发诊断'],['rs232 ys_abc','0.1562±0.0167','原语 0.1970±0.0489','不同实现收益幅度不同'],['历史LIO','0.2112±0.0112','合并特征 0.1632±0.0320','合并特征不等于纯原语；协议不同']],widths=[1.1,1.25,1.55,WIDTH-3.9])
picture(P[43]._p,'图2_历史三向泛化','图2-7 旧版基线的三种泛化方向','N4历史100 epoch汇总 [S7]。LOCO仅一个测试宿主折，LIO为实例/模板留出。')
a=picture(P[44]._p,'图2_真实木马与正常MUX','图2-8 门型相似的木马载荷选择与正常时钟控制实例','两份rs232 ys_id源网表的真实MX2X1_RS引脚连接 [S8]；完整实例和网线名另存图源CSV。')
para(a,'上图木马MUX的驱动节点为37155，已有可信木马标签；下图正常MUX节点为11480，已有可信正常标签。两者都采用A、B、S0、Y引脚，但上者选择并改写rec_readyH数据路径，下者的输出连接寄存器CK时钟端。该例说明局部MUX门型相同并不意味着安全角色相同，也不构成所有位置、门型和功能边界都严格匹配的正常对照。')
# Append sections within the user's existing chapter 2.
a=D.element.body[-2]
a=heading(a,'2.6 可靠边界上的变换前后稳定性')
a=para(a,'对rs232/injalpha的ys_id与ys_abc实现，已有共享PI与同名物理Q上下文下的selector等价证明。完整selector区域由20个组合门改写为10个；图2-9只展示两层局部真实连接，未对所有内部节点强制建立一一对应。功能边界等价与节点安全标签继承仍分别审查。')
a=picture(a,'图2_已证明边界变换前后','图2-9 同一木马选择条件在两种实现中的真实局部结构','第8/9轮的原始JSON和injalpha_cross_impl查询0 [S9]；bit编号仅在各自视图内有效。')
a=picture(a,'图2_可靠对应预测稳定性','图2-10 P2-A在已有验证对应上的风险预测差异','第34轮冻结对应与保存预测 [S10]。每种子仅2对可信正常target，无测试对应。')
a=table(a,'表2-5 已有可靠target对应的评估范围',['范围','配对数','风险概率差MAE','限制'],[['训练','9','0.1083±0.0330','训练侧诊断'],['验证','2','0.0908±0.0259','两对均为可信正常'],['验证 严格PO/D证明','1','0.1152±0.0315','另一对整体检查unknown'],['测试','0','N/A','不能用验证值替代']],widths=[1.2,.55,1.5,WIDTH-3.25])
a=para(a,'两对验证target的分类翻转率均为0，但连续风险分数仍有漂移，且此处没有木马正例。另8条来自插入记录的机制角色配对仅作训练案例诊断。它们不能与盲提取主指标混池，也不能用低漂移或低翻转率代替木马检出。')
a=heading(a,'2.7 修复后基础编码的受控复核')
a=table(a,'表2-6 同一v2图上的基础编码对照',['编码','测试可信AP','旧标签全节点AP','预算'],[['39维v2','0.1989±0.0218','0.0552±0.0085','seed42/1/2 各100次更新'],['原语21维','0.1254±0.0072','0.0267±0.0107','相同图 监督 损失与预算']],widths=[1.1,1.35,1.5,WIDTH-3.95])
a=para(a,'该对照只替换门型表示，原语21维保留与39维v2相同的14维结构拓扑量；不加入SAT。可信与旧标签口径的负例集合不同，不可混用。固定v2图的seed42控制中，旧物理39维与v2特征的可信测试AP分别为0.1203与0.1945，支持本次修复后的输入在这一条件下获得改善；旧特征控制尚未扩为三种子，不能外推为所有宿主均有同幅度收益。[S11]')
a=heading(a,'2.8 SAT功能特征的多角度分析')
a=para(a,'本节整理已经完成并保留证据的功能特征分析。训练集全量k4提取与收尾审计已覆盖259个计划视图，1,250,510个物理节点中1,244,444个有有效内容，覆盖率99.51%。下述分布和匹配图优先复用2026年10月28日20:50冻结的221个已完成训练视图，共677,566节点、671,500个有效覆盖节点；其有效覆盖99.10%。两份统计分母不同。本节不将尚在补齐的验证和测试结果混入历史快照，也不以覆盖提高宣称检测增益。')
a=heading(a,'2.8.1 查询上下文与特征定义',3)
a=para(a,'每个组合目标采用原生物理Q状态上下文，Q为自由状态变量、QN为其反相；寄存器节点描述其D数据输入，不描述完整扫描、复位或下一状态函数。深度与cut规模均受限的完整结构前沿用于条件真值表查询。每个条件分别证明目标为0和为1，据此区分强制、不可行和未决；超时保留为unknown。当前内容为18维摘要及独立覆盖标记，不能把covered当成功能内容。')
a=table(a,'表2-7 SAT十八维内容与覆盖标记',['分组','维数','内容与解释'],[['边界规模','1','k_over_4：cut规模除以4'],['可行与强制','5','可行性已知 可行 强制 未决 不可行比例'],['确定性','2','可行条件上的确定性及其有效标记'],['输出偏置','2','被强制条件中输出1比例及有效标记；不是自然激活概率'],['条件变化','4','可比较对比例 条件变化率 有效标记 最大单输入变化率'],['完成状态','4','全域完整 受限域完整 部分强制 含unknown'],['覆盖标记','另1维','只说明该节点有合格证据；不等同于木马标签']],widths=[1.1,.5,WIDTH-1.6])
a=para(a,'条件变化率比较仅改变一个cut输入、且两种条件均有可比较输出时的变化；最大单输入变化率取各cut输入变化率的最大值。它们属于条件表敏感性，不等于对物理内部网线实施因果干预；输出1比例也依赖边界与条件集合，不能直接解释成运行时触发频率。')
a=heading(a,'2.8.2 覆盖与内容信息量',3)
a=table(a,'表2-8 冻结快照中的有效覆盖与摘要多样性',['项目','数值','解释'],[['视图 / 物理节点','221 / 677,566','仅完成的GLOBAL训练视图'],['有内容 / 无内容','671,500 / 6,066','无内容不作为功能值0'],['正例 / 覆盖正例','731 / 731','沿用冻结标签'],['负例 / 覆盖负例','676,835 / 670,769','负例含未知背景，非全体可信正常'],['18维常量列','7列','状态与有效性部分受当前cut合同固定'],['变化列 / 数值秩','11列 / 8','重复与互补；不是8维安全信息'],['摘要组合 / 前十占比','666种 / 54.87%','重复较集中，不能直接等于判别能力']],widths=[1.5,1.6,WIDTH-3.1])
a=para(a,'无可比较输入对的节点约占覆盖节点1.10%，相应变化值的零填充必须连同有效标记解释。完整全域占69.05%、完整受限域占30.95%；有效节点上的确定性恒为1与完整结构cut一致，不表示该列能区分木马。上述统计均以冻结快照为准。[S12]')
a=heading(a,'2.8.3 正负例差异与混杂控制',3)
a=picture(a,'SAT_正负例均值','图2-11 SAT主要内容在正负例上的均值差异','冻结221视图的label_distribution_reviews [S12]。变化率仅计influence_valid=1：715正例、663395负例。')
a=para(a,'条件变化率正负均值为0.5801和0.4890，高值AUC0.5926；最大单输入变化率为0.6804和0.5722，AUC0.5905。cut规模本身AUC0.6590，说明不控制门型、cut和视图时，内容差异可能部分反映组成变化。输出1比例AUC0.4877，其单调排序接近随机，但不排除与其他特征的组合信息。')
a=picture(a,'SAT_共同样本匹配','图2-12 固定共同样本后的逐层匹配分析','matched_feature_reviews的same_cohort_aggregate.csv [S13]。固定590正例、75131负例，消除逐层丢样本造成的分母变化。')
a=para(a,'匹配键为同视图、同原生driver_type、同cut大小和同目标角色；同视图同时固定宿主及实现流程。严格共同支持为252组、590正例和75131负例；另125个有效正例没有同组负例，单独记录。固定同批节点后，条件变化率AUC从0.6486降至严格匹配0.6223，最大单输入变化率从0.6175降至0.5427。前者仍有描述性区分，后者明显减弱；匹配只控制列出的变量，不能直接宣称因果独立贡献。')
a=heading(a,'2.8.4 跨宿主方向反转',3)
a=picture(a,'SAT_跨宿主反向','图2-13 严格匹配后部分特征在不同宿主上方向相反','host.csv的正例等权条件AUC [S13]。虚线0.5；s35932仅7个合格视图和58个正例。')
a=para(a,'条件变化率在rs232、s15850、s35932的条件AUC分别为0.6796、0.6248和0.3315，最后一个宿主出现反向。其最大单输入变化率AUC为0.4801，接近随机。这里的反向表示高值在该冻结匹配集合中更倾向负例，不表示SAT结果算错，也不表示功能本身由宿主决定。不同插入家族、门型、cut可行性和共同支持样本构成仍可能影响方向。')
a=para(a,'权重口径同样重要：s35932按正负节点对加权时条件变化率AUC约0.5980，而正例等权为0.3315。两种指标回答的问题不同，不能挑选有利值或把它们混用。重复等价视图也不是独立安全样本，本节不提供据此计算的显著性结论。')
a=heading(a,'2.8.5 摘要压缩与组合信息',3)
a=picture(a,'SAT_摘要重复与碰撞','图2-14 摘要重复集中与严格匹配下的正负值碰撞','profile_top20.csv及joint_overlap.csv [S12–S13]。右图分母为590个严格共同支持正例。')
a=para(a,'严格同组内，条件变化率单值与负例相同的正例为435/590，最大变化率为543/590，二维组合仍有419/590发生精确值碰撞。第二列仅让16个正例获得额外的精确值区别；这不等于16个正例可被模型稳定识别。全摘要中714/731正例的摘要也能在某些负例上找到，表明简单低维摘要存在明显信息压缩；节点邻域及安全角色仍可能提供额外信息。固定均值或乘积组合未优于严格匹配下的条件变化率单列，不能由此否定所有非线性组合。')
a=heading(a,'2.8.6 训练增量与证据边界',3)
a=picture(a,'SAT_历史内容对照','图2-15 小网表真实SAT 置换和零内容训练对照','第18轮8个小网表独立协议 [S14]。三种子、测试仅13个正例，不与当前P2-A主表直接比较。')
a=para(a,'真实SAT、层内置换和零内容AP分别为0.02098±0.00698、0.01770±0.00541和0.01596±0.00495。真实内容均值较高，但样本少、变异大且阈值召回仍为0，尚不足以确认稳定增益。另有历史跨插入实验中的置换供体存在跨划分问题，其结果只能保留为诊断，不能作为严格SAT因果增益。当前P2-A/B均未输入SAT，不得将结构模型的AP改进归因于SAT。')
a=para(a,'功能迁移方面，已有11/40条盲提取关系具备完整局部对应（训练9、验证2，测试0）；覆盖的是22个target节点，不是所有cut落点都获得同一目标函数。两条验证target均为可信正常，且其中一条全PO/D检查unknown。已有内容、对应覆盖与安全检测增益是三项独立证据，后续应沿固定输入合同做真实内容、匹配置换和零内容对照，并继续分开报告覆盖、有效性、跨宿主方向和预算定位。')
a=heading(a,'图表数据来源',2)
sources=[('S1','generate_trans/folds/hosts_bt31/views.json 与用户原文数据路线'),('S2','models/gin_net.py 与第32 35轮训练配置；历史区域监督定义'),('S3','phase2/ys/feature_encoding_v2.py 与 make_prim_feats.py；39维v2合同'),('S4','完成工作编辑前文档表1与2.1历史恒等对照；阶段论文历史实验章节'),('S5','完成工作编辑前2.2；历史G1对象统计及seed42 LOCO M0–M3归档'),('S6','10.13原语开发诊断与历史LIO归档；详细阶段论文8.3至8.6'),('S7','10.15/06_统一评测协议/N4_三向泛化_100ep/tables'),('S8','hosts_bt31/trans下rs232 injalpha与ctlmatcha的ys_id源网表；图源CSV记录SHA'),('S9','sat_cases_round8原始JSON与injalpha_cross_impl查询0；sat_boundary_round9'),('S10','_p0pilot/round34_20261029 冻结对应及模型预测差异'),('S11','_p0pilot/round33_20261029 三种子编码对照及seed42旧特征控制'),('S12','round27 feature_distribution_reviews/review_00002 与 label_distribution_reviews/review_00000'),('S13','round27 matched_feature_reviews/review_00000 冻结匹配分析与复核'),('S14','SAT第十八轮_小网表逐节点提取与三组GPU对照_20261026r.md')]
for key,text in sources:a=para(a,'['+key+'] '+text,size=9.5)
for section in D.sections:
    footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    if not footer.text:
        r=footer.add_run();fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');r._r.addnext(fld)
for p in D.paragraphs:p.paragraph_format.widow_control=True
D.save(OUT)
(H/'document_manifest.json').write_text(json.dumps(dict(source_sha=sha(SOURCE),candidate_sha=sha(OUT),figures=len(D.inline_shapes),tables=len(D.tables),paragraphs=len(D.paragraphs),original_images_preserved=1,causal_dual_analysis_in_paper=False),ensure_ascii=False,indent=2),encoding='utf-8')
print('BUILT',OUT,'figures',len(D.inline_shapes),'tables',len(D.tables))
