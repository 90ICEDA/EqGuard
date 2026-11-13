"""Final expanded functional data. No execution or safety-label transfer hooks."""
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
class ExpandedConePairs:
 def __init__(self,split):
  if split not in ['train','val','test']:raise ValueError('Explicit split required')
  contract=read(O/'FINAL_CONTRACT.json')
  for n,h in contract['data_hashes'].items():
   if sha(O/n)!=h:raise ValueError('Frozen expanded pool changed: '+n)
  pp={p['pair_id']:p for p in read(O/'final_pairs.json')};self.rows=[pp[x] for x in contract['primary'][split]];self.cones={c['cone_id']:c for c in read(O/'final_cones.json')};self.weights=contract['weights'];self.split=split
  for p in self.rows:
   if p['split']!=split or not(p['proof_ids'] or p['enum'].get('equal') is True):raise ValueError('Unqualified proof/split')
 def __len__(self):return len(self.rows)
 def __getitem__(self,i):
  p=self.rows[i];sides=[]
  for key in ['left_cone','right_cone']:
   c=self.cones[p[key]];assert c['split']==self.split;members=np.asarray(c['graph_rows'],np.int64);members.flags.writeable=False
   sides.append(dict(view=c['view'],members=members,root_row=c['root_row'],root_bit=c['root_bit'],root_cell=c['output_cell'],root_pin=c['output_pin'],boundary=tuple(tuple(l) for l in c['leaves'])))
  return dict(pair_id=p['pair_id'],split=self.split,source_object=p['source_object'],context_id=p['context_id'],left=sides[0],right=sides[1],weight=self.weights[p['pair_id']],proof_method='source_bound_CEC' if p['proof_ids'] else 'complete_PI_Q_enumeration',selection_origins=tuple(p['origins']),functional_training_data_eligible=self.split=='train',risk_consistency_allowed=False,whole_embedding_alignment_allowed=False,label_transfer_allowed=False)
