"""Unrestricted combinational physical-Q context and source-bound runner."""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round10'
WORK=ROOT/'generate_trans/folds/hosts_bt31'
sys.path.insert(0,str(ROOT/'phase2/ys'))
import sat_functional_relations as P0

ROWS=[];START=time.monotonic();MODULES={}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def load(view):
    if view in MODULES:return MODULES[view]
    source=WORK/'trans'/(view+'.v');top=P0.module_name(source)
    folder=OUT/'structures'/view;folder.mkdir(parents=True,exist_ok=True)
    raw=folder/'raw.json'
    if raw.exists():raise RuntimeError('Existing raw snapshot: use fresh output root')
    script=f'read_verilog "{P0.wsl(source)}"\nhierarchy -top {top}\nflatten\nproc -noopt\nwrite_json "{P0.wsl(raw)}"\n'
    (folder/'prepare.ys').write_text(script,encoding='utf-8')
    log=P0.run_yosys(script,folder/'prepare.log',timeout=120)
    if 'ERROR:' in log:raise ValueError('raw parse failed '+view)
    m=json.loads(raw.read_text())['modules'][top]
    MODULES[view]=m
    (folder/'source.json').write_text(json.dumps(dict(view=view,source_sha=sha(source),raw_sha=sha(raw)),indent=2),encoding='utf-8')
    return m


def layout(m):
    offset=0;ports={}
    for n,p in sorted(m['ports'].items()):
        if p['direction']=='input':
            ports[n]=list(range(offset,offset+len(p['bits'])));offset+=len(p['bits'])
    states=sorted(n for n,c in m['cells'].items() if 'DFF' in c['type'].upper())
    return ports,{n:offset+i for i,n in enumerate(states)},offset+len(states)


def emit(m,name,nets):
    ports,states,width=layout(m)
    bit=lambda bs: bs[0] if len(bs)==1 else (_ for _ in ()).throw(ValueError('scalar required'))
    s=lambda b:f'b{b}' if isinstance(b,int) else "1'b"+b
    probes=[bit(m['netnames'][n]['bits']) if n in m['netnames'] else bit(m['ports'][n]['bits']) for n in nets]
    obs=[(n,i,b) for n,p in sorted(m['ports'].items()) if p['direction']=='output' for i,b in enumerate(p['bits'])]
    obs += [(n+'.D',0,bit(m['cells'][n]['connections']['D'])) for n in sorted(states)]
    bits=sorted({b for c in m['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)} |
                {b for p in m['ports'].values() for b in p['bits'] if isinstance(b,int)})
    lines=[f'module {name}(input [{width-1}:0] env,output [4:0] sigs,output [{len(obs)-1}:0] obs);',
           'wire '+','.join(s(b) for b in bits)+';']
    for n,offsets in ports.items():lines += [f'assign {s(b)}=env[{i}];' for b,i in zip(m['ports'][n]['bits'],offsets)]
    for n,c in m['cells'].items():
        con=c['connections'];typ=c['type'];g=lambda p:s(bit(con[p]))
        if n in states:
            for p,invert in [('Q',False),('QN',True)]:
                if p in con:
                    if not isinstance(bit(con[p]),int):raise ValueError('constant state output')
                    lines.append(f'assign {g(p)}={"~" if invert else ""}env[{states[n]}];')
            continue
        if typ=='AND2X2':op,ex='Q',f'{g("IN1")}&{g("IN2")}'
        elif typ=='OR2X1':op,ex='Q',f'{g("IN1")}|{g("IN2")}'
        elif typ=='XOR2X1':op,ex='Q',f'{g("IN1")}^{g("IN2")}'
        elif typ=='INVX0':op,ex='QN',f'~{g("IN")}'
        elif typ=='MX2X1_RS':op,ex='Y',f'{g("S0")}?{g("B")}:{g("A")}'
        elif typ in ('$and','$or','$xor'):
            symbol={'$and':'&','$or':'|','$xor':'^'}[typ];op,ex='Y',f'{g("A")}{symbol}{g("B")}'
        elif typ=='$not':op,ex='Y',f'~{g("A")}'
        elif typ=='$mux':op,ex='Y',f'{g("S")}?{g("B")}:{g("A")}'
        else:raise ValueError('unsupported cell '+typ)
        lines.append(f'assign {g(op)}={ex};')
    lines += [f'assign sigs={{{",".join(s(b) for b in reversed(probes))}}};',
              f'assign obs={{{",".join(s(b) for _,_,b in reversed(obs))}}};','endmodule']
    return '\n'.join(lines),dict(width=width,ports=ports,states=states,obs=[(n,i) for n,i,b in obs],probes=probes)


def run(folder,code,queries):
    if len(ROWS)+len(queries)>576 or time.monotonic()-START>1500:raise RuntimeError('query/wall cap')
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'run.log').exists():raise RuntimeError('Refuse to overwrite evidence')
    model=folder/'model.v';model.write_text(code,encoding='utf-8')
    commands=[f'read_verilog "{P0.wsl(model)}"','hierarchy -top check','proc','flatten','opt_clean']
    for i,q in enumerate(queries):
        commands += [f'log Q{i:04d}',f'sat {q["args"]} -timeout 5 -show-inputs -show-outputs -dump_json "{P0.wsl(folder/(str(i)+".model.json"))}"']
    script='\n'.join(commands)+'\n';(folder/'run.ys').write_text(script,encoding='utf-8')
    log=P0.run_yosys(script,folder/'run.log',timeout=420)
    blocks={};current=None
    for line in log.splitlines():
        if line.startswith('Q') and len(line)==5 and line[1:].isdigit():current=int(line[1:]);blocks[current]=[]
        elif current is not None:blocks[current].append(line)
    results=[]
    for i,q in enumerate(queries):
        text='\n'.join(blocks.get(i,[]))
        status='proved' if 'no model found: SUCCESS' in text else 'refuted' if 'model found: FAIL' in text else 'unknown'
        if 'ERROR:' in log:status='error'
        witness=folder/(str(i)+'.model.json')
        row=dict(**q,status=status,timeout='TIMEOUT' in text,query_id=i,folder=str(folder.relative_to(ROOT)),
            model_sha=sha(model),script_sha=hashlib.sha256(script.encode()).hexdigest(),log_sha=sha(folder/'run.log'),
            witness=str(witness.relative_to(ROOT)) if witness.exists() else '')
        (folder/(str(i)+'.query.log')).write_text(q['args']+'\n'+text,encoding='utf-8')
        ROWS.append(row);results.append(row)
    return results
