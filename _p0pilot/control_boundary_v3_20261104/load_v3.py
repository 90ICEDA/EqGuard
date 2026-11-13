"""Explicit offline loader for the independent v3 contract. Existing loaders unchanged."""
from pathlib import Path
import json
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def load_arrays(key,normalized=False):
 c=json.loads((HERE/'input_contract.json').read_text(encoding='utf-8'));assert c['version']=='base39_v3_PO_output_driver_only_column30'
 folder=ROOT/c['shared_inputs'][key]['folder'];out={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['x39','edge_index','edge_roles','y','trusted','physical']}
 if normalized:
  z=np.load(HERE/'normalization.npz');x=np.array(out['x39'],copy=True);x[:,25:]=np.clip((x[:,25:]-z['mean'][25:])/z['std'][25:],-10,10);out['x']=x
 return out
