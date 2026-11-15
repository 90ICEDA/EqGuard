"""Replace a live host gate with an equivalent, sensitizable gate network."""
import csv
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
V3 = OUT.parent/'control_boundary_v3_20261104'
sys.path[:0] = [str(ROOT), str(V3)]
from phase2 import netlist_lib as nl
from independent_net import raw_network
import feature_encoding_v3_po as enc


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def linux(path):
    p = path.resolve().as_posix()
    return f'/mnt/{p[0].lower()}{p[2:]}'


def csv_out(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def ports(graph, lib):
    """Reverse distance to a PO driver or D input driver, stopping at state."""
    goals = set(graph['pocells'])
    for _,(typ,pins) in graph['pins'].items():
        if 'DFF' in typ:
            for pin,net in pins:
                if pin=='D':
                    goals.update(graph['drivers'][net])
    depth = dict.fromkeys(goals,0)
    q = deque(sorted(goals))
    while q:
        c = q.popleft()
        if 'DFF' in graph['pins'][c][0]:
            continue
        for p in sorted(graph['pred'][c]):
            if p not in depth:
                depth[p] = depth[c]+1
                q.append(p)
    return depth


def stripped(path):
    target = OUT/'parse_inputs'/path.name
    target.parent.mkdir(exist_ok=True)
    s = path.read_text(encoding='utf-8')
    target.write_text(re.sub(r'(?m)^\s*`timescale[^\n]*\n','\n',s),encoding='utf-8')
    return target


def main():
    lib_path = ROOT/'generate_trans/folds/hosts_bt31/verilog_lib.v'
    lib = nl.load_library(lib_path)
    glib = enc.load_library(lib_path)
    pins = {'XOR2X1':('IN1','IN2','Q'),'XOR2X1_RS':('A','B','Y'),
            'XNOR2X1':('IN1','IN2','Q'),'AND2X1':('IN1','IN2','Q'),
            'AND2X1_RS':('A','B','Y'),'AND2X2':('IN1','IN2','Q'),
            'OR2X1':('IN1','IN2','Q'),'OR2X1_RS':('A','B','Y')}
    contract = read(V3/'input_contract.json')['shared_inputs']
    split = {v['view'].split('__')[0]:s for s in ('train','val','test')
             for v in contract['orig_'+s]['views']}
    inventory = ROOT/'generate_trans/hosts_a4'
    cases=[]
    for folder in sorted(inventory.iterdir()):
        host=folder.name
        if host not in split:
            continue
        clean=folder/'base'/f'{host}_clean.v'
        base = nl.parse_netlist(clean,lib)
        graph = raw_network(stripped(clean),lib)
        depth = ports(graph,lib)
        usable=[]
        for c in base.insts:
            if c.gate not in pins or c.name not in depth:
                continue
            a,b,y=(dict(c.conns)[p] for p in pins[c.gate])
            canon=[graph['find'](n.lstrip('\\')) for n in (a,b,y)]
            if len(set(canon))!=3 or any(n.startswith('#') for n in canon):
                continue
            usable.append(c)
        usable.sort(key=lambda c:(not c.gate.startswith(('XOR','XNOR')),depth[c.name],c.name))
        variants=sorted(folder.glob('*__a4ctldead_*.v'))
        records = {r['view']:r for r in read(folder/'provenance.json')}
        assert len(variants)==8 and len(usable)>=len(variants),(host,len(usable))
        for ordinal,old in enumerate(variants):
            original=records[old.stem]
            assert original['a4_family']=='ctldead'
            c=usable[ordinal]
            a,b,y=(dict(c.conns)[p] for p in pins[c.gate])
            fresh=[f'lc_{ordinal}_{i}' for i in range(11)]
            assert all(not re.search(r'(?<!\w)'+n+r'(?!\w)',clean.read_text(encoding='utf-8')) for n in fresh)
            na,nb,p0,p1=fresh[:4]
            gate = c.gate
            spec=[('INVX1_RS',[a],na),('INVX1_RS',[b],nb)]
            if gate.startswith(('XOR','XNOR')):
                cross = gate.startswith('XOR')
                spec += [('AND2X1_RS',[a,nb if cross else b],p0),
                         ('AND2X1_RS',[na,b if cross else nb],p1),('OR2X1_RS',[p0,p1],y)]
            else:
                spec += [('NOR2X1_RS' if gate.startswith('AND') else 'NAND2X1_RS',[na,nb],y)]
            new_names=fresh[5:5+len(spec)]
            repl=[nl.Inst(typ,n,list(zip(('A','B')[:len(args)],args))+[('Y',o)])
                  for n,(typ,args,o) in zip(new_names,spec)]
            model=nl.parse_netlist(clean,lib)
            model.insts=[x for x in model.insts if x.name!=c.name]+repl
            model.port_decls.extend(f'wire {o}' for _,_,o in spec if o!=y)
            name=old.stem.replace('a4ctldead','a4ctllive')
            model.head=re.sub(r'\bmodule\s+'+re.escape(model.module)+r'\b','module '+name,model.head,count=1)
            model.module=name
            dest=OUT/'netlists'/host/f'{name}.v'
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(nl.emit_netlist(model),encoding='utf-8')
            parsed=raw_network(stripped(dest),lib)
            assert set(parsed['cells'])==set(graph['cells'])-{c.name}|set(new_names)
            assert all(parsed['cells'][n]==graph['cells'][n] for n in graph['cells'] if n!=c.name)
            distances=ports(parsed,lib)
            assert all(n in distances for n in new_names)
            features=enc.parse(stripped(dest),[i.name for i in model.insts],glib)
            assert all(g.gate in features['types'] for g in repl)
            cases.append(dict(view=name,host=host,split=split[host],recipe='orig',old_view=old.stem,
                              old_sha256=digest(old),clean=str(clean.relative_to(ROOT)),clean_sha256=digest(clean),
                              target=str(dest.relative_to(ROOT)),target_sha256=digest(dest),
                              replaced_cell=c.name,replaced_gate=c.gate,host_inputs=[a,b],host_output=y,
                              region=dict(zip(new_names,[g.gate for g in repl])),
                              endpoint_distance={n:distances[n] for n in new_names},
                              old_shape=original['a4_shape'],old_region=original['new_gates']))
    (OUT/'MANIFEST.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
    vali=ROOT.parent/'GraphSAINT-train/vali'
    (OUT/'logs').mkdir(exist_ok=True)
    jobs=[]
    for r in cases:
        log=OUT/'logs'/r['view']
        args=[linux(ROOT/'generate_trans/cec/direct_cec.py'),'--golden',linux(ROOT/r['clean']),
              '--candidate',linux(ROOT/r['target']),'--vali-dir',linux(vali),
              '--timeout','180','--log',linux(log.with_suffix('.log'))]
        jobs.append('python3 '+' '.join(args)+' > '+linux(log.with_suffix('.txt'))+' 2>&1')
    (OUT/'cec_jobs.txt').write_text('\n'.join(jobs)+'\n',encoding='utf-8',newline='\n')
    print('prepared',len(cases),flush=True)


if __name__=='__main__':
    main()
