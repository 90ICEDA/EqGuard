"""Freeze validation thresholds and score equivalence-certified controls."""
import importlib.util
import itertools
import re
from collections import Counter

from build import OUT, ROOT, V3, csv_out, digest, enc, nl, read, stripped

EVAL = OUT.parent / 'control_best200_20261104/evaluate.py'
spec = importlib.util.spec_from_file_location('live_control_frozen_eval', EVAL)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)

import json
import numpy as np
import torch


def local_truth(record, model):
    a, b = record['host_inputs']
    y = record['host_output']
    gates = {cell.name: cell for cell in model.insts}
    ops = {
        'INV': lambda a: not a, 'AND': lambda a, b: a and b,
        'OR': lambda a, b: a or b, 'NOR': lambda a, b: not (a or b),
        'NAND': lambda a, b: not (a and b),
        'XOR': lambda a, b: a != b, 'XNOR': lambda a, b: a == b,
    }
    def operation(gate):
        return ops[re.fullmatch(r'([A-Z]+?)\d*X\d+(?:_RS)?', gate)[1]]

    def forward(av, bv, invert=None):
        values = {a: av, b: bv}
        for name in record['region']:
            gate = gates[name]
            output = operation(gate.gate)(*(values[net] for pin, net in gate.conns if pin != 'Y'))
            values[dict(gate.conns)['Y']] = not output if invert == name else output
        return values[y]

    pairs = list(itertools.product((False, True), repeat=2))
    expected = [operation(record['replaced_gate'])(*p) for p in pairs]
    observed = [forward(*p) for p in pairs]
    witnesses = {n: [list(map(int, p)) for p, bit in zip(pairs, observed) if forward(*p, invert=n) != bit]
                 for n in record['region']}
    assert observed == expected and all(witnesses.values()), record['view']
    return dict(view=record['view'], local_truth=list(map(int, observed)), flip_witnesses=witnesses)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    cases = read(OUT / 'MANIFEST.json')
    folds = ROOT / 'generate_trans/folds/hosts_bt31'
    lib = nl.load_library(folds / 'verilog_lib.v')
    glib = enc.load_library(folds / 'verilog_lib.v')
    mapping = {r['full_gate_name']: r['simplified_gate_type']
               for r in read(folds / 'gate_full_to_simplified_mapping.json')}
    gate_order = read(folds / 'gatelookup_recommended.json')['simplified_gate_type_order']
    norm = np.load(V3 / 'normalization.npz')
    inputs = read(V3 / 'input_contract.json')['shared_inputs']
    validation = ROOT / inputs['trans_val']['folder']
    y, trust, physical = (np.load(validation / (n + '.npy')) for n in ('y','trusted','physical'))
    positive = (y == 1) & trust & physical
    assert positive.sum() > 0 and torch.cuda.is_available()
    runs = OUT.parent / 'seed42_nc_ablation_20261109'
    models, thresholds = {}, {}
    for seed in (42,1,2):
        stem = 'NC' if seed == 42 else f'NC_s{seed}'
        with np.load(runs / f'{stem}_scores.npz') as z:
            assert np.array_equal(z['y_val'], y) and np.array_equal(z['trust_val'], trust)
            for point in ('best','last'):
                model_path = runs / f'{stem}_{point}.pt'
                model = evaluation.Model().cuda()
                model.load_state_dict(torch.load(model_path,map_location='cuda',weights_only=True),strict=True)
                models[seed, point] = model.eval()
                pred = z[f'val_{point}'][positive]
                cut = float(np.sort(pred)[-int(np.ceil(.95 * len(pred)))])
                thresholds[f'{seed}_{point}'] = dict(cut=cut, val_positive=len(pred),
                    val_recall=float((pred >= cut).mean()), checkpoint_sha=digest(model_path))
    write_json(OUT / 'FROZEN_THRESHOLDS.json', thresholds)

    score_rows, region_rows, truth_rows, proof_rows = [], [], [], []
    graph_dir = OUT / 'graphs'
    graph_dir.mkdir(exist_ok=True)
    for rec in cases:
        view = rec['view']
        path = ROOT / rec['target']
        log = OUT / 'logs' / f'{view}.txt'
        proof = re.search(r'\[CEC\] rc=0 total=(\d+) proven=(\d+) unproven=0 PASS', log.read_text())
        assert proof and proof[1] == proof[2] and int(proof[1]) > 0, view
        assert digest(path) == rec['target_sha256'] and digest(ROOT / rec['clean']) == rec['clean_sha256']
        proof_rows.append(dict(view=view, total=int(proof[1]), proven=int(proof[2]), unproven=0,
                               summary_sha=digest(log), target_sha=rec['target_sha256']))
        old_path = ROOT / 'generate_trans/hosts_a4' / rec['host'] / (rec['old_view'] + '.v')
        assert digest(old_path) == rec['old_sha256']
        for kind, netlist, region in (
            ('live', path, rec['region']),
            ('dead', old_path, rec['old_region']),
        ):
            circuit = nl.parse_netlist(netlist, lib)
            names = [cell.name for cell in circuit.insts]
            if kind == 'live':
                truth_rows.append(local_truth(rec, circuit))
            g = enc.parse(stripped(netlist), names, glib)
            raw = enc.features(g, mapping, gate_order)
            indices = {name: idx for idx, name in enumerate(names)}
            region_ids = np.array([indices[n] for n in region], dtype=np.int64)
            native = np.ones(len(names), dtype=bool)
            native[region_ids] = False
            x = raw.copy()
            x[:,25:] = np.clip((x[:,25:] - norm['mean'][25:]) / norm['std'][25:], -10, 10)
            xt = torch.tensor(x, device='cuda')
            edge = torch.tensor(g['edge_index'], device='cuda', dtype=torch.long)
            decisions, margins = {}, {}
            for (seed, point), model in models.items():
                key = f'{seed}_{point}'
                with torch.inference_mode(), torch.autocast('cuda',dtype=torch.bfloat16):
                    logits = model(xt,edge).float()
                pred = (logits[:,1]-logits[:,0]).cpu().numpy()[:len(names)]
                cut = thresholds[key]['cut']
                flagged = pred >= cut
                decisions[key], margins[key] = flagged[region_ids], pred[region_ids]
                score_rows.append(dict(view=view, host=rec['host'], split=rec['split'], kind=kind,
                    seed=seed, point=point, region_n=len(region_ids), region_fp=int(flagged[region_ids].sum()),
                    native_n=int(native.sum()), native_fp=int(flagged[native].sum()),
                    best_rank=1+int((pred > pred[region_ids].max()).sum())))
            if kind == 'live':
                graph_path = graph_dir / f'{view}.npz'
                np.savez_compressed(graph_path, x39=raw, edge_index=g['edge_index'], edge_roles=g['edge_roles'],
                    physical_names=names, region_rows=region_ids)
                graph_sha = digest(graph_path)
            else:
                graph_sha = ''
            votes = np.sum(list(decisions.values()), axis=0)
            for i, (name, row) in enumerate(zip(region, region_ids)):
                region_rows.append(dict(view=view, host=rec['host'], split=rec['split'], kind=kind, node=name,
                    gate=g['types'][row], row=int(row), votes=int(votes[i]), hard=int(votes[i] >= 4),
                    netlist_sha=digest(netlist) if kind == 'dead' else rec['target_sha256'], graph_sha=graph_sha,
                    **{f'margin_{key}':float(margins[key][i]) for key in margins}))
        print(rec['split'], view, flush=True)
    csv_out(OUT / 'CEC_RESULTS.csv', proof_rows)
    write_json(OUT / 'LOCAL_TRUTH.json', truth_rows)
    csv_out(OUT / 'SCORE_BY_VIEW.csv', score_rows)
    csv_out(OUT / 'REGION_NODE_SCORES.csv', region_rows)
    for split in ('train','val','test'):
        subset = [r for r in region_rows if r['split'] == split and r['kind'] == 'live']
        if split == 'test':
            csv_out(OUT / 'TEST_LIVE_NODES.csv', subset)
        else:
            selected = [r for r in subset if r['hard']]
            if selected:
                csv_out(OUT / f'{split.upper()}_HARD.csv', selected)
            else:
                (OUT / f'{split.upper()}_HARD.csv').write_text(','.join(subset[0])+'\n',encoding='utf-8')
    summary = {}
    for host in sorted({r['host'] for r in cases}):
        cc = [r for r in cases if r['host']==host]
        row = dict(split=cc[0]['split'], views=len(cc), gates=dict(Counter(r['replaced_gate'] for r in cc)))
        for kind in ('live','dead'):
            subset = [r for r in region_rows if r['host']==host and r['kind']==kind]
            sample = [r for r in score_rows if r['host']==host and r['kind']==kind]
            row[kind] = dict(nodes=len(subset), hard=sum(r['hard'] for r in subset),
                hard_views=len({r['view'] for r in subset if r['hard']}),
                region_fpr=sum(r['region_fp'] for r in sample)/sum(r['region_n'] for r in sample),
                native_fpr=sum(r['native_fp'] for r in sample)/sum(r['native_n'] for r in sample))
        summary[host] = row
    write_json(OUT / 'SUMMARY.json', summary)


if __name__ == '__main__':
    main()
