"""Two prescribed mechanism cases; shared PI/physical register-state checks.

Combinational state-boundary semantics, not reset/protocol reachability.
Explicit six-cell emitter, independent Python witness replay, no training.
"""
import copy
import hashlib
import itertools
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'generate_trans/folds/hosts_bt31'
OUT = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_cases_round8'
sys.path.insert(0, str(ROOT / 'phase2/ys'))
import sat_functional_relations as P0

STEPS, ROWS, MODULES = [], [], {}
START = time.monotonic()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def scalar(bits):
    if len(bits) != 1:
        raise ValueError('scalar port required')
    return bits[0]


def sig(bit):
    return f'b{bit}' if isinstance(bit, int) else "1'b" + bit


def setup(view):
    source = WORK / 'trans' / (view + '.v')
    folder = OUT / view
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / 'run.log').exists():
        raise RuntimeError('Existing query evidence: use a fresh versioned output root')
    raw = folder / 'raw.json'
    top = P0.module_name(source)
    script = f'read_verilog "{P0.wsl(source)}"\nhierarchy -top {top}\nflatten\nproc -noopt\nwrite_json "{P0.wsl(raw)}"\n'
    (folder / 'prepare.ys').write_text(script, encoding='utf-8')
    P0.run_yosys(script, folder / 'prepare.log', timeout=60)
    m = json.loads(raw.read_text())['modules'][top]
    MODULES[view] = m
    return source, folder, m


def layout(m):
    ports = sorted((n, p['bits']) for n, p in m['ports'].items() if p['direction'] == 'input')
    states = sorted(n for n, c in m['cells'].items() if 'DFF' in c['type'].upper())
    names, offset = {}, 0
    for n, bits in ports:
        names[n] = list(range(offset, offset + len(bits)))
        offset += len(bits)
    state_offsets = {n: offset + i for i, n in enumerate(states)}
    return ports, names, state_offsets, offset + len(states)


def emit(m, module, prefix, probe_names=None):
    ports, offsets, states, width = layout(m)
    probe_names = probe_names or (prefix + 'HJ.S0', prefix + 'HJ.A', prefix + 'HJ.B', prefix + 'HJ.Y', 'rec_readyH')
    probes = [scalar(m['netnames'][n]['bits']) for n in probe_names]
    ctrl = probes[0]
    observation = [(n, i, b) for n, p in sorted(m['ports'].items()) if p['direction'] == 'output'
                   for i, b in enumerate(p['bits'])]
    observation += [(n + '.D', 0, scalar(m['cells'][n]['connections']['D'])) for n in sorted(states)]
    bits = sorted({b for c in m['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b, int)})
    lines = [f'module {module}(input [{width-1}:0] env, input intervention, input value, output [4:0] p, output [{len(observation)-1}:0] obs);',
             'wire ' + ','.join(sig(b) for b in bits) + ';']
    control_drivers = 0
    for n, bs in ports:
        lines += [f'assign {sig(b)} = env[{o}];' for b, o in zip(bs, offsets[n])]
    for n, c in m['cells'].items():
        con = c['connections']
        get = lambda p: sig(scalar(con[p]))
        typ = c['type']
        if n in states:
            for pin, inv in [('Q', False), ('QN', True)]:
                if pin in con:
                    lines.append(f'assign {get(pin)} = {"~" if inv else ""}env[{states[n]}];')
            continue
        expressions = {
            'AND2X2': lambda: (con['Q'], f'{get("IN1")} & {get("IN2")}'),
            'OR2X1': lambda: (con['Q'], f'{get("IN1")} | {get("IN2")}'),
            'XOR2X1': lambda: (con['Q'], f'{get("IN1")} ^ {get("IN2")}'),
            'INVX0': lambda: (con['QN'], f'~{get("IN")}'),
            '$and': lambda: (con['Y'], f'{get("A")} & {get("B")}'),
            '$mux': lambda: (con['Y'], f'{get("S")} ? {get("B")} : {get("A")}'),
            'MX2X1_RS': lambda: (con['Y'], f'{get("S0")} ? {get("B")} : {get("A")}')}
        if typ not in expressions:
            raise ValueError('unsupported cell ' + typ)
        out, expr = expressions[typ]()
        bit = scalar(out)
        if bit == ctrl:
            control_drivers += 1
            expr = f'intervention ? value : ({expr})'
        lines.append(f'assign {sig(bit)} = {expr};')
    if control_drivers != 1:
        raise ValueError('global intervention requires one combinational driver')
    lines += [f'assign p = {{{",".join(sig(b) for b in reversed(probes))}}};',
              f'assign obs = {{{",".join(sig(b) for _, _, b in reversed(observation))}}};', 'endmodule']
    return '\n'.join(lines), dict(width=width, input_offsets=offsets, state_offsets=states,
        probes=probes, observations=[(n, i) for n, i, b in observation], control_bit=ctrl)


def run_queries(folder, verilog, queries):
    if (folder / 'run.log').exists():
        raise RuntimeError('Refusing to overwrite existing solver evidence')
    if len(ROWS) + len(queries) > 192 or time.monotonic() - START > 1500:
        raise RuntimeError('budget cap')
    model = folder / 'model.v'
    model.write_text(verilog, encoding='utf-8')
    commands = [f'read_verilog "{P0.wsl(model)}"', 'hierarchy -top check', 'proc', 'flatten', 'opt_clean']
    for i, q in enumerate(queries):
        commands += [f'log QUERY{i:04d}', f'sat {q["args"]} -timeout 5 -show-inputs -show-outputs -dump_json "{P0.wsl(folder / (str(i)+".model.json"))}"']
    script = '\n'.join(commands) + '\n'
    (folder / 'run.ys').write_text(script, encoding='utf-8')
    out = P0.run_yosys(script, folder / 'run.log', timeout=180)
    blocks = {}
    current = None
    for ln in out.splitlines():
        if ln.startswith('QUERY') and ln[5:].isdigit():
            current = int(ln[5:]); blocks[current] = []
        elif current is not None:
            blocks[current].append(ln)
    for i, q in enumerate(queries):
        text = '\n'.join(blocks.get(i, []))
        st = 'proved' if 'no model found: SUCCESS' in text else 'refuted' if 'model found: FAIL' in text else 'unknown'
        if 'ERROR:' in out:
            st = 'error'
        row = dict(**q, status=st, query_id=i, folder=str(folder.relative_to(ROOT)),
                   script_sha=hashlib.sha256(script.encode()).hexdigest(), model_sha=sha(model),
                   log_sha=sha(folder / 'run.log'), witness=str((folder / (str(i)+'.model.json')).relative_to(ROOT)) if (folder / (str(i)+'.model.json')).exists() else '')
        (folder / (str(i)+'.query.log')).write_text(q['args'] + '\n' + text, encoding='utf-8')
        ROWS.append(row)
    return ROWS[-len(queries):]


def evaluate(m, env, control=None):
    """Independent Boolean replay; SAT environment must be fully defined."""
    ports, offsets, states, width = layout(m)
    if any(x not in '01' for x in env) or len(env) != width:
        raise ValueError('undefined or wrong-width environment')
    vals = {str(i): int(i) for i in (0, 1)}
    ev = list(map(int, reversed(env)))
    for name, bits in ports:
        for b, o in zip(bits, offsets[name]): vals[b] = ev[o]
    pending = []
    for n, c in m['cells'].items():
        if n in states:
            for pin, inv in [('Q', 0), ('QN', 1)]:
                if pin in c['connections']: vals[scalar(c['connections'][pin])] = ev[states[n]] ^ inv
        else: pending.append(c)
    if control is not None: vals[control[0]] = control[1]
    while pending:
        progress = False
        for c in pending[:]:
            cs, typ = c['connections'], c['type']
            outpin = 'QN' if typ == 'INVX0' else 'Y' if typ in ('MX2X1_RS', '$and', '$mux') else 'Q'
            ob = scalar(cs[outpin])
            if control is not None and ob == control[0]:
                pending.remove(c); progress = True; continue
            try:
                g = lambda pin: vals[scalar(cs[pin])]
                v = (g('B') if g('S') else g('A')) if typ == '$mux' else (g('A') & g('B')) if typ == '$and' else (g('IN1') & g('IN2')) if typ == 'AND2X2' else (g('IN1') | g('IN2')) if typ == 'OR2X1' else (g('IN1') ^ g('IN2')) if typ == 'XOR2X1' else (1 ^ g('IN')) if typ == 'INVX0' else g('B') if g('S0') else g('A')
            except KeyError: continue
            vals[ob] = v; pending.remove(c); progress = True
        if not progress: raise ValueError('cycle or undefined inputs')
    return vals


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(WORK / 'view_manifest_cec.csv').set_index('view_name')
    plan = dict(created=datetime.now().astimezone().isoformat(), cases=['injalpha','injepsilon'], recipes=['ys_id','ys_abc'],
        semantics='shared named physical Q state, normal-mode PI constraint only, no reset/protocol reachability',
        budget=192, max_wall_s=1800, training=False, privileged_mechanism_cases_only=True)
    (OUT / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    sources, replays, consistency = [], [], []
    for inst in plan['cases']:
        prefix = 'TrojanA' if inst == 'injalpha' else 'TrojanE'
        emitted = []
        for recipe in plan['recipes']:
            view = f'rs232t1000__{inst}_d1_s42__{recipe}'
            source, folder, m = setup(view)
            assert manifest.loc[view, 'cec_status'] == 'PASS'
            code, spec = emit(m, 'design_'+recipe, prefix)
            emitted.append((view, code, spec, m))
            sources.append(dict(view=view, source=str(source.relative_to(ROOT)), source_sha=sha(source), raw_sha=sha(folder/'raw.json'),
                historical_cec='PASS_not_fresh_source_bound', named_registers=len(spec['state_offsets']), source_instance=inst))
            wrapper = f'''module check(input [{spec['width']-1}:0] env, input intervention, input value,
output control, output a, output b, output target, output endpoint, output diff, output legal, output equal_inputs, output alive);
wire [4:0] p0,p1; wire [{len(spec['observations'])-1}:0] o0,o1;
design_{recipe} left(env,1'b0,1'b0,p0,o0);
design_{recipe} right(env,intervention,value,p1,o1);
assign control=p0[0]; assign a=p0[1]; assign b=p0[2]; assign target=p0[3]; assign endpoint=p0[4];
assign diff=p0[4]^p1[4]; assign equal_inputs=(a==b); assign alive=1'b1;
assign legal=env[{spec['input_offsets']['sys_rst_l'][0]}] & ~env[{spec['input_offsets']['test_mode'][0]}] & ~env[{spec['input_offsets']['test_se'][0]}];
endmodule
'''
            queries = []
            for pat in map(''.join, itertools.product('01', repeat=3)):
                for val in (0,1):
                    queries.append(dict(view=view, kind='local_truth', pattern=pat, prove=val,
                        args=f'-set legal 1 -set intervention 0 -set control {pat[0]} -set a {pat[1]} -set b {pat[2]} -prove target {val}'))
            for v in (0,1):
                queries.append(dict(view=view, kind='joint_intervention', pattern=str(v), prove=0,
                    args=f'-set legal 1 -set intervention 1 -set value {1-v} -set control {v} -prove diff 0'))
                queries.append(dict(view=view, kind='equal_context_feasibility', pattern=str(v), prove=0,
                    args=f'-set legal 1 -set intervention 0 -set control {v} -set equal_inputs 1 -prove alive 0'))
                queries.append(dict(view=view, kind='equal_context_blocking', pattern=str(v), prove=0,
                    args=f'-set legal 1 -set intervention 1 -set value {1-v} -set control {v} -set equal_inputs 1 -prove diff 0'))
            results = run_queries(folder, code+'\n'+wrapper, queries)
            for row in results:
                if row['kind'] != 'joint_intervention' or row['status'] != 'refuted': continue
                w=json.loads((ROOT/row['witness']).read_text()); sigs={s['name']:s for s in w['signal']}
                env=sigs['env']['data'][0]
                natural=evaluate(m,env); counter=evaluate(m,env,(spec['control_bit'],1-int(row['pattern'])))
                c,t,ep=spec['probes'][0],spec['probes'][3],spec['probes'][4]
                ok=natural[c]==int(row['pattern']) and natural[ep]!=counter[ep]
                assert ok
                replays.append(dict(view=view, query_id=row['query_id'], environment=env, natural_control=natural[c],
                    natural_target=natural[t], counter_target=counter[t], natural_endpoint=natural[ep], counter_endpoint=counter[ep], replay_pass=int(ok)))
        va,ca,sa,ma=emitted[0];vb,cb,sb,mb=emitted[1]
        assert sa['input_offsets']==sb['input_offsets'] and sa['state_offsets']==sb['state_offsets'] and sa['observations']==sb['observations']
        folder=OUT/(inst+'_cross_impl');folder.mkdir(exist_ok=True)
        obswidth=len(sa['observations'])
        wrapper=f'''module check(input [{sa['width']-1}:0] env, output [4:0] delta, output po_d_diff);
wire [4:0] a,b; wire [{obswidth-1}:0] oa,ob;
design_ys_id left(env,1'b0,1'b0,a,oa); design_ys_abc right(env,1'b0,1'b0,b,ob);
assign delta=a^b; assign po_d_diff=|(oa^ob); endmodule
'''
        qs=[dict(view=inst,kind='cross_signal_equivalence',pattern=str(i),prove=0,args=f'-prove delta[{i}] 0') for i in range(5)]
        qs.append(dict(view=inst,kind='fresh_po_and_physical_d_equivalence',pattern='all',prove=0,args='-prove po_d_diff 0'))
        rr=run_queries(folder,ca+'\n'+cb+'\n'+wrapper,qs)
        consistency += [dict(instance=inst,signal=['control','A','B','target','rec_readyH','all_PO_and_D'][i],
                            status=row['status'],state_pairing='same named physical Q, same PI bit', source_a_sha=sha(WORK/'trans'/(va+'.v')),
                            source_b_sha=sha(WORK/'trans'/(vb+'.v'))) for i,row in enumerate(rr)]
    pd.DataFrame(ROWS).to_csv(OUT/'queries.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(sources).to_csv(OUT/'sources.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(replays).to_csv(OUT/'independent_replay.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(consistency).to_csv(OUT/'signal_correspondence.csv',index=False,encoding='utf-8-sig')
    summary=dict(solver_subqueries=len(ROWS), status=pd.Series([x['status'] for x in ROWS]).value_counts().to_dict(),
                 independent_joint_replays=len(replays), fresh_cross_checks=consistency, training_runs=0, wall_s=round(time.monotonic()-START,2))
    (OUT/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__': main()
