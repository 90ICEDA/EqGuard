import json,shutil
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); W=R/'generate_trans/folds/nokeep41'; W.mkdir(parents=True,exist_ok=True)
for d in ('orig','trans','mappings','data/for_train'): (W/d).mkdir(parents=True,exist_ok=True)
src=R/'generate_trans/folds/hosts_bt31'
for f in ('verilog_lib.v','gate_full_to_simplified_mapping.json','gatelookup_recommended.json'): shutil.copy2(src/f,W/f)
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8')); views=[]
for v in m['views']:
    view=v['view']; views.append(view)
    op=src/'orig'/f'{view}.v'
    if not op.exists(): op=src/'orig'/f"{v['base']}.v"
    shutil.copy2(op,W/'orig'/f'{view}.v')
    tgt=R/'generate_trans/nokeep41_20261111/jobs'/v['base']/'conv'/v['host']/f"{v['base']}__keepnone__ys_{v['recipe']}.v"
    shutil.copy2(tgt,W/'trans'/f'{view}.v')
    shutil.copy2(tgt.with_suffix('.map.json'),W/'mappings'/f'{view}.json')
json.dump({'train_views':views,'val_views':[],'test_views':[]},open(W/'views.json','w'),indent=2)
(W/'views.txt').write_text('\n'.join(views)+'\n',encoding='utf-8')
print('views',len(views))
