"""Independent saved-prediction audit and report publication; no training/SAT."""
import sys,json,csv,hashlib,time,datetime
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score,roc_auc_score
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent
C=json.loads((H/'input_contract.json').read_text());R=json.loads((H/'comparison.json').read_text());PF=json.loads((H/'preflight.json').read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def arr(key,name):return np.load(ROOT/C['shared_inputs'][key]['folder']/(name+'.npy'),mmap_mode='r')
def main():
    for path,info in PF['source_graph_stats'].items():
        p=ROOT/'generate_trans/folds/hosts_bt31/data/processed'/path
        assert p.stat().st_size==info['size'] and p.stat().st_mtime_ns==info['mtime_ns']
    for path,digest in C['files'].items():assert sha(ROOT/path)==digest
    # Independent role/coordinate checks over all six split graphs.
    graphchecks={}
    for key,conf in C['shared_inputs'].items():
        x=arr(key,'x39');e=arr(key,'edge_index');y=arr(key,'y');trusted=arr(key,'trusted');physical=arr(key,'physical')
        assert np.isfinite(x).all() and not trusted[~physical].any() and np.all(y[~physical]==-1)
        owner=np.empty(len(y),np.int32)
        for j,v in enumerate(conf['views']):owner[v['start']:v['stop']]=j
        assert np.array_equal(owner[e[0]],owner[e[1]])
        graphchecks[key]=dict(nodes=len(y),edges=e.shape[1],views=len(conf['views']),no_cross_view_edges=True)
    p=np.load(H/'primitive_matrix.npy');norm=np.load(H/'normalization.npz')
    mapped_counts={}
    for key in ('orig_train','trans_train'):
        x=arr(key,'x39');physical=arr(key,'physical');trusted=arr(key,'trusted');y=arr(key,'y')
        counts=[]
        for j,name in enumerate(C['columns39'][:25]):
            gate=(x[:,j]>0)&physical
            if gate.any():counts.append(dict(gate=name,physical=int(gate.sum()),trusted=int((gate&trusted).sum()),positive=int((gate&trusted&(y==1)).sum()),primitive=p[j].tolist()))
        mapped_counts[key]=counts
    common_a=torch.load(H/'runs/base39/initial.pt',map_location='cpu',weights_only=True)
    common_b=torch.load(H/'runs/primitive21/initial.pt',map_location='cpu',weights_only=True)
    same=[];different_shapes=[]
    for k,a in common_a.items():
        b=common_b[k]
        if a.shape==b.shape:assert torch.equal(a,b);same.append(k)
        else:different_shapes.append(k)
    assert different_shapes==['convs.0.nn.0.weight']
    rows=[];paired=[];maxmetricdiff=0
    for arm in ('base39','primitive21'):
        out=H/'runs'/arm;log=json.loads((out/'train_log.json').read_text());assert len(log)==100 and [r['updates'] for r in log]==list(range(1,101))
        assert all(np.isfinite(r['loss']) and np.isfinite(r['gradient_norm']) and r['finite'] for r in log)
        pd.DataFrame([{k:v for k,v in r.items() if k!='validation'}|{'validation_ap':r.get('validation',{}).get('trusted',{}).get('ap')} for r in log]).to_csv(out/'train_log.csv',index=False,encoding='utf-8-sig')
        for key in ('trans_val','trans_test'):
            scores=np.load(out/(key+'_scores.npy'));y=arr(key,'y');trusted=arr(key,'trusted');physical=arr(key,'physical');saved=pd.read_csv(out/(key+'_per_view.csv'))
            for scope,mask in [('trusted',trusted),('legacy',physical)]:
                for view in C['shared_inputs'][key]['views']:
                    lo,hi=view['start'],view['stop'];m=mask[lo:hi];yy=y[lo:hi][m];ss=scores[lo:hi][m]
                    savedrow=saved[(saved.view==view['view'])&(saved.scope==scope)].iloc[0]
                    if yy.sum():
                        expected=average_precision_score(yy,ss);diff=abs(expected-savedrow.ap);maxmetricdiff=max(maxmetricdiff,diff);assert diff<1e-12
            for scope in ('trusted','legacy'):
                m=R[arm][key][scope]
                rows.append(dict(arm=arm,split=key,scope=scope,best_epoch=R[arm]['selected']['epoch'],**m))
    pd.DataFrame(rows).to_csv(H/'comparison.csv',index=False,encoding='utf-8-sig')
    a=pd.read_csv(H/'runs/base39/trans_test_per_view.csv');b=pd.read_csv(H/'runs/primitive21/trans_test_per_view.csv')
    pair=a.merge(b,on=['view','scope'],suffixes=('_39','_21'));pair['ap_delta_21_minus_39']=pair.ap_21-pair.ap_39;pair['recipe']=pair.view.str.split('__').str[-1]
    pair.to_csv(H/'test_paired_views.csv',index=False,encoding='utf-8-sig')
    recipe=pair[pair.view.str.contains('__inj')].groupby(['scope','recipe'])[['ap_39','ap_21','ap_delta_21_minus_39']].mean().reset_index()
    recipe.to_csv(H/'test_by_recipe.csv',index=False,encoding='utf-8-sig')
    # Loading a fixed checkpoint on CUDA scatter kernels can introduce tiny changes.
    val_replay={arm:R[arm]['trans_val']['trusted']['ap']-R[arm]['selected']['score'] for arm in R}
    audit=dict(passed=True,graphchecks=graphchecks,input_hashes_unchanged=True,legacy_graph_stats_unchanged=True,
        equal_shape_initial_state_tensors_identical=len(same),different_shape_parameters=different_shapes,
        max_saved_prediction_metric_difference=maxmetricdiff,validation_checkpoint_replay_ap_delta=val_replay,
        deterministic_bitwise_claim=False,epochs_each=100,optimizer_updates_each=100,nonfinite_steps=0,new_SAT_queries=0,
        mapped_training_gates=mapped_counts,peak_memory_note='SELECTED peak_vram_mib is a process-cumulative high-water mark; not an independently reset per-arm measurement.')
    write(H/'final_audit.json',audit)
    base=R['base39'];prim=R['primitive21'];now=datetime.datetime.now().astimezone().isoformat()
    elapsed=((H/'COMPLETE.json').stat().st_mtime-(H/'train.log').stat().st_ctime)
    table=['|口径/集合|39维v2 AP|原语21维 AP|','|---|---:|---:|']
    for key,label in [('trans_val','验证'),('trans_test','测试')]:
        for scope,scope_label in [('trusted','可信监督'),('legacy','旧标签全物理节点')]:
            table.append(f"|{label}·{scope_label}|{base[key][scope]['ap']:.6f}|{prim[key][scope]['ap']:.6f}|")
    t39=base['trans_test']['trusted'];t21=prim['trans_test']['trusted']
    text=f'''# 第三十二轮：P2-A 39维v2与原语21维 seed42受控对照

完成时间：{now}。

## 结论

两组均完成100 epoch、每epoch一次优化更新，共200次。原语21维的验证AP更高，但测试AP更低；测试预算召回更高、正常对照误报也更高。本轮不能认定原语编码整体更优，不据此扩展到其他种子或启动SAT训练。

{chr(10).join(table)}

测试可信口径：Recall@1% {t39['r1']:.4%}→{t21['r1']:.4%}；Recall@5% {t39['r5']:.4%}→{t21['r5']:.4%}；AUC {t39['auc']:.6f}→{t21['auc']:.6f}；正常对照逐视图平均FPR {t39['control_fpr']:.4%}→{t21['control_fpr']:.4%}。阈值分别{base['threshold']:.6f}/{prim['threshold']:.6f}，由各自验证集可信负例95%分位确定，再冻结到测试。该规则控制验证负例整体目标FPR约5%，不保证每个视图均为5%。

AP主表为含正例的注入视图等权平均，验证25视图，测试24视图；不是pooled AP。正常对照另报FPR。可信口径只评价可信节点，旧标签口径包含未知背景的历史0标签，二者分母不同，不能混用。

## 输入与监督

39维v2=25维库门型+14维结构拓扑；21维=7维原语构成+相同14维。组合环两列已在14维中，未另加。7类原语比例保持[0,1]，不是SAT函数签名；复合门的构成顺序仍会丢失，寄存器变体也会归并。

使用同一份v2有向全引脚图，含数据/时钟/复位等边；边角色作为可审计元数据保留，本轮单分支GIN不额外使用角色嵌入。没有将全引脚图声称为纯数据因果图。原始侧76个源网表也独立重建v2，保持旧物理节点坐标并检查前26列；不能只修trans侧。

冻结388视图划分：train259、val65、test64；未列入划分的3071节点视图排除。训练trans物理1250510节点，其中可信421497，含829正例；829013未知背景不进损失，154个新增辅助节点仅参与消息传递。原始侧训练50份源网表、110283个可信节点、136正例。验证/测试辅助节点429/1246均无监督；所有原始源设计引用的划分互斥。图内无跨视图边。

归一化仅由训练集orig+trans物理节点拟合；门型/原语保持有界原值，14维共用完全相同均值标准差、z-score裁剪±10。没有按验证/测试效果删特征。

## 模型、损失与预算

ginvenv_gpu；RTX5060 Laptop；单分支4层GIN，hidden64、dropout0.2、Adam lr0.0002、weight_decay0.001、BF16 AMP、seed42。参数量32322与31170，差1152来自首层输入权重。所有同形状初始参数/缓冲区逐项相等；两组相同逐epoch种子策略，但不声称CUDA聚合逐位确定性。

Mode2有效损失：orig ASL+trans ASL+1.4×两侧soft miss平方；ASL gamma_pos1/gamma_neg4/clip0.05，soft recall温度0.5。一致性、位置、区域、pair和SAT损失均为0。本轮独立入口不再读取固定x[:,29]；小样本与历史有效损失及梯度比较完全一致，max差0。先对orig和trans分别反传、再执行一次optimizer.step，与可分损失累加同义，降低同时保留激活的显存。

每组100次更新，每5次用验证集可信注入视图macro AP选模；39维最佳epoch85，21维最佳epoch100。两组均选定后才进行最终测试预测。记录每次更新、完整配置、初始权重、分阶段checkpoint、选中权重及验证测试预测。没有重复训练成功组。

训练进程日志创建至完成标记约{elapsed:.1f}秒（含初始化、预检、验证、测试，不含前期CPU构建）；进程累计torch显存分配峰值约3385.5MiB，不能当作逐组独立峰值。只加载当前划分图，避免无用全图前向；验证和测试不参与训练BatchNorm统计。最终checkpoint重放的验证AP最大变化{max(abs(x) for x in val_replay.values()):.8f}，不声称逐位重放一致。

## 证据边界与下一步

可信监督、train-only归一化、v2有向图、训练图范围及选模口径均与旧A0存在区别。因此本轮两组可相互比较，不能直接与旧A0 AP比较后把差异归因于特征修复或原语编码。旧数据、训练结果及SAT成功批次未改动。SAT仍暂停；本轮SAT查询0。

先保留39维v2为当前基础候选，原语21维作为独立候选；本轮单种子测试不支持整体替换。后续经授权优先补seed1/2验证方向稳定性，不因测试排名追加调参，也不把历史开发与当前测试当全新独立确认。原语组在预算末尾选中最佳点，只能说明当前固定预算下的表现，不能据测试效果为其单独加预算。

## 产物

input_contract.json、preflight.json、gpu_preflight.json、loss_equivalence.json、final_audit.json；comparison.csv/json；test_paired_views.csv、test_by_recipe.csv；runs/base39及runs/primitive21内含config、train_log、checkpoint、SELECTED、每视图CSV及scores.npy。独立脚本prepare_pair.py、train_pair.py、finalize_pair.py，不修改历史训练入口。
'''
    (H/'第三十二轮_P2A编码对照.md').write_text(text,encoding='utf-8')
    marker='第三十二轮：P2-A 39维v2与原语21维 seed42受控对照'
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        p=ROOT/'10.15/00_说明'/name
        if marker not in p.read_text(encoding='utf-8'):
            with p.open('a',encoding='utf-8') as f:f.write('\n\n'+text.replace('# 第三十二轮','### 第三十二轮',1))
    registry=ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv'
    if marker not in registry.read_text(encoding='utf-8'):
        with registry.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([now,marker,'prepare_pair.py; train_pair.py; finalize_pair.py','ginvenv_gpu; single4x64; 100updates each; BF16',42,'frozen hosts_bt31','same v2 graph/trusted masks/loss/shared14 normalization',str(H.relative_to(ROOT)),f"trusted test AP {t39['ap']:.6f}/{t21['ap']:.6f}; legacy {base['trans_test']['legacy']['ap']:.6f}/{prim['trans_test']['legacy']['ap']:.6f}",'完成；仅seed42；无SAT','old artifacts retained; primary trusted and legacy scopes separated'])
    print(text)
if __name__=='__main__':main()
