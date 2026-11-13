"""Append docs, registry, STATUS."""
import json, shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); F = ROOT / '_p0pilot/four_group_contract_20261109'; H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 hoco 门禁补证与 seed42 四组

- 审计：`10.15/00_说明/返回审计_hoco门禁与seed42_20261110.md`；证据 `heldout_composition_20261110/`。
- 反例改用生产函数 hoco_cone_lib：跨 recipe 同名锥并存且成员不同、正例入负例池、重复、不足均被拒；写 GATE_A/B 的 counterexamples。
- 锥 10,742（358/10,384）与逐源表一致；CONE_QUOTA_A/B.csv 保存候选/匹配/采用/曝光；37 源有 D 锥。
- GATE 补 step0 len 8623/哈希、optimizer_steps=0（optimizer=null）、参数/BN/CPU+全部 CUDA RNG 逐项比较；A/B 门禁通过。
- seed42 四组完成：A-N/A-NC/B-N/B-NC 验证 AP .2154/.1974/.1220/.1050；测试基础池 .2744/.3175/.2483/.2639，aig/nand .1872/.1528/.2218/.2157。
- 交互 I：基础 −0.0275、aig/nand +0.0283（单 seed42，与四组实验方向相反，不宣称稳定/因果）。
- 未完成：seed1/2、Top-1/5、A/B 多阈值、两视图报警、独立审计、no-keep/GT、深度 RF。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_hoco_run')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T13:35:00+08:00,hoco门禁与seed42四组,heldout_composition_20261110,'
        '训练:4组200更新;评价;0综合;0 SAT,seed42,hosts_bt31 train+test,'
        '返回审计_hoco门禁与seed42_20261110.md,'
        'I base -.0275 add +.0283;四组完成;未跑seed1/2\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
st = dict(phase='hoco_seed42_complete', completed=['counterexamples production paths', 'cone quota csv', 'gate A/B',
          'RUN_CONTRACT', 'manifest', '4x200 training', 'test evaluation'],
          not_done=['seed1/2', 'top-k/A-B multi', 'two view alarms', 'independent audit', 'no-keep/GT', 'depth/RF'])
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('registry+status')
