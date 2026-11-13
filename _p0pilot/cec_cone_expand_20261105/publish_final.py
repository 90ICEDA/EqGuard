"""Publish final data audit and saved-prediction diagnostic, without training."""
from pathlib import Path
import csv
import datetime
import json
from final_pair_adapter import read, digest

O = Path(__file__).resolve().parent
R = O.parents[1]
D = R / '10.15/00_说明'

def mdtable(records, fields):
    return '\n'.join(['|'+'|'.join(fields)+'|', '|'+'|'.join(['---']*len(fields))+'|'] +
                     ['|'+'|'.join(str(x[k]) for k in fields)+'|' for x in records])

def main():
    assert not (O/'FINAL_PUBLISHED.json').exists()
    v = read(O/'FINAL_VERIFIED.json')
    b = read(O/'OFFLINE_BASELINE_COMPLETE.json')
    for path, checksum in read(O/'FINAL_COMPLETE.json')['files'].items():
        assert digest(R/path) == checksum
    source = list(csv.DictReader((O/'FINAL_source_summary.csv').open(encoding='utf-8-sig')))
    metrics = []
    for z in b['metrics']:
        metrics.append(dict(划分=z['split'], 根标签=z['stratum'], 源对象=z['sources'], 配对=z['pairs'],
                            概率MAE=f"{z['absolute_drift_mean']:.4f} ± {z['absolute_drift_seed_sd']:.4f}",
                            翻转率=f"{100*z['flip_mean']:.2f}%", 两侧均正确=f"{100*z['both_correct_mean']:.2f}%",
                            两侧均错=f"{100*z['both_wrong_mean']:.2f}%"))
    target = D/'等价锥最终加载核验与既有模型稳定性诊断_20261105.md'
    assert not target.exists()
    text = '''# 等价锥最终加载核验与既有模型稳定性诊断

日期：2026-11-05。继续此前“同源对象、明确边界、CEC证明”的工作。本轮完成最终数据收尾，并复用现有模型预测开展稳定性诊断；0训练、0模型前向、0新增SAT。所有旧图、特征、标签、预测、证明和阶段产物保留，未移动或删除文件。

## 1. 结论

最新主池476对全部通过最终适配器加载预检，训练382、验证94、测试0；对应437个连通锥对象，训练343、验证94。独立制造源对象训练8、验证3，宿主训练3、验证1。另1个仅完整枚举的训练对单列，不混入CEC主池。

相比中断时的475对合同，新增的验证正根已经实际接入，不再只停留在final_pairs的统计中。新适配器为final_pair_adapter.py，合同为FINAL_CONTRACT.json。旧pair_adapter.py、CEC_POOL_CONTRACT.json及全部旧阶段文件均保持。

476对是功能等价观察边，不是476个独立电路或木马实例，也不是476个正例。主池正根训练8对、验证1对，训练正根仅来自4个制造源对象。源对象等权和连通锥等权可避免把重复配对当独立样本，但不能消除共享背景、共享内部节点造成的相关性。

## 2. 最终证据及加载核验

- 重新计算477个候选的canonical身份，采用同源对象、PI/Q上下文、源网表SHA、输出单元和引脚去重；无重复观测边，无测试配对，无训练/验证源对象交叉。
- 从23个原raw模型重新提取915个锥，逐一核对内部单元、成员图坐标、根row/bit/pin、PI/Q叶边界、常量及完整物理成员；现39维v3特征落点有限且正确。
- 重新核对35个既有查询的model/run.ys/run.log绑定哈希、精确query_id、SAT命令和对应SUCCESS日志块。参数只包含既定prove、timeout及显示/反例保存选项，无额外set/assume约束。
- 对主池所有证明引用核对实际观察向量位，产生486条证明投影记录。联合PO/D证明只投影到其明确包含的观察位，未据此推断任意内部网相等。新增正根6条选样证书引用逐项核验，重复观察位仍只计1对。
- 最初的源绑定/模型再生成与raw总函数检查受旧输入哈希约束保留；本次对native模型再次生成比对，并检查共享env连接。第8轮机制模型保留原始已绑定证据、自然intervention=0上下文，不把干预查询混为自由PI/Q证明。
- 全部476对非恒定；386对有完整小边界枚举，90对有输出0/1见证。两见证只证明非恒定，不代替大锥CEC。
- 适配器拒绝all等混合划分，保留精确root_bit/pin和只读成员数组，不向功能训练payload提供y/trusted或整锥安全标签。训练功能数据资格只在train为真，val只评价。
- 按每划分“源对象等权、该源的上下文/连通锥对象等权、该对象已观测边等权”重算权重，各划分和为1。未展开传递闭包来制造更多边。

数据预检完成不等于训练程序已经实现。功能头、防坍缩、真实/置换/零一致性对照和完整训练runner仍待单独实现；FINAL_VERIFIED.training_ready为false。

## 3. 每源规模

'''
    text += mdtable(source, ['split','source_object','pairs','components','unique_cones','unique_physical_members','max_cone_membership','positive_root_pairs'])
    text += '''

max_cone_membership是同源内某物理节点出现在多少个不同锥中的最大次数。范围2至19，说明连通分量不同的锥仍可共享内部逻辑。不能用437分量当437个独立统计观测。效应及不确定性优先按制造源对象报告，三种子仅反映初始化波动。

## 4. 配对是否真的含实现变化

'''
    text += mdtable(b['features'], ['split','pairs','sources','root39_equal','root25_equal','root14_equal','same_cell_histogram','different_cell_count'])
    text += '''

训练327/382对、验证82/94对的组合单元数不同，存在明显实现变化；根39维完全相同仍有训练65对、验证46对。门型直方图相同不能证明拓扑同构，根输入相同也不能证明邻域或模型隐藏表示相同。该表只用来描述配对难度，不能按已有预测漂移重新筛选主池或权重。

## 5. 复用较强现有模型后的稳定性

仅复用control_v3_eligible_20261104下改进双分支39维v3/H、200更新、seed42/1/2的已保存预测。核对模型检查点、特征合同、归一化和预测哈希；没有重新前向，也没有读取测试预测。阈值固定使用各种子已有val_recall80阈值。这里H是已存在的旧H监督版本，不是后来五组公平实验G0，不能混同。

每源先按其连通锥/边权重汇总，再对源等权。正负根分层时只在有该类的源内对既定权重条件归一化，明确报告有效源数。MAE为三种子均值±样本标准差，其余列为三种子均值；并非跨宿主置信区间。

'''
    text += mdtable(metrics, ['划分','根标签','源对象','配对','概率MAE','翻转率','两侧均正确','两侧均错'])
    text += '''

训练诊断属于训练内结果，不能作泛化证据。验证全部94对总体MAE约0.0592、翻转5.71%，仍存在等价实现的检测波动。两侧都给低分也可很稳定，所以同时报告两侧均正确和均错，不把低漂移单独当作成功。

### 5.1 需要解释的木马正根

训练正根的翻转集中于rs232t1000__injzeta_d1_s42的uart_XMIT_dataH[0]观察点：ys_abc锥95门、ys_aig锥231门，共享40个PI/Q叶边界。两个根独立可信正标且输出已由同源PO/D证明。

| seed | abc分数 | aig分数 | 冻结验证阈值 |
|---|---:|---:|---:|
|42|0.784319|0.324396|0.604224|
|1|0.901401|0.513425|0.562177|
|2|0.909265|0.350755|0.628179|

三种子全部发生abc检出、aig漏检，平均绝对漂移0.4688。这是值得研究的现象，但该对象处于训练侧且此前已被检查，不能把它选作唯一验收样例，也不能由此宣布是某一特征或感受野造成。

验证唯一正根是s38417t100__injalpha_d1_s42，ys_id/ys_opt两边369/355门。三种子两根分数完全相同且均正确。这说明验证正根当前没有可供改善的漂移，不能仅靠这1对评价“木马稳定性提升”。

## 6. 接下来怎样推进等价锥实验

当前可以开始做功能表示的探索性原型准备，但不适合直接宣布“等价一致性改善木马泛化”。优先顺序如下：

1. 固定本轮476对主池作为稳定性评价和训练数据版本，继续使用全验证图检测指标。允许按训练/验证可信正标辅助定位既有PO/D证明中的根，但必须单列来源，不按测试正例位置选择。优先检查现有已证明实现对是否还有不同的正根、不同实现流程和不同源对象可投影；没有可用证据就如实保留缺口，不为增大数字展开重复边。
2. 针对上述abc/aig同功能漏检案例做表征机制诊断时，先复用输入、邻域和现有分数，检查表示所见的结构变化；不得因已知分差再调整主池、验证阈值或主指标。当前只证明关联现象，未定位因果。
3. 若进入新训练，保留当前较强改进双分支200更新、39维v3、同图同标签同监督预算和对应初始化。不要同时改正常对照预算、区域监督权重或加入SAT输入。旧H结果可作历史参考；添加新功能头或辅助损失后，原H不能自动充当严格同预算同参数的零约束组。
4. 将等价约束施加到独立功能表示或明确功能输出，而非强迫整段检测embedding或木马概率相同。若选用投影头，必须额外验证其确实保留函数差异；只有低配对距离并不足以赋予它功能含义。用非恒定性/方差及不同功能区分检查排除全常量坍缩。
5. 同一个新结构下准备零配对约束、真实配对约束、分组置换配对约束。三组功能头、其他辅助项、更新数、前向计算和监督曝光相同。先离线检查置换能否保持同源/上下文/实现方向和端点曝光，并剔除已知同功能连通分量内的假置换；无法匹配的配对三组共同暂缓并单列，不能只对置换组缩小预算。等预算指训练更新、监督曝光及结构一致，额外计算时间另报。
6. 先seed42验证加载/损失/非坍缩与检测不退化，再视结果补seed1/2。主结论需同时看全验证检测AP/预算召回、正常FPR、配对MAE/翻转及两侧均正确率。配对稳定性优先按源汇总，正负根分报；不能用占多数的负根改善掩盖木马漏检。

本轮没有实现或启动上述训练，也没有扩大SAT搜索。尤其验证仅1宿主、3源、1正根与无独立测试配对仍是结果外推限制。可先验证方法机制，不能直接作跨宿主木马鲁棒性定论。

## 7. 最终产物与复现入口

目录：`_p0pilot/cec_cone_expand_20261105/`。

- 最终数据：final_pairs.json、final_cones.json；只读原始证据不变。
- 最终合同/加载：FINAL_CONTRACT.json、final_pair_adapter.py、FINAL_adapter_preflight.csv。
- 审计：FINAL_VERIFIED.json、FINAL_COMPLETE.json、FINAL_coordinate_checks.csv、FINAL_proof_queries.csv、FINAL_proof_projection.csv、FINAL_independent_root_labels.csv。
- 权重/去重/依赖：FINAL_weights.csv、FINAL_source_summary.csv、FINAL_overlap_summary.csv。
- 现有模型诊断：OFFLINE_saved_prediction_pairs.csv、OFFLINE_saved_prediction_sources.csv、OFFLINE_saved_prediction_summary.csv、OFFLINE_feature_differences.csv、OFFLINE_feature_summary.csv、OFFLINE_BASELINE_COMPLETE.json。
- 执行环境：ginvenv_gpu中的Python，只做CPU文件与数组分析。finalize_audit.py与offline_baseline.py对已有输出有拒绝覆盖保护，不应直接反复运行。复核时读取证书并核对文件哈希；需改版则新建版本目录。
'''
    target.write_text(text, encoding='utf-8')
    brief = '''

## 等价锥最终加载核验与既有模型稳定性诊断（2026-11-05）

已完成此前交接的最终476对收尾：train382/val94/test0，437个连通锥对象343/94，训练8源3宿主、验证3源1宿主；另1个仅枚举训练对继续单列。重新提取915锥、核对35个旧查询和486条证明投影，新增验证正根证书及最终适配器全通过；按源/连通锥/观测边分级等权，旧475阶段合同和适配器不改。最终加载器为final_pair_adapter.py，FINAL_CONTRACT/FINAL_COMPLETE明确数据审计完成但功能头与训练协议未实现，不宣称训练就绪。训练327/382、验证82/94对门数变化，物理成员仍跨锥重叠（每节点最多19锥），不能视为独立样本。复用现有改进双分支39v3/H 200更新seed42/1/2预测，无训练/前向/新增SAT、未读测试：按源等权验证MAE0.0592±0.0170、翻转5.71%、两侧均正确92.83%；训练8正根来自4源，翻转集中于injzeta的abc/aig uart_XMIT_dataH[0]（95/231门，三种子都abc检出aig漏检，漂移0.4688）。验证唯一正根三种子均正确且零漂移，不能用于证明木马稳定性改善。下一步先扩查既有已证明观察点的有效正根/实现多样性及冻结功能头、非坍缩、真实/置换/零约束公平合同，不直接拉近整段检测embedding/概率、不传播标签。详见[本轮报告](等价锥最终加载核验与既有模型稳定性诊断_20261105.md)及`_p0pilot/cec_cone_expand_20261105/`。
'''
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        assert '## 等价锥最终加载核验与既有模型稳定性诊断' not in (D/name).read_text(encoding='utf-8')
        with (D/name).open('a', encoding='utf-8') as stream:
            stream.write(brief)
    # Update handoff by append, preserving the interrupted-stage account.
    with (D/'交接_等价锥CEC扩充与待收尾_20261105.md').open('a', encoding='utf-8') as stream:
        stream.write('\n\n## 恢复后的完成状态（2026-11-05）\n\n上述最终数据收尾已完成，详见[最终加载核验与稳定性诊断](等价锥最终加载核验与既有模型稳定性诊断_20261105.md)。最新入口改用FINAL_CONTRACT.json和final_pair_adapter.py（476对、437分量），旧475对接口保留。已复用三种子H预测完成离线诊断，仍0新训练/0前向/0新增SAT。后续优先正根及实现多样性、功能头与公平训练合同；不要按原交接待办重复重建已完成数据。\n')
    with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a', encoding='utf-8', newline='') as stream:
        csv.writer(stream).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            '等价锥最终加载与既有预测稳定性', 'cec_cone_expand finalize_audit/offline_baseline/publish_final.py',
            'ginvenv_gpu Python CPU;0 train/forward/newSAT', '42/1/2 saved H', 'train382/val94;test0',
            '39v3;final476;source/component/edge weights', str(O.relative_to(R)),
            '437components;915cones;35queries;valMAE.05922;flip5.71%;valpositive1',
            '完成数据审计和离线诊断', 'functional-head/anti-collapse/fair training protocol pending;one val positive'])
    files = {str(p.relative_to(R)): digest(p) for p in O.glob('FINAL_*') if p.is_file()}
    files.update({str(p.relative_to(R)): digest(p) for p in O.glob('OFFLINE_*') if p.is_file()})
    for p in (target, O/'offline_baseline.py', O/'publish_final.py'):
        files[str(p.relative_to(R))] = digest(p)
    (O/'FINAL_PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)), files=files,
        training=0, model_forward=0, new_SAT_queries=0, status='AUDIT_AND_SAVED_PREDICTION_DIAGNOSTIC_COMPLETE'), ensure_ascii=False, indent=2), encoding='utf-8')
    print('Published final cone audit and updated both notes')

if __name__ == '__main__':
    main()
