"""Shared two-code loader and label-independent JS objective. No optimizer."""
from pathlib import Path
import importlib.util,math
import numpy as np
R=Path(__file__).resolve().parents[2]
p=R/'_p0pilot/cec_repaired_preflight_20261107/run.py'
s=importlib.util.spec_from_file_location('frozen_repaired_loader',p);pf=importlib.util.module_from_spec(s);s.loader.exec_module(pf)
M=pf.M;torch=M.torch
ARMS=['Z0','Z1','R0','R1','P0','P1']
def dualbatch(loader,update,device='cuda'):
 a=loader.batch(update,device);ids=a['cone_ids'];arrays=loader.arrays(ids,10000+update)
 for k,v in a['arrays'].items():
  if k=='x':assert np.array_equal(v[:,:9],arrays[k][:,:9]) and not np.array_equal(v[:,9:],arrays[k][:,9:])
  else:assert np.array_equal(v,arrays[k]),k
 return a,dict(cone_ids=ids,arrays=arrays,graph=M.pack(arrays,device),loss=a['loss'])
def js(logits_a,logits_b,weights):
 la=torch.log_softmax(logits_a,dim=-1);lb=torch.log_softmax(logits_b,dim=-1);lm=torch.logaddexp(la,lb)-math.log(2)
 return .5*(weights*((la.exp()*(la-lm)).sum(-1)+(lb.exp()*(lb-lm)).sum(-1))).sum()
def objective(za,zb,b,coefficient):
 pa,ta,aa=M.objective(za,b);pb,tb,ab=M.objective(zb,b)
 parts={k:(pa[k]+pb[k])*.5 for k in pa};base={k:(ta[k]+tb[k])*.5 for k in ta}
 consistency=js(aa['logits'],ab['logits'],b['query_weight'])
 totals={arm:base[arm[0]]+(coefficient if arm[1]=='1' else 0.)*consistency for arm in ARMS}
 return parts,base,consistency,totals,aa,ab
