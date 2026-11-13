"""Verify v2 output and compare source wiring to independent Yosys JSON.
Uses existing raw snapshots first; missing references require parse-only Yosys,
never SAT, optimization, training or a model forward.
"""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import sys,json,hashlib,collections,subprocess,re,datetime
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;PRE=H.parent/'round29_20261029';sys.path.insert(0,str(ROOT/'phase2/ys'));sys.path.insert(0,str(PRE))
from feature_encoding_v2 import load_library,features,SYNTHETIC
from readonly_graph_arrays import arrays
O=ROOT/'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2';V=H/'validation';V.mkdir(exist_ok=True,parents=True)
def sha(p):
    d=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):d.update(b)
    return d.hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def wsl(p):s=str(p.resolve()).replace('\\','/');return '/mnt/'+s[0].lower()+s[2:]
def main():
    c=json.loads((O/'COMPLETE.json').read_text());contract=json.loads((O/'contract.json').read_text());f=ROOT/'generate_trans/folds/hosts_bt31';old,_=arrays(f/'data/processed/trans_graph.pt');x=np.load(O/'features39_v2.npy',mmap_mode='r');vx=np.load(O/'virtual_features39_v2.npy',mmap_mode='r');e=np.load(O/'edge_index_directed_v2.npy',mmap_mode='r');roles=np.load(O/'edge_roles_v2.npy',mmap_mode='r');N=len(x)
    report=dict(time=datetime.datetime.now().astimezone().isoformat(),original_nodes=N,virtual_nodes=len(vx),views=len(c['rows']),edges=e.shape[1],checks={},independent_yosys=[],new_sat_queries=0,training_runs=0,model_forwards=0)
    assert x.shape==(3220146,39) and e.shape==(2,c['edges']) and vx.shape==(c['virtual_nodes'],39)
    for p,h in contract['inputs'].items():assert sha(ROOT/p)==h,p
    for p,h in c['outputs'].items():assert sha(O/p)==h,p
    for a in [x,vx]:
        for b in range(0,len(a),32768):
            z=a[b:b+32768];assert np.isfinite(z).all() and np.isin(z[:,:25],[0,1]).all() and np.all(z[:,:25].sum(1)==1)
    view_of=np.full(N+len(vx),-2,np.int16);cursor=0;rowlookup={r['view']:r for r in c['rows']}
    with (f/'data/processed/node_names_trans.txt').open(encoding='utf-8') as stream:
        for num,r in enumerate(c['rows']):
            lo,hi=r['start'],r['stop'];nv=r['virtual_nodes'];vstart=r['virtual_global_start'];assert lo==cursor and hi-lo==r['nodes'];cursor=hi
            names=[next(stream).strip().lstrip('\\') for _ in range(hi-lo)];assert hashlib.sha256('\n'.join(names).encode()).hexdigest()==r['ordered_cell_names_sha'];assert sha(ROOT/r['source'])==r['source_sha'];folder=O/'views'/r['view'];assert sha(folder/'features_and_edges.npz')==r['sha256'];assert sha(folder/'virtual_nodes.json')==r['virtual_metadata_sha']
            with np.load(folder/'features_and_edges.npz') as z:
                assert np.array_equal(z['x'][:hi-lo],x[lo:hi]);assert np.array_equal(z['x'][hi-lo:],vx[vstart-N:vstart-N+nv])
            assert np.array_equal(x[lo:hi,:26],old['x'][lo:hi,:26]);view_of[lo:hi]=num;view_of[vstart:vstart+nv]=num
        assert stream.readline()==''
    assert np.all(view_of>=0)
    for b in range(0,e.shape[1],65536):
        ee=e[:,b:b+65536];assert ee.min()>=0 and ee.max()<len(view_of);assert np.array_equal(view_of[ee[0]],view_of[ee[1]]);assert np.all(roles[b:b+65536]>0)
    graph=f/'data/processed/trans_graph.pt';assert graph.stat().st_size==contract['legacy_graph']['size'] and graph.stat().st_mtime_ns==contract['legacy_graph']['mtime_ns'];report['checks'].update(hash_bound=True,coordinate_rows=True,source_cells=True,legacy_graph_stat_unchanged=True,all_onehot_and_finite=True,no_cross_view_edges=True)
    print('Whole-fold hashes and coordinates PASS',flush=True)
    # Fixed label-blind selection: first injection and first control for each host/recipe.
    selected=[]
    for host in ['rs232t1000','s15850t100','s35932t200','s38417t100','s38584t100']:
        for recipe in ['ys_abc','ys_aig','ys_nand','ys_id']:
            for token in ['__injalpha_','__ctldup_']:
                matches=sorted(v for v in rowlookup if v.startswith(host+'__') and token in v and v.endswith('__'+recipe))
                if matches:selected.append(matches[0])
    idsneeded=set()
    for v in selected:
        r=rowlookup[v];idsneeded.update(range(r['start'],r['stop']))
    namesby={}
    with (f/'data/processed/node_names_trans.txt').open(encoding='utf-8') as stream:
        for i,name in enumerate(stream):
            if i in idsneeded:namesby[i]=name.strip().lstrip('\\')
    lib=load_library(f/'verilog_lib.v');mapping={r['full_gate_name']:r['simplified_gate_type'] for r in json.loads((f/'gate_full_to_simplified_mapping.json').read_text())};order=json.loads((f/'gatelookup_recommended.json').read_text())['simplified_gate_type_order']
    panels=[ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'/s for s in ['sat_k4_alltrain_round27','sat_k4_rs232_round23','sat_s15850_round22']]
    for v in selected:
        row=rowlookup[v];lo,hi=row['start'],row['stop'];source=ROOT/row['source'];ref=None;origin='existing_bound_snapshot'
        for panel in panels:
            folder=panel/'views'/v
            if (folder/'snapshots.json').exists():
                for r in json.loads((folder/'snapshots.json').read_text()):
                    raw=ROOT/r['folder']/'raw.json'
                    if raw.exists() and r['source_sha']==row['source_sha'] and sha(raw)==r['raw_sha']:ref=raw;break
            if ref:break
        if ref is None:
            # Parsing only: no sat command and no truth-table search.
            origin='new_readonly_verilog_parse';folder=V/'yosys_parse_only'/v;folder.mkdir(parents=True,exist_ok=True);ref=folder/'raw.json';script=folder/'parse.ys';top=re.search(r'\bmodule\s+(\w+)',source.read_text(encoding='utf-8'))[1]
            code=f'read_verilog "{wsl(source)}"\nhierarchy -top {top}\nproc -noopt\nwrite_json "{wsl(ref)}"\n';assert not re.search(r'^\s*sat\b',code,re.M)
            if not ref.exists():
                script.write_text(code,encoding='utf-8')
                with (folder/'parse.log').open('xb') as log:rc=subprocess.call(['wsl','-e','yosys','-Q','-s',wsl(script)],stdout=log,stderr=subprocess.STDOUT,timeout=90)
                assert rc==0 and ref.exists()
                write(folder/'binding.json',dict(source_sha=row['source_sha'],raw_sha=sha(ref),SAT_commands=0))
            else:
                binding=json.loads((folder/'binding.json').read_text());assert binding['source_sha']==row['source_sha'] and binding['raw_sha']==sha(ref)
        raw=json.loads(ref.read_text());m=next(iter(raw['modules'].values()));native={k.lstrip('\\'):cell for k,cell in m['cells'].items()};ordered=[namesby[i] for i in range(lo,hi)];assert all(n in native for n in ordered)
        meta=json.loads((O/'views'/v/'virtual_nodes.json').read_text());wire={k.lstrip('\\'):bits['bits'] for k,bits in m['netnames'].items()}
        def bit(name):
            if name.startswith('#'):return name[1:]
            if name not in wire:raise ValueError(f'No independently named scalar net {name}')
            if len(wire[name])!=1:raise ValueError('Scalar virtual wire required')
            return wire[name][0]
        virtual_matches=[]
        for rec in meta:
            outbit=bit(rec['output']);op={'V2_ASSIGN_AND':'$and','V2_ASSIGN_OR':'$or','V2_ASSIGN_XOR':'$xor','V2_ASSIGN_NOT':'$not','V2_ASSIGN_MUX':'$mux'}[rec['type']]
            matches=[(name,cell) for name,cell in native.items() if cell['type']==op and cell['connections'].get('Y')==[outbit]]
            assert len(matches)==1,(v,rec,matches)
            name,cell=matches[0];inputs=[bit(s) for s in rec['inputs']];pins=['S','B','A'] if op=='$mux' else ['A'] if op=='$not' else ['A','B'];assert [cell['connections'][pin][0] for pin in pins]==inputs,(v,rec,cell)
            virtual_matches.append((rec,name,cell))
        raw_nodes=[(name,native[name],native[name]['type']) for name in ordered]+[(rec['name'],cell,rec['type']) for rec,name,cell in virtual_matches]
        pi={b for p in m['ports'].values() if p['direction'] in ['input','inout'] for b in p['bits']};po={b for p in m['ports'].values() if p['direction'] in ['output','inout'] for b in p['bits']};drv=collections.defaultdict(list);cons=collections.defaultdict(list);PI=[];PO=[];ports=[];types=[]
        for i,(name,cell,typ) in enumerate(raw_nodes):
            types.append(typ);connections=cell['connections'];pins=list(SYNTHETIC[typ][0]) if typ in SYNTHETIC else lib[typ]['input'];ports.append(len(pins));allbits=[b for bs in connections.values() for b in bs];PI.append(any(b in pi for b in allbits));PO.append(any(b in po for b in allbits))
            outs=['Y'] if typ in SYNTHETIC else lib[typ]['output'];ins=[p for p,d in cell.get('port_directions',{}).items() if d=='input'] if typ in SYNTHETIC else lib[typ]['input']
            for p,bs in connections.items():
                for b in bs:
                    if p in outs:drv[b].append(i)
                    if p in ins:cons[b].append(i)
        pairs=set();degree=np.zeros(len(raw_nodes),np.int64)
        for b,dd in drv.items():
            for u in dd:
                for w in cons.get(b,[]):pairs.add((u,w));degree[u]+=1;degree[w]+=1
        de=np.array(sorted(pairs),np.int64).T if pairs else np.empty((2,0),np.int64)
        graph=dict(types=types,input_ports=np.array(ports),PI=np.array(PI),PO=np.array(PO),edge_index=de,incident_count=degree)
        expected=features(graph,mapping,order)
        with np.load(O/'views'/v/'features_and_edges.npz') as z:
            assert np.array_equal(de,z['edge_index']),(v,'independent edge mismatch');assert np.allclose(expected,z['x'],atol=2e-6,rtol=2e-6),(v,'independent feature mismatch')
        report['independent_yosys'].append(dict(view=v,original_nodes=hi-lo,auxiliary_nodes=len(meta),raw_origin=origin,raw_path=str(ref.relative_to(ROOT)),source_sha=row['source_sha'],raw_sha=sha(ref),edges_equal=True,all_39_columns_equal=True,expression_operands_equal=True));print('Independent Yosys PASS',v,flush=True)
    report['independent_views']=len(report['independent_yosys']);report['independent_nodes']=sum(r['original_nodes'] for r in report['independent_yosys']);report['passed']=True
    write(V/'final_validation.json',report);print('VALIDATED',report['independent_views'],report['independent_nodes'],flush=True)
if __name__=='__main__':main()
