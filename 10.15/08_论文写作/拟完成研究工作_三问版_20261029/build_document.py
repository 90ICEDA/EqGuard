from pathlib import Path
import json, hashlib
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE=Path(__file__).resolve().parent
SECTIONS=[
('intro','后续研究将围绕三个问题展开：真正的功能关系能否帮助定位木马，同一木马更换等价实现后能否保持稳定，以及结构相似的正常逻辑能否避免误报。在现有等价网表数据集、双分支GNN和区域监督模型基础上，进一步完善真实功能证据、跨实现可靠对应与安全行为对照，分别检验功能信息的定位价值、模型对实现变化的鲁棒性及其对恶意行为的区分能力。'),
('heading','一 真正的功能关系能否帮助定位木马'),
('body','针对现有功能分支中结构统计与真实布尔语义混合、局部SAT摘要可能丢失信息的问题，拟完成训练、验证和测试视图的既定SAT特征提取与质量核验。提取过程沿用原生物理寄存器状态上下文和统一查询合同，分别记录有效覆盖、不可比较、超时与未知状态，并核对特征与图节点的坐标对应。候选选择与提取过程不依赖测试正例位置，特征归一化参数仅由训练集合确定，防止覆盖标记、数据划分或节点附着错误形成虚假增益。'),
('body','在此基础上，进一步研究局部功能信息如何形成对木马定位有价值的表示。比较紧凑统计摘要、逐输入变化统计和完整局部状态表，分析摘要压缩导致的特征碰撞及跨宿主差异；在同宿主、同视图、同门型和同cut大小等条件下，对比正负例特征，判断现有条件变化率和最大单输入变化率是否提供结构统计之外的信息。对于控制信号影响目标、影响传播至主输出或寄存器输入等关系，优先复用已有证据，在缺失处开展小范围验证，区分直接功能影响、条件相关性与结构可达性，不将局部变化率等同于恶意行为证据。'),
('body','功能内容的有效性将通过严格训练对照确认。以现有双分支及区域监督模型为基础，在相同数据划分、输入宽度、初始化和训练预算下，比较元数据基线、真实SAT内容、分组置换SAT内容和零内容；置换仅在各自数据划分内按可比条件执行，并保持覆盖及有效性标记可比。重点报告逐视图节点AP、AUC、Recall@1%和Recall@5%，同时考察DFF与PO区域指标及区域内部定位。只有真实内容相对置换内容表现出可重复增益，才将其作为功能信息有助于定位的证据；若未获得稳定增益，则分析局部边界、表示压缩和安全上下文不足等原因，明确适用范围。'),
('heading','二 同一木马更换等价实现后能否保持稳定'),
('body','针对逻辑综合导致门级节点拆分、合并、消失及信号重命名的问题，拟继续完善跨实现信号与区域的可靠对应。复用现有信号追踪、边界保留和标签溯源结果，在ys_id、ys_abc、ys_aig和ys_nand等实现之间，通过形式等价检查验证信号功能关系；对于无法建立一对一节点映射的情况，转向输入输出边界能够对应的逻辑区域。验证时统一状态、输入约束及信号极性，单独记录边界缺失、别名歧义与证明未知，避免将名称相同或旧有proved标记直接视为可靠对应。'),
('body','跨实现功能等价与安全角色一致将分别核验。结合木马插入记录和实际功能影响证据，将对应对象划分为可信木马、可信正常、混合及未知，仅使用满足训练集合归属、可靠对应和安全角色要求的样本构建一致性监督。进一步统计唯一对象口径的信号匹配率、区域匹配率、可信木马标签覆盖率和有效训练配对数，明确无法对应的对象占比，避免少量成功案例掩盖整体覆盖不足。'),
('body','模型层面，在真实功能内容通过前述检验后，逐步引入基于可靠对应的一致性损失，比较加入前后的节点检测性能、配对预测MAE、预测翻转率和跨实现AP变化，并使用按原始对象等权的统计减轻拆分数量造成的偏差。泛化评估重点采用未见综合流程留出，同时明确区分同一源实例的未见实现与独立源实例上的未见流程。拟选取同一真实木马的两种CEC等价实现，绘制包含触发与载荷重写、可靠边界对应和风险分数的真实电路图，分析模型在哪些实现变化下保持稳定、在哪些变化下发生失效。稳定性改进须与定位性能同时考察，防止模型通过输出趋同而损失检测能力。'),
('heading','三 结构相似的正常逻辑能否避免误报'),
('body','针对木马与正常逻辑可能共享MUX、XOR、低活动率或局部异常结构的问题，拟完善结构匹配的正常对照与安全角色证据。优先从既有对照中选择真实连接到输出、具有可信正常标签的逻辑，并与具有插入记录和实际功能影响证据的木马逻辑配对；在宿主、实现配方、局部门型及规模等条件上尽量保持可比。行为等价正常对照和失效载荷对照分别分析，悬空或失效结构仅作为辅助对照，避免模型通过“是否连接输出”等简单线索完成区分。'),
('body','在样本合同成立后，研究木马与正常行为区分损失能否补充跨实现一致性约束。按照结构GNN、双分支GNN、加入真实SAT功能内容、进一步加入可靠对应一致性、再加入行为区分损失的顺序开展消融，区域监督的设置在各组中保持可比，并设置容量和训练预算尽量匹配的对照。所有配对只服务于规定的数据划分，记录有效样本数及损失实际激活情况，不以配置开关代替模块有效性的证据。'),
('body','评价时，在验证集确定并冻结阈值，分别报告正常节点误报率、正常网表或视图报警比例，以及木马召回率，避免以不同层级的低误报互相替代。结合未见宿主、未见综合流程和未见插入机制开展检验，其中插入组留出需核实触发与载荷机制是否实际不同，不能仅以模板编号代替机制差异。另选结构相似的木马与正常案例，导出GNN输入、逐层聚合、隐藏表示和风险分数，通过局部保功能重写及特征消融检查模型判断依据，形成第二张真实机制图，解释结构一致性与恶意行为区分之间的关系。'),
('closing','上述研究将按功能证据核验、可靠对应构建和安全行为对照的依赖关系推进。关键模型实验计划采用seed 42、1、2和统一训练预算，训练继续使用ginvenv_gpu；结果报告均值与样本标准差，并附视图数、正例数、CEC状态、可信标签覆盖、功能证据覆盖及运行成本。只有相应样本与实验均通过验证，才将完整FG-HTL作为完成模型报告；尚未验证的模块、无增益结果和失败案例将如实保留，为论文结论提供明确边界。')
]

def main():
    doc=Document(); sec=doc.sections[0]
    sec.page_width=Inches(8.2677);sec.page_height=Inches(11.6929)
    sec.top_margin=sec.bottom_margin=Inches(.82)
    sec.left_margin=sec.right_margin=Inches(.9)
    for name in ['Normal','Title','Heading 1']:
        st=doc.styles[name];st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0)
        st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体' if name=='Normal' else '黑体')
    for st in doc.styles:
        for border in list(st.element.iter(qn('w:pBdr'))):
            border.getparent().remove(border)
    n=doc.styles['Normal'];n.font.size=Pt(12)
    n.paragraph_format.line_spacing=1.45;n.paragraph_format.space_after=Pt(6)
    n.paragraph_format.first_line_indent=Pt(24)
    title=doc.add_paragraph('拟完成的研究工作','Title');title.style.font.size=Pt(18)
    title.paragraph_format.space_after=Pt(14)
    title.paragraph_format.first_line_indent=Pt(0)
    for typ,text in SECTIONS:
        if typ=='heading':
            p=doc.add_paragraph(text,'Heading 1');p.paragraph_format.first_line_indent=Pt(0)
            p.style.font.size=Pt(13);p.paragraph_format.space_before=Pt(12);p.paragraph_format.space_after=Pt(7)
        else:
            p=doc.add_paragraph(text);p.paragraph_format.widow_control=True
    footer=sec.footer.paragraphs[0];footer.alignment=1
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
    path=HERE/'拟完成的研究工作_围绕三问展开.docx';doc.save(path)
    (HERE/'正文.md').write_text('# 拟完成的研究工作\n\n'+'\n\n'.join(('## ' if t=='heading' else '')+s for t,s in SECTIONS),encoding='utf-8')
    src=HERE.parents[1]/'10.22新说明.txt'
    (HERE/'来源说明.json').write_text(json.dumps({'source':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'organization':'10.22新说明末尾三问','scope':'拟完成研究工作独立替换稿 未改动原阶段报告和研究脚本','characters':sum(len(s) for _,s in SECTIONS)},ensure_ascii=False,indent=2),encoding='utf-8')
    print(path)
if __name__=='__main__':main()
