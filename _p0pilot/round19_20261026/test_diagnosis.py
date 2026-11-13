import itertools
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'phase2/ys'))
from sat_boundary_semantics import summarize
from analyze import canonical

OLD=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
OUT=OLD.parent/'sat_diagnosis_round19'


class DiagnosisTests(unittest.TestCase):
    def test_xor_xnor_information_is_lost(self):
        pats=list(itertools.product((0,1),repeat=2))
        a={''.join(map(str,p)):('feasible',str(p[0]^p[1])) for p in pats}
        b={p:('feasible',str(1-int(value[1]))) for p,value in a.items()}
        self.assertEqual(summarize(a,2)[0],summarize(b,2)[0])
        av=tuple(int(a[''.join(map(str,p))][1]) for p in pats)
        bv=tuple(int(b[''.join(map(str,p))][1]) for p in pats)
        self.assertNotEqual(canonical(2,av),canonical(2,bv))

    def test_canonical_is_input_permutation_invariant(self):
        k=4;pats=list(itertools.product((0,1),repeat=k));lookup={p:j for j,p in enumerate(pats)}
        values=tuple((p[0]&p[1])^p[2] if p[3] else 3 for p in pats)
        c=canonical(k,values)
        for order in itertools.permutations(range(k)):
            changed=tuple(values[lookup[tuple(p[i] for i in order)]] for p in pats)
            self.assertEqual(canonical(k,changed),c)

    def test_candidate_masks_and_recovery(self):
        z=np.load(OUT/'candidate_boundary_repr.npz');rows=json.loads((OLD/'records.json').read_text())
        state={('infeasible','not_applicable'):0,('feasible','0'):1,('feasible','1'):2,('feasible','undecided'):3,('unknown','unknown'):4}
        checked=0
        for r in rows:
            n=r['local_node']
            if r['status']!='eligible':
                self.assertFalse(z['covered'][n]);self.assertFalse(z['pattern_valid'][n].any());continue
            k=r['k'];table=z['canonical_state_onehot'][n]
            self.assertTrue(np.all(table[:2**k].sum(1)==1))
            self.assertFalse(table[2**k:].any())
            v=tuple(state[tuple(value)] for _,value in sorted(r['table'].items()))
            self.assertEqual(tuple(table[:2**k].argmax(1)),canonical(k,v));checked+=1
        self.assertEqual(checked,2291)

    def test_real_collision_examples_are_not_just_different_gate_types(self):
        rr=json.loads((OUT/'collision_examples.json').read_text());original={r['local_node']:r for r in json.loads((OLD/'records.json').read_text())}
        for pair in rr:
            a,b=pair['a'],pair['b'];self.assertEqual(a['features'],b['features'])
            self.assertNotEqual(a['table'],b['table'])
        first=rr[0];a,b=[original[first[s]['local_node']] for s in ('a','b')]
        self.assertEqual((a['driver_type'],a['target_role']),(b['driver_type'],b['target_role']))

    def test_fixed_checkpoint_baseline_reproduced(self):
        rr=json.loads((OUT/'fixed_checkpoint.json').read_text())
        self.assertEqual(rr['optimizer_steps'],0)
        self.assertTrue(all(r['mean_probability_change']==0 for r in rr['records'] if r['input']=='real'))
        self.assertEqual(len(rr['records']),30)

    def test_candidate_is_not_silently_training_compatible(self):
        s=json.loads((OUT/'candidate_schema.json').read_text())
        self.assertFalse(s['training_allowed']);self.assertFalse(s['training_loader_compatible'])
        self.assertEqual(s['unique_permutation_classes'],231)


if __name__=='__main__':unittest.main()
