"""Pure-array loader for expanded evaluation cones;no model instantiation or training."""
from pathlib import Path
import gzip,importlib.util,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
class PanelLoader:
 def __init__(self):
  with gzip.open(O/'local_graphs.json.gz','rt',encoding='utf-8') as f:z=json.load(f)
  self.graphs=dict(zip(z['cone_ids'],z['graphs']));self.contexts=dict(zip(z['cone_ids'],z['contexts']))
  p=R/'_p0pilot/cec_hard_boundary_20261106/local_interface.py';s=importlib.util.spec_from_file_location('expanded_panel_frozen_array_schema',p);self.schema=importlib.util.module_from_spec(s);s.loader.exec_module(self.schema)
  maps=json.loads((R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json').read_text(encoding='utf-8-sig'));self.tokens={m['context_key']:m['tokens'] for m in maps}
 def arrays(self,cone_ids,tag=9000):
  assert cone_ids and len(cone_ids)==len(set(cone_ids))
  for cid in cone_ids:self.schema.validate(self.graphs[cid])
  return self.schema.collate([self.graphs[c] for c in cone_ids],[self.contexts[c] for c in cone_ids],self.tokens,tag)
 def unit(self,u,tag=9000):
  """Roots stay ordered L0,R0,L1,R1,...;2/3 candidates remain genuine."""
  n=u['functions'];assert n in [2,3] and len(u['cones'])==2*n
  a=self.arrays(u['cones'],tag);queries=[]
  for f in range(n):
   for side in [0,1]:queries.append(dict(anchor=2*f+side,candidates=[2*j+1-side for j in range(n)],true_target=f))
  assert len(a['root_index'])==2*n
  return a,queries
