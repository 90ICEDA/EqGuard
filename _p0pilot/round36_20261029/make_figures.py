"""Static research figures from frozen CSV/raw evidence; no training or SAT imports."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import json,re,hashlib,collections,ctypes
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;OUT=H/'figures';OUT.mkdir(exist_ok=True)
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'svg.fonttype':'none'})
T=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables';R27=ROOT/'_p0pilot/round27_20261027';BLUE='#285d85';TEAL='#248b83';ORANGE='#c77b3a';GREY='#667782';RED='#b04e50';MAN=[]
def save(fig,name,source,data=None):
    fig.savefig(OUT/(name+'.png'),dpi=240,bbox_inches='tight',facecolor='white');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig)
    if data is not None:pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    MAN.append(dict(name=name,source=source,path=str((OUT/(name+'.png')).relative_to(ROOT))))
def box(ax,x,y,w,h,text,color=BLUE,fs=12):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.012,rounding_size=.015',facecolor=color+'14',edgecolor=color,lw=1.3));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fs)
def arrow(ax,a,b):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=15,color=GREY,lw=1.4))
def diagrams():
    f,ax=plt.subplots(figsize=(9,4));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    for i,(title,body) in enumerate([('规则表阶段','局部门展开\n保留生成血缘'),('算子与规则表阶段','decomp / balance\nrefactor / resub'),('Yosys综合阶段','id / opt / ABC\nAIG / NAND')]):
        x=.02+i*.335;box(ax,x,.57,.29,.30,title+'\n'+body,fs=12)
        if i<2:arrow(ax,(x+.29,.72),(x+.333,.72))
    box(ax,.06,.08,.88,.28,'可信基准：正常匹配对照＋插入来源＋CEC记录＋固定留出\n当前388视图：训练259　验证65　测试64',TEAL,13)
    for x in (.16,.49,.83):arrow(ax,(x,.56),(x,.38))
    save(f,'图1_数据路线','10.15/完成工作.docx 原数据路线；hosts_bt31/views.json')
    f,ax=plt.subplots(figsize=(9,4.8));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    box(ax,.02,.57,.23,.30,'原始网表与等价视图\n同源来源及标签\n正确解析连接与别名',BLUE)
    box(ax,.34,.74,.27,.17,'前29维\n门型与局部连接',BLUE)
    box(ax,.34,.40,.27,.17,'后10维\n距离 邻域 SCC',TEAL)
    arrow(ax,(.25,.73),(.34,.82));arrow(ax,(.25,.66),(.34,.49))
    box(ax,.70,.55,.27,.27,'共享视图编码\n单分支或双分支融合\n节点木马概率',BLUE)
    arrow(ax,(.61,.82),(.70,.74));arrow(ax,(.61,.49),(.70,.63))
    box(ax,.27,.04,.67,.20,'分类监督只使用可信物理节点\n区域监督为独立辅助项　SAT输入须另做内容对照',ORANGE)
    arrow(ax,(.84,.55),(.84,.26))
    save(f,'图1_方法框架','models/gin_net.py；round32/35配置；历史区域监督定义')
    f,ax=plt.subplots(figsize=(9,4.4));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    box(ax,.02,.57,.30,.32,'基础39维\n25维库单元类别\n14维结构拓扑',BLUE,14)
    box(ax,.37,.57,.28,.32,'原语21维候选\n7维原语构成\n相同14维结构拓扑',TEAL,13)
    box(ax,.70,.57,.28,.32,'SAT独立内容\n18维功能摘要\n1维覆盖标记',ORANGE,13)
    box(ax,.04,.08,.92,.27,'14维已包含：局部连接与PI/PO边界4维＋距离与两步邻域4维\n＋寄存器边界4维＋组合环标记及SCC规模2维\n结构可达性是代理　条件真值表变化不等于物理因果影响',GREY,12)
    save(f,'图1_特征体系','feature_encoding_v2.COLS；make_prim_feats；boundary_repr.COLS')
def experiments():
    data=pd.DataFrame(dict(group=['G1','G2','G3','G4'],same=[.5472,.5986,.6026,.6144],same_sd=[.1518,.1495,.1409,.1396],loco=[.1221,.1512,.1446,.1448],loco_sd=[.0332,.0408,.0395,.0329]))
    f,ax=plt.subplots(figsize=(8.5,3.7));x=np.arange(4)
    ax.bar(x-.18,data.same,.34,yerr=data.same_sd,capsize=4,label='同源d2',color=BLUE);ax.bar(x+.18,data.loco,.34,yerr=data.loco_sd,capsize=4,label='历史LOCO',color=TEAL)
    ax.set(xticks=x,xticklabels=data.group,ylabel='节点 AP',ylim=(0,.85));ax.legend(frameon=False,ncol=2);ax.grid(axis='y',alpha=.2);save(f,'图2_增广与泛化','完成工作.docx 表1；历史d2三种子',data)
    f,ax=plt.subplots(figsize=(8.5,3.5));xx=np.arange(3);v=[.0111,.0926,.1300];ax.bar(xx,v,color=[BLUE,ORANGE,RED]);ax.set(xticks=xx,xticklabels=['一对一','一对多 拆分','多对一 合并'],ylabel='平均预测漂移',ylim=(0,.16))
    for i,y in enumerate(v):ax.text(i,y+.004,f'{y:.4f}',ha='center')
    ax.text(.02,.96,'G1历史对象统计；rs232木马相关对象拆分比例约41.99%',transform=ax.transAxes,va='top',fontsize=10.5);save(f,'图2_对象粒度与漂移','完成工作.docx 2.2；历史G1对象统计',dict(mapping=['1:1','1:N','N:1'],drift=v))
    f,axes=plt.subplots(1,2,figsize=(9,3.7));names=['M0','M1 域对抗','M3 对象一致性'];ap=[.1642,.2006,.1250];gap=[.0272,.0240,.0203]
    for ax,v,title in zip(axes,[ap,gap],['节点AP 越高越好','配对MAE 越低越一致']):
        ax.bar(np.arange(3),v,color=[GREY,BLUE,TEAL]);ax.set(xticks=np.arange(3),xticklabels=names,title=title);ax.tick_params(axis='x',labelsize=10);ax.set_ylim(0,max(v)*1.3)
        for i,y in enumerate(v):ax.text(i,y+max(v)*.035,f'{y:.4f}',ha='center',fontsize=10)
    f.tight_layout();save(f,'图2_域对抗与一致性','历史seed42 LOCO；不是新v2协议',dict(model=names,AP=ap,MAE=gap))
    f,ax=plt.subplots(figsize=(8.5,3.7));x=np.arange(3);v=[.6611,.0554,.1562];w=[.9449,.3824,.1970]
    ax.bar(x-.18,v,.34,yerr=[.3775,.0164,.0167],capsize=4,color=BLUE,label='旧39维');ax.bar(x+.18,w,.34,yerr=[.0157,.1308,.0489],capsize=4,color=TEAL,label='历史原语配置')
    ax.set(xticks=x,xticklabels=['decomp3','ys_rt','ys_abc'],ylabel='开发集逐视图AP',ylim=(0,1.1));ax.legend(frameon=False);save(f,'图2_历史原语编码','10.13历史rs232开发集；7原语+筛选5结构；三种子',dict(recipe=['decomp3','ys_rt','ys_abc'],base=v,primitive=w))
    f,ax=plt.subplots(figsize=(8.5,3.6));labels=['LOCO\n1个宿主留出折','LRO\n5个流程留出折','LIO\n5个实例模板组'];v=[.1408,.1484,.1602];sd=[.0301,.0385,.0226]
    ax.bar(np.arange(3),v,yerr=sd,capsize=5,color=[BLUE,TEAL,ORANGE]);ax.set(xticks=np.arange(3),xticklabels=labels,ylabel='逐视图AP',ylim=(0,.23));ax.text(.01,.96,'独立性与折数不同，不能用均值排序泛化难度',transform=ax.transAxes,va='top',fontsize=10.5);save(f,'图2_历史三向泛化','完成工作.docx 2.5；N4_三向泛化_100ep历史汇总',dict(direction=['LOCO','LRO','LIO'],AP=v,std=sd))
    gain=pd.DataFrame(dict(group=['G2','G3','G4'],identity=[.0518,.0531,.0563],rewrite=[.0514,.0555,.0672]));f,ax=plt.subplots(figsize=(8.5,3.2));x=np.arange(3)
    ax.bar(x-.18,gain.identity,.34,label='恒等视图',color=GREY);ax.bar(x+.18,gain.rewrite,.34,label='真实变换',color=BLUE);ax.set(xticks=x,xticklabels=gain.group,ylabel='相对G1的AP增量',ylim=(0,.085));ax.legend(frameon=False,ncol=2);save(f,'图2_恒等视图增益','完成工作.docx 2.1历史恒等对照',gain)
def circuits():
    # Draw two genuine MUX instances, preserving their recorded pin connections.
    f,axes=plt.subplots(2,1,figsize=(9,5.3));data=[]
    for ax,view,needle,title in [(axes[0],'rs232t1000__injalpha_d1_s42__ys_id','g_rec_readyH_2','木马载荷选择器'),(axes[1],'rs232t1000__ctlmatcha_d1_s42__ys_id','g__U291.Y_332','正常对照中的MUX')]:
        src=ROOT/'generate_trans/folds/hosts_bt31/trans'/(view+'.v');text=src.read_text();line=next(x for x in text.splitlines() if x.startswith('MX2X1_RS '+needle+' '));ports={p:n.strip().lstrip('\\') for p,n in re.findall(r'\.(\w+)\(([^)]+)\)',line)}
        ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off');ax.set_title(title,loc='left',fontsize=15,pad=3)
        box(ax,.42,.20,.22,.60,'MUX\n节点'+('37155' if 'injalpha' in view else '11480'),RED if 'injalpha' in view else TEAL,14)
        for pin,y in [('A',.73),('B',.48),('S0',.23)]:
            label=ports[pin].replace('TrojanAHJ.','HJ.');ax.text(.02,y,pin+'  '+label,va='center',fontsize=14);arrow(ax,(.31,y),(.42,y))
        arrow(ax,(.64,.49),(.78,.49));ax.text(.79,.49,'Y\n'+ports['Y'],va='center',fontsize=13)
        data.append(dict(view=view,cell=needle,type='MX2X1_RS',source_sha=hashlib.sha256(src.read_bytes()).hexdigest(),**ports))
    f.tight_layout();save(f,'图2_真实木马与正常MUX','两份源网表实际MX2X1_RS实例；局部相似不等于功能与安全等价',data)
    # Proven selector points; show only depth2 real data cone, not speculative whole-region mapping.
    tables=T/'sat_boundary_round9';parts=pd.read_csv(tables/'case_participants.csv');rows=[]
    f,axes=plt.subplots(1,2,figsize=(10,4.5))
    for ax,recipe in zip(axes,['ys_id','ys_abc']):
        view='rs232t1000__injalpha_d1_s42__'+recipe;raw=T/'sat_cases_round8'/view/'raw.json';m=next(iter(json.loads(raw.read_text())['modules'].values()));part=parts[(parts.view==view)&(parts.role=='selector')].iloc[0];root=int(part.bit)
        drivers={};ins={};typ={}
        for name,c in m['cells'].items():
            con=c['connections'];dt=c['type'];outs=['Q','QN'] if 'DFF' in dt.upper() else ['Y'] if dt in ('MX2X1_RS','$and','$mux','$not','$or','$xor') else ['QN'] if dt=='INVX0' else ['Q']
            for pin in outs:
                if pin in con:
                    bit=con[pin][0];drivers[bit]=name;typ[bit]=dt
                    ins[bit]=[] if 'DFF' in dt.upper() else [b for p,bs in con.items() if p not in outs for b in bs if isinstance(b,int)]
        levels={root:2};edges=[];pending=[(root,2)]
        while pending:
            bit,depth=pending.pop()
            if depth==0:continue
            for b in sorted(set(ins.get(bit,[]))):
                edges.append((b,bit))
                if b not in levels:levels[b]=depth-1;pending.append((b,depth-1))
        positions={}
        for level in range(3):
            bits=sorted(b for b,l in levels.items() if l==level)
            for j,b in enumerate(bits):positions[b]=(.12+level*.36,(j+1)/(len(bits)+1))
        ax.axis('off');ax.set(xlim=(0,1),ylim=(0,1));ax.set_title(recipe+' 选择条件局部真实连接',fontsize=14)
        for a,b in edges:arrow(ax,positions[a],positions[b])
        for bit,(x,y) in positions.items():
            label=(typ.get(bit,'边界').replace('AND2X2','AND').replace('OR2X1','OR').replace('INVX0','INV').replace('SDFFSRX1_RS','DFF'))+'\nb'+str(bit)
            ax.text(x,y,label,ha='center',va='center',fontsize=15,bbox=dict(boxstyle='round,pad=.3',facecolor='#e8f1f5',edgecolor=BLUE))
            rows.append(dict(view=view,bit=bit,cell=drivers.get(bit,''),type=typ.get(bit,'boundary'),root=bit==root))
    f.suptitle('同一selector输出已有等价证明\n仅展示向前两层，不表示内部节点一一对应',fontsize=14);f.tight_layout(rect=(0,0,1,.87));save(f,'图2_已证明边界变换前后','round8 proof injalpha_cross_impl q0；round9 selector完整区域20→10门',rows)
    d=pd.read_csv(ROOT/'_p0pilot/round34_20261029/main_target_prediction_pairs.csv');v=d[d.split=='val'];f,ax=plt.subplots(figsize=(8.5,3.7));x=np.arange(3)
    means=[v[v.seed==s].absolute_difference.mean() for s in (42,1,2)];ax.bar(x,means,color=BLUE);ax.set(xticks=x,xticklabels=['seed42','seed1','seed2'],ylabel='预测概率差 MAE',ylim=(0,.17))
    for i,y in enumerate(means):ax.text(i,y+.004,f'{y:.4f}',ha='center')
    ax.text(.02,.96,'仅验证2对可信正常target；不代表测试木马稳定性',transform=ax.transAxes,va='top',fontsize=10.5);save(f,'图2_可靠对应预测稳定性','round34冻结验证预测和功能点对应',dict(seed=[42,1,2],MAE=means,pairs=[2]*3))
def sat_figures():
    base=R27/'feature_distribution_reviews/review_00002';label=R27/'label_distribution_reviews/review_00000';match=R27/'matched_feature_reviews/review_00000'
    cols=pd.read_csv(base/'column_statistics.csv');raw=pd.read_csv(label/'feature_comparison.csv');a=raw[(raw.scope=='all')&(raw.group=='all')]
    keys=['ones_on_forced','change_on_comparable','max_input_influence'];ch=['输出1比例','条件变化率','最大单输入变化率'];f,ax=plt.subplots(figsize=(8.5,3.6));x=np.arange(3)
    pos=[a[a.column==k].iloc[0].pos_mean for k in keys];neg=[a[a.column==k].iloc[0].neg_mean for k in keys]
    ax.bar(x-.18,pos,.34,color=RED,label='正例');ax.bar(x+.18,neg,.34,color=BLUE,label='负例');ax.set(xticks=x,xticklabels=ch,ylabel='有效节点均值',ylim=(0,.82));ax.legend(frameon=False,ncol=2);save(f,'SAT_正负例均值',str(label.relative_to(ROOT)),dict(feature=keys,pos=pos,neg=neg))
    co=pd.read_csv(match/'same_cohort_aggregate.csv');scope=['all','host','view','view_gate','view_gate_k'];f,ax=plt.subplots(figsize=(8.5,3.8))
    for score,color,text in [('change',BLUE,'条件变化率'),('max_change',ORANGE,'最大单输入变化率')]:
        values=[co[(co.scope==s)&(co.score==score)].iloc[0].pos_weighted_auc for s in scope];ax.plot(range(5),values,'o-',color=color,label=text)
    ax.axhline(.5,color=GREY,ls='--',lw=1);ax.set(xticks=range(5),xticklabels=['同批总体','同宿主','同视图','同视图门型','同视图门型cut'],ylabel='正例等权条件AUC',ylim=(.45,.72));ax.legend(frameon=False,fontsize=10);ax.tick_params(axis='x',labelsize=10);save(f,'SAT_共同样本匹配',str(match.relative_to(ROOT)),co)
    host=pd.read_csv(match/'host.csv');hosts=['rs232t1000','s15850t100','s35932t200'];f,ax=plt.subplots(figsize=(8.5,3.9));x=np.arange(3)
    for offset,score,color,text in [(-.18,'change',BLUE,'条件变化率'),(.18,'max_change',ORANGE,'最大单输入变化率')]:
        values=[host[(host.scope==h)&(host.score==score)].iloc[0].pos_weighted_auc for h in hosts];ax.bar(x+offset,values,.34,color=color,label=text)
        for i,y in enumerate(values):ax.text(i+offset,y+.015,f'{y:.3f}',ha='center',fontsize=10)
    ax.axhline(.5,color=GREY,ls='--');ax.set(xticks=x,xticklabels=['rs232\n283正例','s15850\n249正例','s35932\n58正例'],ylabel='严格匹配条件AUC',ylim=(0,.85));ax.legend(frameon=False,ncol=2,fontsize=10);save(f,'SAT_跨宿主反向',str(match.relative_to(ROOT)),host)
    f,axes=plt.subplots(1,2,figsize=(9,3.5));top=pd.read_csv(base/'profile_top20.csv');axes[0].bar(top['rank'][:10],top.fraction[:10]*100,color=BLUE);axes[0].set(xlabel='摘要频次排名',ylabel='覆盖节点占比 %',title='前10种摘要占54.87%')
    collision=[435/590,543/590,419/590];axes[1].bar(np.arange(3),np.array(collision)*100,color=[BLUE,ORANGE,TEAL]);axes[1].set(xticks=np.arange(3),xticklabels=['条件变化','最大变化','二维组合'],ylabel='与同组负例值碰撞 %',ylim=(0,105));axes[1].tick_params(axis='x',labelsize=10)
    for i,v in enumerate(collision):axes[1].text(i,v*100+2,f'{v:.1%}',ha='center',fontsize=10)
    f.tight_layout();save(f,'SAT_摘要重复与碰撞',str(base.relative_to(ROOT))+'；严格匹配590正例',dict(feature=['change','max','joint'],collision=collision))
    f,ax=plt.subplots(figsize=(8.5,3.5));names=['零内容','层内置换','真实SAT'];v=[.015955,.017704,.020977];sd=[.004953,.005406,.00698];ax.bar(range(3),v,yerr=sd,capsize=5,color=[GREY,ORANGE,BLUE]);ax.set(xticks=range(3),xticklabels=names,ylabel='历史小网表测试AP',ylim=(0,.035));ax.text(.01,.98,'8个小网表；3种子；测试13正例；不能作为全量增益结论',transform=ax.transAxes,va='top',fontsize=10);save(f,'SAT_历史内容对照','SAT第十八轮说明；小样本独立协议',dict(arm=names,AP=v,std=sd))
    # Export the complete frozen content dictionary for the Word authoring stage.
    export=dict(snapshot=json.loads((base/'distribution.json').read_text()),feature_columns=cols.to_dict('records'),label_means=a.to_dict('records'),host=host.to_dict('records'))
    (H/'sat_evidence_extract.json').write_text(json.dumps(export,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    diagrams();experiments();circuits();sat_figures();(H/'figure_manifest.json').write_text(json.dumps(MAN,ensure_ascii=False,indent=2),encoding='utf-8');print('FIGURES',len(MAN))
