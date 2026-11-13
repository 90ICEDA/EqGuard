"""Large-host validation, independent witness replay and selected re-solves."""
import json
from pathlib import Path
import pandas as pd
import case_chain as C


def replay_rows(queries):
    out = []
    for r in queries.to_dict('records'):
        if r['kind'] not in ('joint_intervention', 'equal_context_blocking') or r['status'] != 'refuted':
            continue
        folder = C.ROOT / r['folder']
        m = next(iter(json.loads((folder / 'raw.json').read_text())['modules'].values()))
        large = r['view'].startswith('s38417')
        prefix = 'TrojanA' if ('injalpha' in r['view']) else 'TrojanE'
        names = ['TrojanAHJ.IN3','TrojanAHJ.IN1','TrojanAHJ.IN2','TrojanAHJ.QN','g5629'] if large else None
        _, spec = C.emit(m, 'unused', prefix, names)
        w = json.loads((C.ROOT / r['witness']).read_text())
        env = next(s['data'][0] for s in w['signal'] if s['name'] == 'env')
        natural = C.evaluate(m, env)
        counter = C.evaluate(m, env, (spec['control_bit'], 1-int(r['pattern'])))
        ctrl, a, b, target, endpoint = spec['probes']
        assert natural[ctrl] == int(r['pattern']) and natural[endpoint] != counter[endpoint]
        if r['kind'] == 'equal_context_blocking':
            assert natural[a] == natural[b]
        out.append(dict(view=r['view'], query_id=r['query_id'], kind=r['kind'],
            natural_control=natural[ctrl], natural_A=natural[a], natural_B=natural[b],
            counter_A=counter[a], counter_B=counter[b], natural_endpoint=natural[endpoint],
            counter_endpoint=counter[endpoint], environment=env, independent_replay=1))
    return out


def main():
    view='s38417t100__injalpha_d1_s42__ys_id'
    source, folder, m = C.setup(view)
    code, spec = C.emit(m, 'large', 'TrojanA', ['TrojanAHJ.IN3','TrojanAHJ.IN1','TrojanAHJ.IN2','TrojanAHJ.QN','g5629'])
    width = len(spec['observations'])
    mode = ' & '.join('~env['+str(spec['input_offsets'][name][0])+']' for name in ['test_se','test_mode'] if name in spec['input_offsets']) or "1'b1"
    wrapper=f'''module check(input [{spec['width']-1}:0] env,input intervention,input value,
output control,output a,output b,output target,output diff,output legal,output equal_inputs,output alive);
wire [4:0] p0,p1;wire [{width-1}:0] o0,o1;
large l(env,1'b0,1'b0,p0,o0);large r(env,intervention,value,p1,o1);
assign control=p0[0];assign a=p0[1];assign b=p0[2];assign target=p0[3];
assign diff=p0[4]^p1[4];assign legal={mode};assign equal_inputs=(a==b);assign alive=1'b1;
endmodule
'''
    qs=[]
    import itertools
    for pat in map(''.join,itertools.product('01',repeat=3)):
        for val in (0,1):
            qs.append(dict(view=view,kind='local_truth',pattern=pat,prove=val,
                args=f'-set legal 1 -set intervention 0 -set control {pat[0]} -set a {pat[1]} -set b {pat[2]} -prove target {val}'))
    for v in (0,1):
        qs.append(dict(view=view,kind='joint_intervention',pattern=str(v),prove=0,
            args=f'-set legal 1 -set intervention 1 -set value {1-v} -set control {v} -prove diff 0'))
        # NAND3 is blocked when A=0; assess feasibility separately.
        qs.append(dict(view=view,kind='blocking_context_feasibility',pattern=str(v),prove=0,
            args=f'-set legal 1 -set intervention 0 -set control {v} -set a 0 -prove alive 0'))
        qs.append(dict(view=view,kind='blocking_context',pattern=str(v),prove=0,
            args=f'-set legal 1 -set intervention 1 -set value {1-v} -set control {v} -set a 0 -prove diff 0'))
    C.run_queries(folder,code+'\n'+wrapper,qs)
    extra=pd.DataFrame(C.ROWS)
    extra.to_csv(C.OUT/'large_host_queries.csv',index=False,encoding='utf-8-sig')
    original=pd.read_csv(C.OUT/'queries.csv',dtype={'pattern':str})
    allq=pd.concat([original,extra],ignore_index=True)
    replays=replay_rows(allq)
    pd.DataFrame(replays).to_csv(C.OUT/'all_independent_replays.csv',index=False,encoding='utf-8-sig')
    # Independent new Yosys processes for joint queries and control/target equivalence.
    picks=allq[(allq.kind=='joint_intervention') | ((allq.kind=='cross_signal_equivalence') & allq.pattern.isin(['0','3']))]
    start=len(C.ROWS)
    for i,r in enumerate(picks.to_dict('records')):
        dest=C.OUT/'review'/str(i);dest.mkdir(parents=True,exist_ok=True)
        model=(C.ROOT/r['folder']/'model.v').read_text()
        C.run_queries(dest,model,[dict(view=r['view'],kind='review',pattern=r['pattern'],prove=int(r['prove']),args=r['args'],original_status=r['status'])])
    reviews=pd.DataFrame(C.ROWS[start:]);assert (reviews.status==reviews.original_status).all()
    reviews.to_csv(C.OUT/'review_queries.csv',index=False,encoding='utf-8-sig')
    total=len(original)+len(extra)+len(reviews)
    assert total<=192
    summary=dict(main_subqueries=len(original),large_subqueries=len(extra),review_subqueries=len(reviews),
        total_subqueries=total,review_agree=int((reviews.status==reviews.original_status).sum()),
        independently_replayed=len(replays),large_source_sha=C.sha(source),large_registers=len(spec['state_offsets']),
        large_status=extra.groupby(['kind','status']).size().to_string(),training_runs=0)
    (C.OUT/'complete_manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
