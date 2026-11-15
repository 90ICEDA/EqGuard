"""Emit the clean reference from Yosys JSON and check the frozen feature interface."""
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
FOLD = ROOT/'generate_trans/folds/hosts_bt31'
V3 = OUT.parent/'control_boundary_v3_20261104'
sys.path.insert(0, str(V3))
import feature_encoding_v3_po as v3

CELLS = {
    'AND': ('AND2X1_RS', dict(A='A', B='B', Y='Y')),
    'OR': ('OR2X1_RS', dict(A='A', B='B', Y='Y')),
    'XOR': ('XOR2X1_RS', dict(A='A', B='B', Y='Y')),
    'XNOR': ('XNOR2X1', dict(A='IN1', B='IN2', Y='Q')),
    'NOT': ('INVX1_RS', dict(A='A', Y='Y')),
    'MUX': ('MX2X1_RS', dict(A='A', B='B', S='S0', Y='Y')),
    'DFF_P': ('DFFX2', dict(C='CLK', D='D', Q='Q')),
}


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def csv_out(name, rows):
    with (OUT/name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    contract = read(OUT/'STATIC_INPUT.json')
    assert sha(ROOT/contract['source']) == contract['source_sha256']
    lib_path = FOLD/'verilog_lib.v'
    lookup_path = FOLD/'gatelookup_recommended.json'
    assert sha(lib_path) == contract['frozen_inputs']['graph_library_sha256']
    assert sha(lookup_path) == contract['frozen_inputs']['gate_lookup_sha256']
    assert sha(V3/'input_contract.json') == contract['frozen_inputs']['feature_contract_sha256']
    assert sha(V3/'normalization.npz') == contract['frozen_inputs']['normalization_sha256']
    assert sha(ROOT.parent/'GraphSAINT-train/vali/verilog_lib.v') == contract['frozen_inputs']['historical_synthesis_library_sha256']
    design = read(OUT/'clean_generic.json')
    assert set(design['modules']) == {'picorv32'}
    m = design['modules']['picorv32']
    ports = m['ports']
    cells = m['cells']
    assert not any('init' in n.get('attributes',{}) or 'keep' in n.get('attributes',{})
                   for n in m['netnames'].values())
    lib = v3.load_library(lib_path)
    lookup = read(lookup_path)
    order = lookup['simplified_gate_type_order']
    mapping = {r['full_gate_name']:r['simplified_gate_type']
               for r in read(FOLD/'gate_full_to_simplified_mapping.json')}
    assert ['gate_'+k for k in order] == v3.COLS[:25]
    assert read(V3/'input_contract.json')['columns39'] == v3.COLS
    names, drivers, consumers = [], {}, defaultdict(set)
    wire_bits = set()
    inputs, po, lines, state = {}, [], [], []
    for name,p in ports.items():
        assert not (p.get('offset') or p.get('upto'))
        bits = p['bits']
        direction = p['direction']
        assert direction in ('input','output')
        width = f' [{len(bits)-1}:0]' if len(bits)>1 else ''
        lines.append(f'  {direction}{width} {name};')
        for i,b in enumerate(bits):
            port = f'{name}[{i}]' if width else name
            if direction=='input':
                assert isinstance(b,int) and b not in inputs
                inputs[b] = port
            else:
                po.append((port,b))
    q_aliases = defaultdict(list)
    for n,v in m['netnames'].items():
        if not v['hide_name']:
            for i,b in enumerate(v['bits']):
                if isinstance(b,int):
                    q_aliases[b].append(f'{n}:{i+v.get("offset",0)}')
    def signal(bit):
        return inputs.get(bit,f'n{bit}') if isinstance(bit,int) else f"1'b{bit}"
    gates = []
    for j,(source,c) in enumerate(sorted(cells.items())):
        typ = c['type']
        assert typ.startswith('$_') and typ.endswith('_')
        generic = typ[2:-1]
        cell,pins = CELLS[generic]
        assert set(c['connections'])==set(pins) and not c['parameters']
        pininfo = lib[cell]
        assert pininfo['scalar'] and set(pins.values())==set(pininfo['input']+pininfo['output'])
        name = f'g{j:05d}'
        names.append(name)
        connections = {}
        for old,new in pins.items():
            bit, = c['connections'][old]
            assert isinstance(bit,int)
            direction = c['port_directions'][old]
            assert new in pininfo[direction]
            if direction=='output':
                assert bit not in drivers and bit not in inputs
                drivers[bit] = name
            else:
                consumers[bit].add(name)
            if bit not in inputs:
                wire_bits.add(bit)
            connections[new] = signal(bit)
        gates.append(f'  {cell} {name} ('+', '.join(f'.{p}({n})' for p,n in connections.items())+');')
        if generic=='DFF_P':
            d,q,clk = (c['connections'][p][0] for p in ('D','Q','C'))
            assert clk in inputs and inputs[clk]=='clk'
            state.append(dict(cell=name,yosys_cell=source,d_bit=d,q_bit=q,clock_bit=clk,
                              d_signal=signal(d),q_signal=signal(q),q_aliases='|'.join(sorted(q_aliases[q]))))
    assert len({r['q_bit'] for r in state})==len(state) and consumers.keys()<=drivers.keys()|inputs.keys()
    for port,bit in po:
        assert bit in drivers or bit in inputs or bit in ('0','1','x')
        lines.append(f'  assign {port} = {signal(bit)};')
    wires = [f'  wire n{b};' for b in sorted(wire_bits)]
    source = OUT/'picorv32_clean.v'
    source.write_text('module picorv32_clean('+', '.join(ports)+');\n'+'\n'.join(
        lines[:len(ports)]+wires+gates+lines[len(ports):])+'\nendmodule\n',encoding='utf-8')
    graph = v3.parse(source,names,lib)
    assert graph['original_nodes']==len(cells) and not graph['virtual_nodes']
    features = v3.features(graph,mapping,order)
    assert features.shape==(len(cells),39) and (features[:,:25].sum(1)==1).all()
    with np.load(V3/'normalization.npz') as z:
        scaled = (features[:,25:]-z['mean'][25:])/z['std'][25:]
    normalized = features.copy()
    normalized[:,25:] = np.clip(scaled,-10,10)
    assert np.isfinite(normalized).all()
    index = {n:i for i,n in enumerate(names)}
    roots = {index[drivers[b]] for _,b in po if b in drivers}
    assert roots==set(np.flatnonzero(graph['PO_driver']))==set(np.flatnonzero(features[:,30]==0))
    edges = set(map(tuple,graph['edge_index'].T.tolist()))
    assert edges=={(index[drivers[b]],index[c]) for b,cs in consumers.items() if b in drivers for c in cs}
    back = defaultdict(list)
    for a,b in edges:
        back[b].append(a)
    distances = np.full(len(cells),-1)
    distances[list(roots)] = 0
    todo = deque(sorted(roots))
    while todo:
        b = todo.popleft()
        for a in back[b]:
            if distances[a]<0:
                distances[a] = distances[b]+1
                todo.append(a)
    assert np.array_equal(distances,features[:,30])
    roles = dict(zip(map(tuple,graph['edge_index'].T.tolist()),graph['edge_roles']))
    for r in state:
        assert drivers[r['q_bit']]==r['cell']
        if r['d_bit'] in drivers:
            assert roles[index[drivers[r['d_bit']]],index[r['cell']]] & 1
    csv_out('D_Q_BITS.csv',state)
    po_rows = [dict(port=port,bit=bit,kind='cell' if bit in drivers else 'direct_pi' if bit in inputs
                    else 'undefined' if bit=='x' else 'constant',driver=drivers.get(bit,'')) for port,bit in po]
    csv_out('PO_BITS.csv',po_rows)
    (OUT/'NODE_NAMES.txt').write_text('\n'.join(names)+'\n',encoding='utf-8')
    np.savez_compressed(OUT/'GRAPH39_V3.npz',x39=features,x=normalized,edge_index=graph['edge_index'],
                        edge_roles=graph['edge_roles'],physical=np.ones(len(names),dtype=bool))
    result = dict(cells=len(cells),types=Counter(graph['types']),dff=len(state),clock='clk',
                  cpuregs_q_bits=sum(any(a.startswith('cpuregs[') for a in q_aliases[r['q_bit']]) for r in state),
                  po_bits=Counter(r['kind'] for r in po_rows),po_driver_nodes=len(roots),edges=len(edges),
                  po_reachable=int((distances>=0).sum()),clipped_entries=int((np.abs(scaled)>10).sum()),
                  hashes={n:sha(OUT/n) for n in ('clean.ys','clean_generic.json','picorv32_clean.v','D_Q_BITS.csv',
                                                 'PO_BITS.csv','GRAPH39_V3.npz','NODE_NAMES.txt')})
    (OUT/'CLEAN_AUDIT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result)


if __name__=='__main__':
    main()
