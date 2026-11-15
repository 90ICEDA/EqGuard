"""Check frozen feature parity and bind split-specific negative-pool rows."""
import csv

import numpy as np

from build import OUT, ROOT, V3, digest, enc, read, stripped


def main():
    folders = ROOT / 'generate_trans/folds/hosts_bt31'
    contract = read(V3 / 'input_contract.json')['shared_inputs']
    order = read(folders / 'gatelookup_recommended.json')['simplified_gate_type_order']
    mapping = {r['full_gate_name']: r['simplified_gate_type']
               for r in read(folders / 'gate_full_to_simplified_mapping.json')}
    lib = enc.load_library(folders / 'verilog_lib.v')
    names = (OUT.parent / 'round32_20261029/orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines()
    d = contract['orig_train']
    old_x = np.load(ROOT / d['folder'] / 'x39.npy', mmap_mode='r')
    old_edge = np.load(ROOT / d['folder'] / 'edge_index.npy', mmap_mode='r')
    parity = 0
    for v in d['views']:
        if '__a4ctldead_' not in v['view']:
            continue
        physical = [s.strip().lstrip('\\') for s in names[v['old_start']:v['old_stop']]]
        source = folders / 'orig' / (v['view'] + '.v')
        g = enc.parse(stripped(source), physical, lib)
        x = enc.features(g, mapping, order)
        lo, hi = v['start'], v['stop']
        idx = (old_edge[0] >= lo) & (old_edge[0] < hi)
        assert np.array_equal(old_edge[:,idx] - lo, g['edge_index']), v['view']
        assert np.allclose(old_x[lo:hi], x, atol=1e-6, rtol=0), v['view']
        parity += 1
    assert parity == 4

    cases = {r['view']: r for r in read(OUT / 'MANIFEST.json')}
    for split in ('train','val'):
        table = OUT / f'{split.upper()}_HARD.csv'
        with table.open(encoding='utf-8',newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len({(r['view'],r['row']) for r in rows})
        target = OUT / f'{split.upper()}_NEGATIVE_POOL.csv'
        with target.open('w',encoding='utf-8',newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['split','view','host','row','node','label','trusted','optimizer_eligible',
                             'votes','graph_sha','netlist_sha'])
            for r in rows:
                c = cases[r['view']]
                graph = OUT / 'graphs' / (r['view'] + '.npz')
                assert r['split'] == c['split'] == split and int(r['votes']) >= 4
                assert r['netlist_sha'] == c['target_sha256'] and r['graph_sha'] == digest(graph)
                with np.load(graph) as g:
                    row = int(r['row'])
                    assert row in g['region_rows'] and g['physical_names'][row] == r['node']
                writer.writerow([split,r['view'],r['host'],row,r['node'],0,1,int(split=='train'),
                                 r['votes'],r['graph_sha'],r['netlist_sha']])
        print(split, len(rows), 'bound')
    print(parity, 'frozen source graphs matched in all 39 dimensions and directed edges')


if __name__ == '__main__':
    main()
