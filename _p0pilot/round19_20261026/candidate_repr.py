"""Offline richer representation candidate; NOT a training-loader input.

Recover all existing masked table information up to input permutation, retain
all tied canonical orders, original per-input statistics and physical bindings.
No new SAT, labels, model fitting, or historical arrays are used/changed.
"""
import collections
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

from analyze import canonical

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
OUT=OLD.parent/'sat_diagnosis_round19'
STATES={('infeasible','not_applicable'):0,('feasible','0'):1,('feasible','1'):2,('feasible','undecided'):3,('unknown','unknown'):4}


def main():
    records=json.loads((OLD/'records.json').read_text());snaps=json.loads((OLD/'snapshots.json').read_text())
    n=len(records);state=np.zeros((n,16,5),np.uint8);row_mask=np.zeros((n,16),bool)
    covered=np.zeros(n,bool);arity=np.zeros(n,np.uint8);per_input=np.zeros((n,4,3),np.float32);input_mask=np.zeros((n,4),bool)
    lookup={(r['view'],r['cell']):r['local_node'] for r in records};modules={};driver={}
    for s in snaps:
        raw=ROOT/s['folder']/'raw.json';assert hashlib.sha256(raw.read_bytes()).hexdigest()==s['raw_sha']
        m=next(iter(json.loads(raw.read_text())['modules'].values()));modules[s['view']]=m;driver[s['view']]={}
        for name,c in m['cells'].items():
            for pin,bs in c['connections'].items():
                if c.get('port_directions',{}).get(pin)=='output' or (not c.get('port_directions') and pin in ('Y','Q','QN')):
                    for b in bs:driver[s['view']][b]=(name,c['type'],pin)
    bindings=[];classes=set();ambiguous=0;decoded=0
    for r in records:
        if r['status']!='eligible':continue
        i=r['local_node'];k=r['k'];arity[i]=k;covered[i]=True;row_mask[i,:2**k]=True;input_mask[i,:k]=True
        values=tuple(STATES[tuple(v)] for p,v in sorted(r['table'].items()));canon=canonical(k,values)
        for j,value in enumerate(canon):state[i,j,value]=1
        pats=list(itertools.product((0,1),repeat=k));index={p:j for j,p in enumerate(pats)}
        orders=[list(order) for order in itertools.permutations(range(k)) if tuple(values[index[tuple(p[j] for j in order)]] for p in pats)==canon]
        ambiguous+=len(orders)>1
        assert tuple(state[i,:2**k].argmax(1))==canon
        decoded+=1;classes.add((k,canon))
        per_input[i,:k]=[[p['pair_coverage'],p['change_fraction'],p['influence_valid']] for p in r['inputs']]
        inputs=[];m=modules[r['view']]
        for slot,b in enumerate(r['cut_bits']):
            pi=[dict(port=pn,index=j) for pn,p in m['ports'].items() if p['direction']=='input' for j,v in enumerate(p['bits']) if v==b]
            if pi:anchor=dict(kind='PI',ports=pi)
            else:
                cell,typ,pin=driver[r['view']][b];dff='DFF' in typ.upper()
                anchor=dict(kind='physical_Q' if dff else 'logic_output',cell=cell,pin=pin,
                            local_graph_node=lookup[(r['view'],cell)],
                            physical_Q=cell if dff else None,physical_Q_polarity=(1 if pin=='Q' else -1) if dff else None)
            inputs.append(dict(original_slot=slot,raw_bit=b,anchor=anchor))
        bindings.append(dict(local_node=i,view=r['view'],target_owner_cell=r['cell'],target_role=r['target_role'],
                             target_pin=r['target_pin'],evidence=r['evidence'],inputs=inputs,
                             canonical_orders=orders,
                             order_convention='old coordinate i takes new coordinate order[i]; retain all ties, no forced cross-design correspondence'))
    p=OUT/'candidate_boundary_repr.npz'
    np.savez_compressed(p,canonical_state_onehot=state,pattern_valid=row_mask,covered=covered,k=arity,
                        per_input_original=per_input,input_valid=input_mask)
    (OUT/'candidate_bindings.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2),encoding='utf-8')
    schema=dict(status='offline_candidate_only',training_loader_compatible=False,training_allowed=False,
                state_shape=list(state.shape),states=['infeasible','forced_zero','forced_one','feasible_undecided','solver_unknown'],
                pattern_mask_shape=list(row_mask.shape),per_input_shape=list(per_input.shape),
                per_input_columns=['pair_coverage','change_fraction','valid'],
                covered_nodes=decoded,unique_permutation_classes=len(classes),ambiguous_canonical_order_records=ambiguous,
                bound_input_records=sum(len(r['inputs']) for r in bindings),
                binding_rules='Graph node routing metadata only; never feed raw bit IDs, node IDs, canonical hashes or arbitrary class numbers as scalar features.',
                claim='preserves existing table up to input reordering; no predictive gain, safety-role transfer or reachability proof',
                representation_sha=hashlib.sha256(p.read_bytes()).hexdigest(),new_sat_queries=0,new_training_runs=0)
    (OUT/'candidate_schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(schema,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
