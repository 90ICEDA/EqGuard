"""Finalize GT v3 text, keep view check correction, status."""
import json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
g = json.loads((H / 'GT_AVAILABILITY_V3.json').read_text(encoding='utf-8'))
g['counts'] = dict(DFF_Q=58, DFF_D=58, PI=7, PO=5)
g['design_note'] = 'tr45 is one host-level example; panel 30-combo endpoint GT not built per combo'
g['dff_note'] = 'DFF rows mapped by preserved instance name; src_Q==dst_Q and src_D==dst_D for all 58 each'
(H / 'GT_AVAILABILITY_V3.json').write_text(json.dumps(g, indent=2), encoding='utf-8')
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['view_check'] = dict(path='generate_trans/hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v', exists=True)
ka['full_command_valid'] = True
ka['command_status'] = 'ready_but_not_run'
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
q = R / '10.15/00_说明/返回审计_GT端点与keep命令_20261110.md'
if '更正（端点计数）' not in q.read_text(encoding='utf-8'):
    q.write_bytes(q.read_bytes() + """

## 更正（端点计数，2026-11-10 追加）

- 前文“13 条 verified（DFF Q/D + PI/PO）”不准确：当时 13 条为 PI/PO（7+5）加少量未分类行，**DFF 未成功解析**；
- 修正后：DFF_Q **58**、DFF_D **58**（按保留实例名映射，src/dst Q/D 网名逐条相等）、PI **7**、PO **5**；
- tr45 仅为宿主级示例；**面板 30 组合的端点 GT 尚未逐组合建立**；
- keep 视图实际位于 `generate_trans/hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v`，存在；命令可执行但仍未运行。
""".encode('utf-8'))
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['gt'] = dict(dff_q=58, dff_d=58, pi=7, po=5, note='tr45 example only; 30-combo panel GT not built')
st['keep_counterexample'] = 'not_executed'
st['synthesis_cec'] = 'not_started'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('ok')
