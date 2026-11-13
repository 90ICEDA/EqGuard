"""Bounded synthetic SAT check with an independent exhaustive environment oracle.

No project netlist, labels, training feature or historical evidence is changed.
One Yosys preparation/batch, 9 cases x 8 patterns x 2 proves = 144 subqueries.
"""
import hashlib
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'phase2/ys'))
import sat_functional_relations as P0
from sat_boundary_semantics import classify, summarize

OUT = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_audit_round17'


def main():
    if (OUT / 'solver.log').exists():
        raise RuntimeError('Do not overwrite executed evidence')
    # The Python oracle and Verilog expressions are independently specified.
    cases = [
        ('mux', '{env[2],env[1],env[0]}', 'env[0]?env[2]:env[1]',
         lambda e: ((e[0], e[1], e[2]), e[2] if e[0] else e[1])),
        ('and3', '{env[2],env[1],env[0]}', 'env[0]&env[1]&env[2]',
         lambda e: ((e[0], e[1], e[2]), e[0] & e[1] & e[2])),
        ('or3', '{env[2],env[1],env[0]}', 'env[0]|env[1]|env[2]',
         lambda e: ((e[0], e[1], e[2]), e[0] | e[1] | e[2])),
        ('xor3', '{env[2],env[1],env[0]}', 'env[0]^env[1]^env[2]',
         lambda e: ((e[0], e[1], e[2]), e[0] ^ e[1] ^ e[2])),
        ('nand3', '{env[2],env[1],env[0]}', '~(env[0]&env[1]&env[2])',
         lambda e: ((e[0], e[1], e[2]), 1 - (e[0] & e[1] & e[2]))),
        ('first_input_only', '{env[2],env[1],env[0]}', 'env[0]',
         lambda e: ((e[0], e[1], e[2]), e[0])),
        ('same_bit_alias', '{env[2],env[0],env[0]}', 'env[2]',
         lambda e: ((e[0], e[0], e[2]), e[2])),
        ('unmeasured_input', '{env[2],env[1],env[0]}', 'env[3]',
         lambda e: ((e[0], e[1], e[2]), e[3])),
        ('Q_QN_complements', '{env[2],~env[0],env[0]}', 'env[2]',
         lambda e: ((e[0], 1-e[0], e[2]), e[2])),
    ]
    model = ['module check(input [3:0] env,input [2:0] pattern,',
             'output [8:0] premise,output [8:0] target);']
    for i, (_, cut, target, _) in enumerate(cases):
        model += [f'assign premise[{i}]=({cut}==pattern);',
                  f'assign target[{i}]={target};']
    model.append('endmodule')
    path = OUT / 'synthetic.v'
    path.write_text('\n'.join(model) + '\n', encoding='utf-8')
    commands = [f'read_verilog "{P0.wsl(path)}"', 'hierarchy -top check',
                'proc', 'flatten', 'opt_clean']
    bindings = []
    for i, (name, _, _, _) in enumerate(cases):
        for p in map(''.join, itertools.product('01', repeat=3)):
            for prove in (1, 0):
                args = (f"-set pattern 3'b{p[::-1]} -set premise[{i}] 1 "
                        f'-prove target[{i}] {prove} -timeout 5')
                qid = len(bindings)
                commands += [f'log SATQ{qid:06d}', f'sat {args}']
                bindings.append(dict(query_id=qid, case=name, pattern=p,
                                     prove=prove, args=args))
    script = '\n'.join(commands) + '\n'
    log = P0.run_yosys(script, OUT / 'solver.log', timeout=180)
    statuses = P0.parse_results(log)
    assert len(statuses) == len(bindings) == 144
    for row, status in zip(bindings, statuses):
        row['status'] = status
    results = []
    for name, _, _, oracle in cases:
        table = {}
        for p in map(''.join, itertools.product('01', repeat=3)):
            rows = {q['prove']: q['status'] for q in bindings
                    if q['case'] == name and q['pattern'] == p}
            actual = classify(rows[1], rows[0])
            outputs = {value for env in itertools.product((0, 1), repeat=4)
                       for cut, value in [oracle(env)] if ''.join(map(str, cut)) == p}
            expected = (('infeasible', 'not_applicable') if not outputs else
                        ('feasible', str(next(iter(outputs)))) if len(outputs) == 1
                        else ('feasible', 'undecided'))
            assert actual == expected, (name, p, actual, expected)
            table[p] = actual
        features, per_input = summarize(table, 3)
        results.append(dict(case=name, table=table, features=features, inputs=per_input))
    evidence = dict(queries=bindings, actual_sat_queries=len(bindings),
                    patterns_checked=72, cases=results, all_oracles_agree=True,
                    model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    script_sha256=hashlib.sha256(script.encode()).hexdigest(),
                    log_sha256=hashlib.sha256((OUT/'solver.log').read_bytes()).hexdigest(),
                    scope='synthetic combinational fixtures; no training or project search')
    (OUT / 'solver_validation.json').write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('queries', 'cases')}))


if __name__ == '__main__':
    main()
