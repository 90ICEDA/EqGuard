import json
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8'))
for v in m['views']:
    p=R/'generate_trans/folds/hosts_bt31/orig'/f"{v['view']}.v"
    if not p.exists(): print(v['view'],v['base'],v['host'])
