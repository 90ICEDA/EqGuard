"""Functional-cone data only. Does not load y/trusted, a model, or a solver."""
from pathlib import Path
import json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
class FunctionalConePairs:
 def __init__(self,split='train',pool='strict_label_blind'):
  if split not in ['train','val','test']:raise ValueError('Explicit train/val/test split required')
  tiers=read(O/'LABEL_INDEPENDENCE_TIERS.json')
  if pool not in tiers['pools']:raise ValueError('Unknown independence pool')
  self.split=split;self.pool=pool;self.contract=read(O/'FUNCTIONAL_PAIR_CONTRACT.json');allowed=set(tiers['pools'][pool]['pair_ids']);self.rows=[p for p in self.contract['pairs'] if p['split']==split and p['pair_id'] in allowed];self.cones={c['cone_id']:c for c in read(O/'cones.json')};self.feature_contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')
 def __len__(self):return len(self.rows)
 def __getitem__(self,i):
  p=self.rows[i];sides=[]
  for key in ['left_cone','right_cone']:
   c=self.cones[p[key]];assert c['split']==self.split;rr=np.array(c['graph_rows'],np.int64);rr.flags.writeable=False;sides.append(dict(view=c['view'],members=rr,output_cell=c['output_cell'],output_pin=c['output_pin'],output_bit=c['root_bit'],semantic_boundary=c['leaves'],source_object=c['source_object']))
  return dict(pair_id=p['pair_id'],context_id=p['context_id'],source_object=p['source_object'],split=self.split,left=sides[0],right=sides[1],functional_observation_equivalent=True,detector_risk_equivalent_not_certified=True)
