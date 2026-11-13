"""Measure directed message-passing exposure, without changing the graph."""
import json
import numpy as np
import pandas as pd
import torch
from build_sparse_sat_round1 import PT,OUT


def main():
    torch.set_num_threads(2)
    graph=torch.load(PT/'trans_graph.pt',map_location='cpu',weights_only=False,mmap=True)
    y=graph.y.numpy().reshape(-1)>0
    test=graph.test_mask.numpy().reshape(-1).astype(bool)
    edges=graph.edge_index.numpy()
    x=np.load(PT/'satrel_node_feats_sparseR1_real.npy',mmap_mode='r')
    perm=np.load(PT/'satrel_node_feats_sparseR1_permuted.npy',mmap_mode='r')
    scenarios={'SAT_nonzero':(x[:,2:6]!=0).any(axis=1),
               'permutation_changed':(x[:,2:6]!=perm[:,2:6]).any(axis=1)}
    rows=[]
    for scenario,support in scenarios.items():
        reached=support.copy()
        for h in range(3):
            rows.append(dict(scenario=scenario,hops=h,exposed_nodes=int(reached.sum()),test_exposed_nodes=int((reached&test).sum()),
                             test_positive_exposed=int((reached&test&y).sum()),test_positives=int((test&y).sum())))
            if h<2:
                nxt=reached.copy()
                nxt[edges[1,reached[edges[0]]]]=True
                reached=nxt
    pd.DataFrame(rows).to_csv(OUT/'directed_receptive_field.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':
    main()
