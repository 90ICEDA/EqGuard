from pathlib import Path
import json,csv,hashlib,datetime
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];N=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert (O/'PUBLISHED.json').exists() and not (O/'COMPLETE.json').exists()
 for seed in [42,1,2]:
  for arm in ['H','C']:
   p=O/f'seed{seed}'/arm;h=read(p/'history.json');ev=read(p/'EVALUATED.json');sel=read(p/'SELECTED.json')
   assert [x['update'] for x in h]==list(range(1,201));assert sel['score']==max(x['val_ap'] for x in h if 'val_ap' in x);assert sel['epoch']==next(x['update'] for x in h if x.get('val_ap')==sel['score']);assert sha(p/'best.pt')==ev['checkpoint_sha']==sel['checkpoint_sha']
   for key,digest in ev['prediction_sha'].items():assert sha(p/(key+'_scores.npy'))==digest
 assert not list(O.glob('failure_*.log'))
 conclusion='''

## 结果解释与下一步决定

1. **支持有限的正常区域监督贡献，不支持AP提高。** 测试AP均值H 0.2445±0.0194、C 0.2441±0.0150，配对差均值约−0.0004，种子42/1/2变化分别+0.0047/−0.0027/−0.0031，没有一致AP增益。验证AP均值0.1652→0.1666，也只有小幅变化。
2. **误报下降具有方向一致性，但还没消除对象级报警。** 历史操作点下，验证正常区域节点FPR24.66%→20.14%；测试25.25%→18.37%，下降6.88个百分点。测试三个种子分别26.31%→25.79%、22.00%→14.37%、27.46%→14.96%。六个测试源对象跨种子平均均下降，但逐对象不是每个种子都改善。测试有报警的源对象H为5/6、6/6、6/6，C均5/6。风险前列问题仍在，不能称正常区域识别已经解决。
3. **木马检出基本接近，但不能说完全无损。** 历史操作点测试木马视图宏平均召回51.83%→50.94%，下降0.89个百分点；对应角色后代集合的木马节点召回47.39%→45.97%。因此误报下降伴随小幅检出代价，不能把全部FPR改善都归因于更好的判别表示。
4. **匹配角色集合有部分改善。** 测试正确排序93.33%→96.67%，联合成功（木马报警且正常不报警）30%→40%，三个种子为40%→40%、30%→50%、20%→30%。这是既有阈值附近的局部收益，不是对所有中间门的逐节点功能区分证明。
5. **高召回条件下的分离仍弱。** 仅以验证正例校准80% pooled召回后，实际测试宏平均召回80.64%→80.03%，正常区域FPR67.52%→64.87%，仅下降2.65个百分点；两组配对联合成功均0。90%校准下实际测试召回90.29%→90.55%，正常区域FPR82.58%→81.89%，只下降0.69个百分点，联合成功仍0。说明提高检出要求时，木马与正常区域分数仍大量重叠。

本轮可以写为：“在固定模型、图与监督预算的探索性对照中，面向木马相似正常区域的定向负例监督降低了局部误报，并改善部分对应角色集合的联合判别；尚未观察到节点AP增益，高召回工作点的误报问题仍然突出。”不能写成“正常对照显著提高总体检测性能”或“高召回下误报问题已解决”。

下一步先复用本轮预测，检查误报下降来自哪些源角色、门型和分数区间，以及木马漏检是否集中在相同角色；在验证集上比较完整召回—区域误报曲线，量化可接受的检出代价。本轮到此停止，不自动追加训练/SAT。若后续授权训练，优先检验固定总负例权重下的区域监督强度，并保持H/C严格等权；当前320槽占trans监督仅约0.076%，不能凭本轮近零AP变化否定更合适权重的作用。任何下一轮方案只用训练/验证证据决定，现有测试仍作探索性结果，独立确认需新增冻结对象/宿主。
'''
 report=N/'正常对照等预算实验_改进双分支200次_20261104.md'
 for p in [report,O/'实验报告.md']:
  with p.open('a',encoding='utf-8') as f:f.write(conclusion)
 brief='\n\n### 本轮最终判读：误报有局部收益，AP没有增益\n\nH/C三种子测试AP 0.2445/0.2441；新增正常区域等源FPR25.25%/18.37%（三个种子均下降）；木马召回51.83%/50.94%；配对集合联合成功30%/40%。验证校准80%召回操作点的区域FPR仍67.52%/64.87%，联合成功均0，高召回分离不足。仅支持固定低预算下局部误报改善，不支持总体AP或无损检出改善。本轮不再追加训练或SAT；下一步先用既有预测诊断角色与召回—误报曲线，另行授权后才测试监督强度。证据见[完整实验报告](正常对照等预算实验_改进双分支200次_20261104.md)。\n'
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as f:f.write(brief)
 files=[p for p in O.glob('*.csv')]+[O/'manifest.json',O/'FAIRNESS_VERIFIED.json',O/'ANALYSIS_COMPLETE.json',report]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),training_runs=6,updates=1200,no_failed_runs=True,no_repeated_update_records=True,checkpoints_and_predictions_verified=True,SAT=0,files={str(p.relative_to(R)):sha(p) for p in files},conclusion='local false positives reduced; AP unchanged; high recall separation unresolved'),ensure_ascii=False,indent=2),encoding='utf-8');print('Final integrity and notes updated')
if __name__=='__main__':main()
