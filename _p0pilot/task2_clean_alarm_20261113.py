"""Frozen graph-alarm diagnostic on existing, unpaired clean netlists."""
import sys

import numpy as np
import torch

from evaluate_task2_nokeep_20261113 import (
    CAL, CONFIRM, NORM, OUT, P, ROOT, RUN, SEEDS, dump, module, read, sha, validation_threshold, write_csv,
)


def main():
    b = module('task2_clean_builder', CONFIRM / 'build.py')
    a = sys.modules['audit']
    s = b.S
    lib = b.V.load_library(s.F / 'verilog_lib.v')
    mapping = {r['full_gate_name']:r['simplified_gate_type'] for r in read(s.F / 'gate_full_to_simplified_mapping.json')}
    order = read(s.F / 'gatelookup_recommended.json')['simplified_gate_type_order']
    model = module('task2_clean_model', P / 'control_best200_20261104/evaluate.py').Model().cuda().eval().requires_grad_(False)
    with np.load(NORM) as norm:
        mean,std = norm['mean'][25:],norm['std'][25:]
    evaluation = read(CAL)
    paths = [ROOT / f'generate_trans/yslib_test/{host}/{host}_clean__ys_{recipe}.v'
             for host in ('s38417t100','s38584t100') for recipe in ('abc','nand')]
    graphs, skipped = [], []
    for path in paths:
        if not path.is_file():
            skipped.append(str(path))
            continue
        raw = a.endpoints(path)[0]
        names = [n for n in raw['cells'] if n not in set(raw['virtual_names'])]
        _, parsed, x, _, _ = b.graph(path,names,lib,mapping,order)
        x[:,25:] = np.clip((x[:,25:]-mean)/std,-10,10)
        graphs.append((path,len(names),torch.as_tensor(x,device='cuda'),torch.as_tensor(parsed['edge_index'],device='cuda')))
    assert graphs
    rows=[]
    for seed in SEEDS:
        for arm in ('N','NC'):
            for point in ('best','last'):
                suffix='' if seed==42 else f'_s{seed}'
                ckpt=RUN/f'{arm}{suffix}_{point}.pt'
                model.load_state_dict(torch.load(ckpt,map_location='cpu',weights_only=True),strict=True)
                cutoff=validation_threshold(seed,arm,point,evaluation)
                for path,n,x,edge in graphs:
                    with torch.inference_mode(), torch.autocast('cuda',dtype=torch.bfloat16):
                        logits=model(x,edge).float()
                    margin=(logits[:,1]-logits[:,0]).cpu().numpy()[:n]
                    assert np.isfinite(margin).all()
                    hits=int((margin>=cutoff).sum())
                    rows.append(dict(view=path.stem,host=path.parent.name,recipe=path.stem.rsplit('__ys_',1)[-1],seed=seed,
                                     arm=arm,point=point,physical=n,alarm=int(hits>0),alarm_nodes=hits,
                                     alarm_node_fraction=hits/n,threshold=cutoff,max_margin=float(margin.max())))
    write_csv(OUT/'CLEAN_UNPAIRED_ALARMS.csv',rows)
    dump(OUT/'CLEAN_UNPAIRED_PROTOCOL.json',dict(netlists={str(p.relative_to(ROOT)):sha(p) for p,_,_,_ in graphs},
         missing=skipped,views=len(graphs),forward_sets=len(rows),paired_keep_state=False,optimizer_steps=0,sat_cec_calls=0))
    print('clean',len(graphs),len(rows),sum(r['alarm'] for r in rows),flush=True)


if __name__=='__main__':
    main()
