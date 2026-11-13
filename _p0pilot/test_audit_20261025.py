"""Focused semantic and byte-equivalence checks; no GPU training required."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'_p0pilot'))
sys.path.insert(0,str(ROOT/'phase2/ys'))
import audit_sat_20261025 as audit
from structural_reach_index import ReachIndex
from audit_reach_bench_20261025 import selfcheck
from replay_observability_20261025 import simulate


def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path))
    spec=importlib.util.spec_from_loader(name,loader)
    mod=importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def main():
    audit.checks()
    selfcheck()
    # An unknown, unselected mux branch must not poison a known witness;
    # selecting that branch must NOT fabricate a defined observation change.
    mod=dict(ports={'env':dict(direction='input',bits=[1]),
                    'audit_inject':dict(direction='input',bits=[2]),
                    'audit_obs':dict(direction='output',bits=[3])},
             cells={'mux':dict(type='$mux',port_directions={'A':'input','B':'input','S':'input','Y':'output'},
                               connections={'A':[2],'B':['x'],'S':[1],'Y':[3]})})
    assert simulate(mod,0,0)==[0] and simulate(mod,0,1)==[1]
    assert simulate(mod,1,0)==[None] and simulate(mod,1,1)==[None]
    # BFS truncation must be visible and must not poison full cached traversal.
    r=ReachIndex(dict(netnames={'a':{'bits':[1]}},ports={'o':dict(direction='output',bits=[3])},
                     cells={'g':dict(type='AND',port_directions={'A':'input','Y':'output'},connections={'A':[1],'Y':[2]}),
                            'h':dict(type='INV',port_directions={'A':'input','Y':'output'},connections={'A':[2],'Y':[3]})}))
    assert r.reach('a',max_nodes=1)['truncated']
    assert r.reach('a')['reach_po']==1 and not r.reach('a')['truncated']
    old=load('legacy_builder',ROOT/'_p0pilot/build_p0clean4.py.bak_20261025_audit')
    new=load('fast_builder',ROOT/'_p0pilot/build_p0clean4.py')
    rng=np.random.default_rng(71)
    with tempfile.TemporaryDirectory(prefix='sat_audit_test_') as temp:
        base=Path(temp)
        fid=['v2','v0','v1','v2','v0','v1']*32
        core=rng.random((len(fid),10),dtype=np.float32)
        core[:,7:]=(core[:,7:]>.5).astype(np.float32)
        source=base/'core.npy'
        np.save(source,core)
        table=[]
        for i in range(30):
            table.append(dict(design=f'v{i%3}',target=f'n{i}',cut_nets=f'n{(i+1)%30};n{(i+2)%30}',
                              cell=f'n{(i+3)%30}',case_class=old.CLASSES[i%4],status_v3=old.STATUS[i%3]))
        csv=base/'relations.csv'
        pd.DataFrame(table).to_csv(csv,index=False)
        outputs=[]
        for mod,dirname in [(old,'old'),(new,'new')]:
            path=base/dirname
            path.mkdir()
            (path/'data/for_train').mkdir(parents=True)
            (path/'data/for_train/metadata_trans.json').write_text(json.dumps(dict(file_ids=fid)))
            (path/'node_names_trans.txt').write_text('\n'.join(f'n{i%30}' for i in range(len(fid)))+'\n')
            mod.PT=path
            mod.WORK=path
            mod.SRC3=source
            mod.V3=csv
            sys.argv=['builder']
            with contextlib.redirect_stdout(io.StringIO()):
                assert mod.main()==0
            outputs.append(path)
        count=0
        for before in outputs[0].glob('*.npy'):
            after=outputs[1]/before.name
            assert before.read_bytes()==after.read_bytes(), before.name
            count+=1
        assert count==19
        # The shortcut exporter must agree byte-for-byte too.
        new.PT=outputs[1]
        sys.argv=['builder','--only','core_reach,covered_only','--suffix','fasttest']
        with contextlib.redirect_stdout(io.StringIO()):
            assert new.main()==0
        for k in ['core_reach','covered_only']:
            a=np.load(outputs[1]/f'satrel_node_feats_sat_p0clean4_fasttest_{k}.npy')
            b=np.load(outputs[0]/f'satrel_node_feats_sat_p0clean4_{k}.npy')
            assert a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
    print('PASS: query alignment with middle timeout; exact bit neighbours; aliases; D-only endpoints; truncation; 19 variant byte-equivalence; fast exporter byte-equivalence')


if __name__=='__main__':
    main()
