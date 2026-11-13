import json,shutil
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); W=R/'generate_trans/folds/nokeep41'; S=R/'generate_trans/folds/hosts_bt31/mappings'; m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8'))
n=0
for v in m['views']:
    p=S/f"{v['view']}.json"; q=W/'mappings'/f"{v['view']}.json"
    if p.exists(): shutil.copy2(p,q); n+=1
print('copied',n)
