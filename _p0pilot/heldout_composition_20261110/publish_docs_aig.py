"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 aig 不一致诊断（结论 B）

- 审计：`10.15/00_说明/返回审计_aig诊断_20261110.md`；证据 `KEEP_AUDIT.json`、`STATUS.json`、`keepab_panel_stage1/conv`。
- 源视图无 (* keep *) 属性；源 Trojan 名 9 个，aig none/cur 输出均仅 4 个变换名（TrojanAT1->TrojanA_t1）；两 scheme anchor_text_surv 均 .444 → 文本名指标失效，不是 keep 保留。
- 结论 B：aig 重命名/重建；aig 需结构/单元级指标，abc/nand 文本名结果保留但不与 aig 混判。
- 未新增综合（0 次）；面板不启动；STATUS nokeep.keep_removal=stage1_inconsistent (aig)，keep_removal_pilot_supported=false。
- 未训练/未 CEC/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_aig_diag')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T18:55:00+08:00,aig不一致诊断,heldout_composition_20261110,'
        '只读:结论B;0综合;0训练,seed42/1/2,rs232t1000 aig,'
        '返回审计_aig诊断_20261110.md,'
        '源9名->输出4变换名;文本指标失效;面板停\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
