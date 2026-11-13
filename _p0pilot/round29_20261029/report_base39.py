from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
P=Path(__file__).resolve().parent/'base39_audit'
R=list(csv.DictReader((P/'distribution_by_split_host_recipe.csv').open(encoding='utf-8-sig')))
L=list(csv.DictReader((P/'train_positive_negative.csv').open(encoding='utf-8-sig')))
S=json.loads((P/'summary.json').read_text(encoding='utf-8'))
def row(scope,name,j):return next(z for z in R if z['scope']==scope and z['group']==name and int(z['column'])==j)
def lr(label,j):return next(z for z in L if z['label']==label and int(z['column'])==j)
def f(z,k='mean'):return float(z[k])
gate=[j for j in range(25) if f(row('split','train',j),'maximum')>0]
labels=[S['feature_names'][j].replace('gate_','') for j in gate]
fig,axs=plt.subplots(1,2,figsize=(12,4.5))
for ax,names,source,title in [(axs[0],['train','val','test'],'split','门类型组成与数据划分'),(axs[1],['positive','negative'],'label','训练正负例的门类型组成')]:
    for i,n in enumerate(names):
        vals=[100*f(row('split',n,j) if source=='split' else lr(n,j)) for j in gate]
        ax.bar(np.arange(len(gate))+(i-(len(names)-1)/2)*.24,vals,width=.23,label=n)
    ax.set_xticks(range(len(gate)),labels,rotation=35);ax.set_ylabel('节点占比 %');ax.set_title(title);ax.legend()
fig.tight_layout();fig.savefig(P/'门类型分布.png',dpi=160);plt.close(fig)
cols=list(range(25,39));fig,axs=plt.subplots(1,2,figsize=(13,6.5),gridspec_kw={'width_ratios':[2,1]})
for lab in ['positive','negative']:
    values=[(f(lr(lab,j))-f(row('split','train',j)))/max(f(row('split','train',j),'std'),1e-6) for j in cols]
    axs[0].plot(values,range(len(cols)),'o-',label=lab)
axs[0].set_yticks(range(len(cols)),[f'{j} '+S['feature_names'][j] for j in cols]);axs[0].invert_yaxis();axs[0].axvline(0,color='gray',lw=.6);axs[0].set_xlabel('相对训练总体均值的偏移 单位为训练标准差');axs[0].legend();axs[0].set_title('训练正负例结构特征均值')
aucs=[float(lr('positive',j)['auc_high']) for j in cols];axs[1].barh(range(len(cols)),aucs);axs[1].invert_yaxis();axs[1].set_xlim(0,1);axs[1].axvline(.5,color='red',ls='--');axs[1].set_yticks(range(len(cols)),[str(j) for j in cols]);axs[1].set_title('单列训练AUC 高值指向正例')
fig.tight_layout();fig.savefig(P/'训练正负例结构对比.png',dpi=160);plt.close(fig)
vary=[j for j in range(39) if f(row('split','train',j),'std')>1e-6]
groups=[('split',s) for s in ['train','val','test']]+[('recipe',s) for s in sorted({z['group'] for z in R if z['scope']=='recipe'})]
mat=np.array([[(f(row(a,b,j))-f(row('split','train',j)))/f(row('split','train',j),'std') for j in vary] for a,b in groups])
fig,ax=plt.subplots(figsize=(13,5));im=ax.imshow(mat,aspect='auto',cmap='RdBu_r',vmin=-2,vmax=2)
ax.set_xticks(range(len(vary)),[f'{j} '+S['feature_names'][j] for j in vary],rotation=65,ha='right');ax.set_yticks(range(len(groups)),[b for a,b in groups]);ax.set_title('划分与综合流程均值相对训练分布的偏移 常量列不显示');fig.colorbar(im,ax=ax,label='训练标准差');fig.tight_layout();fig.savefig(P/'划分与流程分布偏移.png',dpi=160);plt.close(fig)
lines=['# 当前39维输入分布与低AP证据分析','',f"冻结时间 {S['time']}。图节点 {S['shape'][0]:,}；训练 {S['split_counts']['train']:,}，验证 {S['split_counts']['val']:,}，测试 {S['split_counts']['test']:,}；另有3071节点不在当前388视图划分内。",'','全局坐标复用冻结SAT清单。仅统计训练标签，未读取验证或测试标签。没有新增SAT或模型训练。分布为存盘原始输入，未经过训练时归一化。宿主与流程统计采用节点权重，含重复等价视图，不是独立样本检验。','','## 39列定义和分布','','门类型数值为占比百分数。列号从0开始。','','|列|门类型|训练占比|验证占比|测试占比|训练正例占比|训练负例占比|','|---|---|---:|---:|---:|---:|---:|']
for j in range(25):lines.append('|'+str(j)+'|'+S['feature_names'][j]+'|'+'|'.join(f'{100*f(row("split",s,j)):.3f}%' for s in ['train','val','test'])+'|'+'|'.join(f'{100*f(lr(s,j)):.3f}%' for s in ['positive','negative'])+'|')
lines+=['','结构量括号内为5%与95%分位；AUC按高值指向正例，取自训练数据，未控制门型和宿主，不代表GNN测试性能。33/34具体表示寄存器边界重置后的距离，存在DFF时源点取寄存器相邻组合节点，不宜简单称为原始PI/PO距离。','','|列|特征|训练中位数 [P05,P95]|验证中位数|测试中位数|正例均值|负例均值|训练AUC|','|---|---|---|---:|---:|---:|---:|---:|']
for j in range(25,39):
    z=row('split','train',j)
    lines.append(f"|{j}|{S['feature_names'][j]}|{f(z,'median'):.3f} [{f(z,'p05'):.3f},{f(z,'p95'):.3f}]|{f(row('split','val',j),'median'):.3f}|{f(row('split','test',j),'median'):.3f}|{f(lr('positive',j)):.3f}|{f(lr('negative',j)):.3f}|{float(lr('positive',j)['auc_high']):.3f}|")
lines+=['','## 宿主和流程角度','','|范围|节点数|XOR占比|INV占比|到PO距离均值|边界重置距离均值 33列|','|---|---:|---:|---:|---:|---:|']
for a,b in [('host',s) for s in sorted({z['group'] for z in R if z['scope']=='host'})]+[('recipe',s) for s in sorted({z['group'] for z in R if z['scope']=='recipe'})]:
    lines.append(f"|{b}|{row(a,b,0)['n']}|{100*f(row(a,b,24)):.3f}%|{100*f(row(a,b,9)):.3f}%|{f(row(a,b,30)):.3f}|{f(row(a,b,33)):.3f}|")
lines+=['','## AP偏低的解释及证据边界','','1. 训练829个正例对1249681个负例，正例率0.06629%，约1比1507。即使召回率50%、FPR仅0.1%，按该比例估算精确率也仅约24.9%。这是指标困难性的解释，不是模型失败的唯一原因。正式AP为逐视图宏平均，不能用全训练池化正例率直接当作其随机基线。','','2. 18个门类型列全零，加上组合环标记全零和SCC大小恒为log(2)，共有20个训练常量列；只有19列变化，且门类型one-hot存在和为1的约束。这意味着名义39维的信息量有限，但常量列本身不直接导致AP下降，简单删列不能保证增益。','','3. 352/829即42.46%的训练正例与至少一个训练负例具有完全相同39维输入；512个正例唯一向量中192个也见于负例。单节点属性不足以唯一判断安全角色；这不是GNN不可分的证明，邻域仍可能不同。','','4. XOR在训练/验证/测试占比分别4.627%/1.505%/0.661%，PO距离中位数12/17/9；AIG与NAND流程中XOR和MUX编码占比为0，而INV比例约56.1%和50.8%。源实现里的显式算子形态发生变化，门型与距离捷径难以直接迁移。宿主恰与当前划分高度绑定，不能将观察到的差异只归因于某一种因素。ys_nand配方名不等于图输入一定保留NAND类别；此处只报告存盘39维编码。','','5. 单列正负例结构特征重叠明显，例如degree高值AUC约0.506，input_ports约0.466；到PO距离按低值指向正例可达约0.780，说明有局部定位线索，但这些是训练关联，可能依赖插入位置、宿主和实现。不能依据此表按测试结果重选方向或特征。','','6. 基础特征做z-score并裁剪到正负10时，稀有MUX和SDFFSR列会饱和。全图拟合方案中测试共有6719个“节点列”值被裁剪，其中6555来自MUX列。二值门型裁剪后仍保留有无区别，不能将其解释为SAT稀疏内容坍缩，也不能据此认定是低AP主因。部分历史主结果的run_config未保存norm_fit，当前代码默认all，全图无标签归一化属于传导设定；严格归纳评测应单独固定训练拟合口径，不应把默认值当成每个旧run的已核实配置。','','7. 固定折主结果：39维双分支A2节点AP 0.1425±0.0221；加入cone5后的A3为0.1410±0.0314；在A3上加入区域监督A5为0.1850±0.0272。上下文与区域监督的收益有既有实验支持，但容量未严格匹配，不能仅用分布统计断言每项原因的因果贡献。小网表SAT试验的AP约0.021属于另一协议，不能与上述主结果混为同一个“当前AP”。','','## 后续优先事项','','优先复核特征编码、不可达距离哨兵与归一化合同，在已有划分中诊断稳定性；保留双分支及区域上下文，待当前SAT收尾后做真实内容、匹配置换和元数据对照。利用区域内排名、困难负例和可靠跨实现对象检查错误来源。不要因为单列AUC较高就删改特征，也不要假定提高SAT覆盖一定提高AP。','','详细数据见同目录CSV；本轮只新增分析产物，未修改训练、数据生成或SAT运行脚本。']
(P/'39维特征分布与AP分析.md').write_text('\n'.join(lines),encoding='utf-8')
print(P/'39维特征分布与AP分析.md')
