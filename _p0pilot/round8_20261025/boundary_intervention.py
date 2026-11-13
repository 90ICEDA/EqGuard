"""Functional boundary intervention: freeze natural A/B, change only select.

Different from a global physical-wire fault, which may alter A/B via aliases.
Target equals rec_readyH in these four cases; this is explicitly checked.
"""
import json
import pandas as pd
import case_chain as C


def main():
    sources=pd.read_csv(C.OUT/'sources.csv')
    replay=[]
    for r in sources.itertuples():
        original=C.OUT/r.view
        raw=next(iter(json.loads((original/'raw.json').read_text())['modules'].values()))
        prefix='TrojanA' if 'injalpha' in r.view else 'TrojanE'
        _,spec=C.emit(raw,'unused',prefix)
        assert spec['probes'][3]==spec['probes'][4], 'downstream model required when target is not PO alias'
        text=(original/'model.v').read_text().replace('output alive);','output alive, output boundary_diff);')
        before,after=text.rsplit('endmodule',1)
        text=before+'assign boundary_diff=p0[4] ^ (value ? p0[2] : p0[1]);\nendmodule'+after
        folder=C.OUT/'functional_boundary'/r.view;folder.mkdir(parents=True,exist_ok=True)
        qs=[]
        for v in (0,1):
            for equal in (0,1):
                qs.append(dict(view=r.view,kind='fixed_boundary_change' if equal==0 else 'fixed_boundary_blocking',pattern=str(v),prove=0,
                    args=f'-set legal 1 -set intervention 0 -set value {1-v} -set control {v} -set equal_inputs {equal} -prove boundary_diff 0'))
        results=C.run_queries(folder,text,qs)
        for q in results:
            if q['kind']=='fixed_boundary_blocking':
                assert q['status']=='proved'
                continue
            assert q['status']=='refuted'
            w=json.loads((C.ROOT/q['witness']).read_text());env=next(s['data'][0] for s in w['signal'] if s['name']=='env')
            vals=C.evaluate(raw,env);s,a,b,t,ep=spec['probes'];counter=vals[b] if 1-int(q['pattern']) else vals[a]
            assert vals[s]==int(q['pattern']) and vals[a]!=vals[b] and vals[ep]!=counter
            replay.append(dict(view=r.view,natural_control=vals[s],A=vals[a],B=vals[b],natural_endpoint=vals[ep],
                boundary_counter_endpoint=counter,independent_replay=1,scope='fixed_A_B_functional_boundary_not_global_wire'))
    pd.DataFrame(C.ROWS).to_csv(C.OUT/'boundary_queries.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(replay).to_csv(C.OUT/'boundary_replays.csv',index=False,encoding='utf-8-sig')
    (C.OUT/'boundary_manifest.json').write_text(json.dumps(dict(subqueries=len(C.ROWS),positive_replay=len(replay),
        status=pd.Series([r['status'] for r in C.ROWS]).value_counts().to_dict(),training_runs=0),indent=2),encoding='utf-8')
    print('16 boundary queries; 8 positive replay, 8 proved blocked.',flush=True)


if __name__=='__main__':main()
