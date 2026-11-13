"""Expose statistical limitations of draft budgets; no model/SAT calls."""
from pathlib import Path
import csv,json,hashlib
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (O/'REVIEW_FINDINGS.json').exists()
 c=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');norm=np.load(R/'_p0pilot/control_boundary_v3_20261104/normalization.npz');rr=[]
 for dm in ['orig','trans']:
  key=dm+'_train'
  with np.load(O/('supervision_'+key+'.npz')) as z:s={k:z[k] for k in z.files}
  x=np.load(R/c['shared_inputs'][key]['folder']/'x39.npy',mmap_mode='r')
  for cat,name in enumerate(['B','M','U']):
   units=read(O/('units_'+key+'_'+name+'.json'));z=np.load(O/('schedule_'+key+'_'+name+'.npz'));order=z['order'];counts=z['counts'];w=np.zeros(len(s['N']),np.int64)
   for j,u in enumerate(units):
    total=int(counts[:,j].sum());ii=order[u['offset']:u['offset']+u['size']];w[ii]+=total//u['size'];w[ii[:total%u['size']]]+=1
   ids=np.flatnonzero(s['category']==cat);weights=w[ids];assert (weights>0).all();nn=np.clip((x[s['N'][ids],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);hh=np.clip((x[s['H'][ids],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);gap=np.abs(np.average(nn-hh,axis=0,weights=weights));rr.append(dict(domain=dm,block=name,unique_pairs=len(ids),entries_200=int(weights.sum()),minimum_node_exposures=int(weights.min()),maximum_node_exposures=int(weights.max()),node_weight_concentration_equivalent_count=float(weights.sum()**2/np.square(weights.astype(float)).sum()),weighted_largest_train_z_mean_gap=float(gap.max()),weighted_gap_column=int(25+gap.argmax())))
 with (O/'weighted_exposure_review.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 findings=dict(status='REVIEW_REQUIRED_BEFORE_TRAINING',training=0,model_forward=0,SAT=0,algebraic_budget_checks_passed=True,ready_to_launch=False,issues=['Trans U:79400/79447 nodes are incomplete-added-trace residual; not a coherent functional category','Source-equal old-entry-budget schedules overexpose small objects, max trans U442550 exposures/node over200; paired fairness holds but dose is not recommended without review','M structural residual:unweighted largest train-z mean gap0.8778 orig/0.7176 trans at exact2_fanout column32; RMS matching is not full balance','B/M block budgets unequal; five-arm contribution study is not equal-dose type-efficiency comparison'],weighted_exposure=rr,recommendation='First review/cap per-node and per-object exposure in all arms symmetrically, or adopt a new lower common negative-entry budget across all five arms; explicitly document change from historical budgets. Separate U lineage uncertainty in interpretation. No new training/SAT until contract reviewed.')
 (O/'REVIEW_FINDINGS.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
 target=D/'正常对照整体作用_五组公平实验合同_20261105.md'
 text='\n## 8. 最终审视：形式公平已通过，剂量提案仍需修订\n\n五组逐步正负条目数、独立节点数及重复次数分布相同，不能因此推断当前剂量统计上合适。当前保留历史负条目数的预算是可审视草案，**不建议直接按它启动训练**。\n\n1. 变换训练U中79400/79447（99.94%）属于新增追踪不完整；匹配U不等于补齐了血缘。GAll−GBM只能解释为这批剩余可信正常标签的作用，不能称为dup/某类功能正常逻辑的独立贡献。原始U仅15节点、3源，也不支持广泛类型结论。\n2. 原始侧每步110230条负监督只有38210个独立节点，重复72020条；变换侧每步420365条仅106153—108079个独立节点，重复312286—314212条。按独立源等额虽避免大图主导，但不同源大小悬殊，变换U单节点200步最多442550次，不能将这些当独立样本。各组配对重复相同使对照在形式上公平，仍可能放大少数源对象或减弱泛化解释。\n3. M与H的结构分布未完全平衡：未加权的最大列均值差原始0.8778、变换0.7176个训练标准差，均在列32（0起，二跳扇出log1p）。这不是SAT功能差异证据，也不能称已排除全部拓扑混杂；按实际200步曝光加权后的差异另列下表。\n4. B/M/U条目预算差别很大；先明确研究目标是给定剂量下的整体/增量作用，不能直接比较GB、GM效应大小就判定哪类更有价值。\n\n'
 fields=list(rr[0]);text+='| '+' | '.join(fields)+' |\n| '+' | '.join(['---']*len(fields))+' |\n'
 for row in rr:text+='| '+' | '.join(format(row[k],'.4f') if isinstance(row[k],float) else str(row[k]) for k in fields)+' |\n'
 text+='\n“节点权重集中等效数”仅为(sum w)^2/sum(w²)，反映重复权重集中程度，不是独立源对象数，也不替代相关图节点的统计有效样本量。\n\n建议下一步先对五组对称地限制单节点/单源累计曝光，或允许五组共同采用低于历史的新版负条目预算，再冻结最终剂量；不能既强保旧条目数又把高度重复视为独立信息。减少预算将构成新的训练协议，须五组一起调整，旧H/C结果仅作历史参考。其次将U解释为剩余可信负标而非明确语义类型，必要时把可解释U与追踪不完整U分开报告。之后才核验加载器并考虑训练。本轮到此完成合同审计，没有启动训练或SAT。\n'
 with target.open('a',encoding='utf-8') as f:f.write(text)
 brief='\n\n五组合同最终审视补充（2026-11-05）：形式预算核验通过，但暂不建议原剂量直接开跑。变换U79400/79447为新增追踪不完整，不能当明确类型；历史负条目数+等源采样导致少数节点重曝（变换U最高442550次/200步），M/H二跳扇出仍有结构均值差。建议先对五组同步约束单节点/单源曝光或采用共同较低负条目预算，再冻结训练合同；不引入正例保护。实际加权差异与集中度见五组合同第8节及weighted_exposure_review.csv；0训练/0前向/0SAT。\n'
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (D/name).open('a',encoding='utf-8') as f:f.write(brief)
 # Finalize only files created in this round; no historical manifest is changed.
 files={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and p.name not in ['PUBLISHED.json','COMPLETE.json']};files[str(target.relative_to(R))]=sha(target)
 (O/'COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,labels_modified=False,review_required=True,files=files),ensure_ascii=False,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),sha=sha(target),complete_sha=sha(O/'COMPLETE.json')),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(findings,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
