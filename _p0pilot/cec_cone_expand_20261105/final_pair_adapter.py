"""Frozen final functional-cone data, with no detector labels or execution hooks."""
from pathlib import Path
import hashlib
import json
import numpy as np

O = Path(__file__).resolve().parent

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

class FinalCECConePairs:
    def __init__(self, split):
        if split not in ('train', 'val', 'test'):
            raise ValueError('Explicit train/val/test split required')
        contract = read(O / 'FINAL_CONTRACT.json')
        for name, checksum in contract['data_hashes'].items():
            if digest(O / name) != checksum:
                raise ValueError('Frozen cone input changed: ' + name)
        allowed = contract['primary'][split]
        byid = {p['pair_id']: p for p in read(O / 'final_pairs.json')}
        self.rows = [byid[p] for p in allowed]
        self.cones = {c['cone_id']: c for c in read(O / 'final_cones.json')}
        self.weights = contract['weights']
        self.split = split
        self.training_data_eligible = split == 'train'
        if any(p['split'] != split or not p['proof_ids'] for p in self.rows):
            raise ValueError('Split or proof eligibility mismatch')

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        p = self.rows[index]
        sides = []
        for key in ('left_cone', 'right_cone'):
            c = self.cones[p[key]]
            if c['split'] != self.split:
                raise ValueError('Cross-split cone')
            ids = np.array(c['graph_rows'], dtype=np.int64)
            ids.flags.writeable = False
            sides.append(dict(view=c['view'], members=ids, root_row=c['root_row'],
                              root_cell=c['output_cell'], root_pin=c['output_pin'],
                              root_bit=c['root_bit'],
                              boundary=tuple(tuple(x) for x in c['leaves'])))
        return dict(pair_id=p['pair_id'], split=self.split,
                    source_object=p['source_object'], context_id=p['context_id'],
                    selection_origins=tuple(p['origins']),
                    proof_ids=tuple(p['proof_ids']),
                    weight=self.weights[p['pair_id']], left=sides[0], right=sides[1],
                    functional_equivalence=True,
                    functional_training_data_eligible=self.training_data_eligible,
                    detector_risk_training_allowed=False,
                    whole_embedding_alignment_allowed=False,
                    security_label_transfer_allowed=False)
