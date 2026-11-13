"""Data-only current-CEC cone pairs. No Torch, labels, optimizers or solver imports."""
from pathlib import Path
import json
import numpy as np
O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
class CECConePairs:
 def __init__(self,split='train'):
  if split not in ['train','val','test']:raise ValueError('Explicit split required')
  contract=read(O/'CEC_POOL_CONTRACT.json');allowed=set(contract['primary'][split]);self.rows=[p for p in read(O/'pairs.json') if p['pair_id'] in allowed];self.cones={c['cone_id']:c for c in read(O/'cones.json')};self.split=split
 def __len__(self):return len(self.rows)
 def __getitem__(self,i):
  p=self.rows[i];sides=[]
  for key in ['left_cone','right_cone']:
   c=self.cones[p[key]];assert c['split']==self.split;ids=np.array(c['graph_rows'],np.int64);ids.flags.writeable=False;sides.append(dict(view=c['view'],members=ids,root_row=c['root_row'],root_pin=c['output_pin'],boundary=c['leaves']))
  return dict(pair_id=p['pair_id'],split=self.split,source_object=p['source_object'],selection_origins=p['origins'],left=sides[0],right=sides[1],functional_equivalence=True,detector_risk_training_allowed=False)
