"""Independently replay SAT witnesses with a small combinational evaluator."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/audit_20261025'


def simulate(mod,env,inject):
    values={'0':0,'1':1,'x':None,'z':None}
    off=0
    for name,port in mod['ports'].items():
        if port['direction']!='input':
            continue
        for j,b in enumerate(port['bits']):
            v=inject if name=='audit_inject' else (env>>(off+j))&1
            if b in values:
                assert values[b]==v, 'contradictory aliased inputs'
            values[b]=v
        if name!='audit_inject':
            off+=len(port['bits'])
    cells=list(mod['cells'].values())
    driver={b:i for i,c in enumerate(cells) for p,d in c['port_directions'].items()
            if d=='output' for b in c['connections'][p]}
    need=set()
    stack=list(mod['ports']['audit_obs']['bits'])
    seen=set()
    while stack:
        bit=stack.pop()
        if bit in values or bit in seen:
            continue
        seen.add(bit)
        assert bit in driver, f'undriven observation cone bit {bit}'
        i=driver[bit]
        if i not in need:
            need.add(i)
            c=cells[i]
            stack.extend(b for p,d in c['port_directions'].items() if d=='input' for b in c['connections'][p])
    todo=[cells[i] for i in sorted(need)]
    def logic_and(a,b):
        return 0 if a==0 or b==0 else (1 if a==b==1 else None)
    def logic_or(a,b):
        return 1 if a==1 or b==1 else (0 if a==b==0 else None)
    while todo:
        rest=[]
        done=0
        for cell in todo:
            con=cell['connections']
            inputs=[p for p,d in cell['port_directions'].items() if d=='input']
            if any(b not in values for p in inputs for b in con[p]):
                rest.append(cell)
                continue
            width=len(con['Y'])
            def vals(port,w):
                bits=[values[v] for v in con.get(port,[])]
                # Operators in these mapped gate models have unsigned inputs.
                signed=int(cell.get('parameters',{}).get(port+'_SIGNED','0'),2)
                assert not signed, 'signed replay operator needs explicit extension'
                return (bits+[0]*w)[:w]
            a=vals('A',width)
            b=vals('B',width)
            typ=cell['type']
            if typ in ('$and','$_AND_'):
                y=[logic_and(u,v) for u,v in zip(a,b)]
            elif typ in ('$or','$_OR_'):
                y=[logic_or(u,v) for u,v in zip(a,b)]
            elif typ in ('$xor','$_XOR_'):
                y=[None if u is None or v is None else u^v for u,v in zip(a,b)]
            elif typ in ('$not','$_NOT_'):
                y=[None if u is None else 1-u for u in a]
            elif typ in ('$mux','$_MUX_'):
                s=values[con['S'][0]]
                y=(a if s==0 else b) if s is not None else [u if u==v else None for u,v in zip(a,b)]
            elif typ in ('$ne','$eq'):
                w=max(len(con['A']),len(con['B']))
                pairs=list(zip(vals('A',w),vals('B',w)))
                ne=1 if any(u is not None and v is not None and u!=v for u,v in pairs) else (None if any(u is None or v is None for u,v in pairs) else 0)
                y=[ne if typ=='$ne' or ne is None else 1-ne]
            elif typ in ('$reduce_or','$reduce_bool','$logic_not'):
                bits=[values[v] for v in con['A']]
                out=1 if 1 in bits else (None if None in bits else 0)
                y=[out if typ!='$logic_not' or out is None else 1-out]
            else:
                raise AssertionError(f'unsupported replay operator {typ}')
            for j,bit in enumerate(con['Y']):
                v=y[j]
                if bit in values:
                    assert values[bit]==v, 'multiple drivers'
                values[bit]=v
            done+=1
        assert done, f'unresolved combinational inputs: {len(rest)}'
        todo=rest
    return [values[b] for b in mod['ports']['audit_obs']['bits']]


def main():
    d=pd.read_csv(OUT/'two_case_observability.csv',encoding='utf-8-sig')
    rows=[]
    for _,r in d[d.status=='sensitizable_sat'].iterrows():
        witness=ROOT/r.witness
        waves=json.loads(witness.read_text())['signal']
        env=int(next(s for s in waves if s['name']=='env')['data'][0],2)
        model=witness.with_name(witness.name.replace('.witness.json','.model.json'))
        mod=json.loads(model.read_text())['modules']['audit_design']
        a,b=simulate(mod,env,0),simulate(mod,env,1)
        diff=[i for i,(x,y) in enumerate(zip(a,b)) if x is not None and y is not None and x!=y]
        assert diff, r.target
        rows.append(dict(view=r.view,target=r.target,passed=True,changed_observation_indices=';'.join(map(str,diff)),
                         changed_observations=len(diff),witness=r.witness))
    pd.DataFrame(rows).to_csv(OUT/'witness_replay.csv',index=False,encoding='utf-8-sig')
    print(f'PASS: {len(rows)} SAT witnesses independently replayed')


if __name__=='__main__':
    main()
