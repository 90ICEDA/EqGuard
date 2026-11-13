"""Frozen mixed-proof functional pool. No labels, model or solver in payload."""
from pathlib import Path
import hashlib,json
import numpy as np
O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
class FunctionalConePool:
 def __init__(self,split):
  if split not in ['train','val','test']:raise ValueError('Explicit split required')
  c=read(O/'POOL_CONTRACT.json')
  for n,h in c['data_hashes'].items():
   if sha(O/n)!=h:raise ValueError('Frozen input changed: '+n)
  byid={p['pair_id']:p for p in read(O/'pool_pairs.json')};self.rows=[byid[x] for x in c['primary'][split]];self.cones={p['cone_id']:p for p in read(O/'pool_cones.json')};self.weights=c['weights'];self.split=split
  for p in self.rows:
   if p['split']!=split or not (p['proof_ids'] or p['enum'].get('equal') is True):raise ValueError('Split or proof mismatch')
 def __len__(self):return len(self.rows)
 def __getitem__(self,i):
  p=self.rows[i];sides=[]
  for k in ['left_cone','right_cone']:
   c=self.cones[p[k]];assert c['split']==self.split;ii=np.asarray(c['graph_rows'],dtype=np.int64);ii.flags.writeable=False
   sides.append(dict(view=c['view'],members=ii,root_row=c['root_row'],root_cell=c['output_cell'],root_bit=c['root_bit'],root_pin=c['output_pin'],boundary=tuple(tuple(l) for l in c['leaves'])))
  return dict(pair_id=p['pair_id'],split=self.split,source_object=p['source_object'],context_id=p['context_id'],left=sides[0],right=sides[1],weight=self.weights[p['pair_id']],proof_method='source_bound_native_CEC' if p['proof_ids'] else 'complete_PI_Q_enumeration',selection_origins=tuple(p['origins']),functional_training_data_eligible=self.split=='train',detector_risk_consistency_allowed=False,label_transfer_allowed=False)
