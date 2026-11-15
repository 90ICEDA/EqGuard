"""Compare emitted pin connectivity and port bits against the generic Yosys snapshot."""
from collections import Counter
import json

from build_clean import CELLS, OUT, read, sha


def main():
    generic = read(OUT/'clean_generic.json')['modules']['picorv32']
    mapped = read(OUT/'clean_readback.json')['modules']['picorv32_clean']
    assert generic['ports'].keys() == mapped['ports'].keys()
    correspondence = {}

    def bind(a,b):
        if isinstance(a,str):
            assert a == b
        else:
            assert isinstance(b,int)
            assert correspondence.setdefault(a,b) == b

    for name,a in generic['ports'].items():
        b = mapped['ports'][name]
        assert a['direction']==b['direction'] and len(a['bits'])==len(b['bits'])
        for ai,bi in zip(a['bits'],b['bits']):
            bind(ai,bi)
    assert len(generic['cells'])==len(mapped['cells'])
    state = Counter()
    for j,(_,a) in enumerate(sorted(generic['cells'].items())):
        b = mapped['cells'][f'g{j:05d}']
        typ,pins = CELLS[a['type'][2:-1]]
        assert b['type']==typ and set(b['connections'])==set(pins.values())
        for src,dst in pins.items():
            ai, = a['connections'][src]
            bi, = b['connections'][dst]
            bind(ai,bi)
        if typ=='DFFX2':
            state.update(('D','Q','CLK'))
    assert len(correspondence)==len(set(correspondence.values()))
    assert state==dict(D=1596,Q=1596,CLK=1596)
    report = read(OUT/'CLEAN_AUDIT.json')
    assert all(sha(OUT/n)==h for n,h in report['hashes'].items())
    result = dict(bit_bijection=len(correspondence),ports=len(generic['ports']),
                  port_bits=sum(len(p['bits']) for p in generic['ports'].values()),
                  cells=len(mapped['cells']), state_pins=state,
                  readback_sha256=sha(OUT/'clean_readback.json'), emitted_sha256=sha(OUT/'picorv32_clean.v'))
    (OUT/'READBACK_AUDIT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result)


if __name__=='__main__':
    main()
