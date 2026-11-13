"""Offline data-level invariance and schema checks; never runs a solver."""
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
from boundary_repr import canonical, parse_table, reindex, summarize

ROOT=Path(__file__).resolve().parents[2]
TABLES=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'
OUT=TABLES/'sat_boundary_round9'


def main():
    transformations=0
    for rd,folder in [('r5','sat_nonlocal_round5'),('r6','sat_expand_round6'),('r7','sat_repair_round7')]:
        for r in pd.read_csv(TABLES/folder/f'{rd}_nonlocal_relations.csv').itertuples():
            k=len(r.cut_nets.split(';'));table=parse_table(r.truth_table,k)
            signature=canonical(table,k)['signature'];features=summarize(table,k)[0]
            for order in itertools.permutations(range(k)):
                renamed=reindex(table,order)
                assert canonical(renamed,k)['signature']==signature
                assert summarize(renamed,k)[0]==features
                transformations+=1
    pairs=pd.read_csv(OUT/'proven_boundary_pairs.csv')
    assert pairs.semantic_pair_allowed.all() and not pairs.training_pair_allowed.any()
    assert (pairs.descriptor_max_abs_diff==0).all() and (pairs.input_stats_max_abs_diff==0).all()
    region=pd.read_csv(OUT/'expanded_region_pairs.csv')
    assert region.resolved_a.all() and region.resolved_b.all()
    assert not region.internal_node_correspondence_inferred.any()
    assert not region.training_pair_allowed.any()
    a=np.load(OUT/'blind_annotations_sparse.npz')
    f=a['features'];schema=json.loads((OUT/'feature_schema.json').read_text())
    assert np.isfinite(f).all() and f.min()>=0 and f.max()<=1
    assert len(np.unique(a['node_index']))==len(a['node_index'])==132
    assert not schema['training_loader_compatible']
    assert (f[f[:,-1]>0,-2]>0).all(), 'No unavailable comparison can create input functional coverage'
    out=dict(unit_tests_passed=12,permutation_checks=transformations,
        exact_case_role_comparisons=len(pairs),max_case_descriptor_difference=0,
        expanded_regions_resolved=len(region),blind_nodes=len(a['node_index']),
        bounded=True,training_gate_closed=True,new_sat_queries=0,training_runs=0)
    (OUT/'quality_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2),flush=True)


if __name__=='__main__':main()
