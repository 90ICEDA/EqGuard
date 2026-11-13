from pathlib import Path
import json,csv,collections
import numpy as np
from pair_adapter import FunctionalConePairs,read
from audit import sha
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def main():
 checks=[];unique={};orig=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')
 for pool,split in [(p,s) for p in ['strict_label_blind','node_label_independent_stratified_views'] for s in ['train','val','test']]:
  adapter=FunctionalConePairs(split,pool);key='trans_'+split;raw=R/orig['shared_inputs'][key]['folder'];x=np.load(raw/'x39.npy',mmap_mode='r');physical=np.load(raw/'physical.npy',mmap_mode='r');views={v['view']:v for v in orig['shared_inputs'][key]['views']};nodes=set();sources=set()
  for p in adapter:
   sources.add(p['source_object'])
   for side in ['left','right']:
    q=p[side];v=views[q['view']];ids=q['members'];assert len(ids)>0 and len(np.unique(ids))==len(ids);assert ((ids>=v['start'])&(ids<v['physical_stop'])).all() and physical[ids].all() and np.isfinite(x[ids]).all();nodes.update(map(int,ids));assert q['output_cell'] and q['output_pin']
   assert p['left']['source_object']==p['right']['source_object'];checks.append(dict(pool=pool,split=split,pair_id=p['pair_id'],source_object=p['source_object'],left_nodes=len(p['left']['members']),right_nodes=len(p['right']['members']),current_graph_coordinate_valid=True))
  unique[pool+':'+split]=dict(pairs=len(adapter),sources=len(sources),unique_physical_members=len(nodes))
 try:FunctionalConePairs('all')
 except ValueError:pass
 else:raise AssertionError('Unsafe all-split adapter')
 with (O/'adapter_preflight.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(checks[0]));w.writeheader();w.writerows(checks)
 (O/'ADAPTER_VERIFIED.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,labels_loaded=False,by_split=unique,validation_not_in_training=True,test_empty=True,bit_pin_boundaries_preserved=True,source_equal_sampling_not_implemented=True,functional_head_not_implemented=True,detector_consistency_allowed=False,adapter_sha=sha(O/'pair_adapter.py')),ensure_ascii=False,indent=2),encoding='utf-8');print(unique,flush=True)
if __name__=='__main__':main()
