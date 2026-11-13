"""Incremental v2 features beside frozen legacy graph; never overwrites SAT.
All 389 stored views, including the explicitly unlisted legacy view, are bound
by existing global rows and exact ordered cell names, not by labels.
"""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import sys,json,hashlib,time,ctypes,collections,shutil,datetime,csv
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;FOLD=ROOT/'generate_trans/folds/hosts_bt31';P=FOLD/'data/processed';PRE=H.parent/'round29_20261029'
sys.path.insert(0,str(ROOT/'phase2/ys'));sys.path.insert(0,str(PRE));sys.path.insert(0,str(H.parent/'round27_20261027'))
from feature_encoding_v2 import parse,features,load_library,COLS,CONTRACT
from readonly_graph_arrays import arrays
from k4_runtime import memory_available_gib
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
OUT=FOLD/'data/derived_v2/bitwise_alias_20261029_v2'
def sha(p):
    z=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):z.update(b)
    return z.hexdigest()
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    for attempt in range(40):
        try:os.replace(tmp,p);return
        except PermissionError:
            if attempt==39:raise
            time.sleep(.05)
def stamp():return datetime.datetime.now().astimezone().isoformat()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'COMPLETE.json').exists():raise RuntimeError('Completed independent output retained; validate it instead of rebuilding')
    old,desc=arrays(P/'trans_graph.pt');vi=np.load(PRE/'frozen/view_index_all.npy',mmap_mode='r');manifest=json.loads((PRE/'frozen/manifest.json').read_text());names=manifest['view_names'];extra=list(manifest['unlisted_nodes']);assert len(extra)==1
    groups=[]
    for k,v in list(enumerate(names))+[(-1,extra[0])]:
        ids=np.flatnonzero(vi==k);assert len(ids)>0 and np.all(np.diff(ids)==1);groups.append((int(ids[0]),int(ids[-1])+1,v,k))
    groups.sort();assert groups[0][0]==0 and groups[-1][1]==len(vi) and all(a[1]==b[0] for a,b in zip(groups,groups[1:]));N=len(vi)
    inputs={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'phase2/ys/feature_encoding_v2.py',FOLD/'verilog_lib.v',FOLD/'gatelookup_recommended.json',FOLD/'gate_full_to_simplified_mapping.json',P/'node_names_trans.txt',PRE/'frozen/view_index_all.npy']}
    contract=dict(contract=CONTRACT,created=stamp(),shape=[N,39],columns=COLS,inputs=inputs,legacy_graph=dict(path=str((P/'trans_graph.pt').relative_to(ROOT)),size=(P/'trans_graph.pt').stat().st_size,mtime_ns=(P/'trans_graph.pt').stat().st_mtime_ns),coordinate='Row i equals existing global node i; names are read from frozen ordered node_names_trans.txt; every source cell is checked',labels_read=False,training_started=False,legacy_graph_modified=False,SAT_inputs_modified=False,fan_contract='exactly two directed steps, distinct nodes, excluding self; preserved explicitly',distance_unreachable=-1,constant_is_primary_input=False,edge_contract='Unique source-cell -> sink-cell physical connections on all pins. Per-edge bit mask: 1 data/comb input,2 clock,4 scan input,8 reset/set,16 scan-enable/enable,64 other sequential control. A pair may combine roles; data-only consumers must filter role&1.',unlisted_view=extra[0],unlisted_nodes=int((vi<0).sum()))
    cp=OUT/'contract.json'
    if cp.exists():
        prior=json.loads(cp.read_text());assert prior['inputs']==inputs and prior['legacy_graph']==contract['legacy_graph']
    else:write(cp,contract)
    densepath=OUT/'features39_v2.npy';dense=np.load(densepath,mmap_mode='r+') if densepath.exists() else np.lib.format.open_memmap(densepath,mode='w+',dtype=np.float32,shape=(N,39))
    lib=load_library(FOLD/'verilog_lib.v');mapping={r['full_gate_name']:r['simplified_gate_type'] for r in json.loads((FOLD/'gate_full_to_simplified_mapping.json').read_text())};gate_order=json.loads((FOLD/'gatelookup_recommended.json').read_text())['simplified_gate_type_order'];assert COLS[:25]==['gate_'+s for s in gate_order]
    rows=[];edgecount=0;virtualcount=0;start=time.perf_counter()
    with (P/'node_names_trans.txt').open(encoding='utf-8') as stream:
        for num,(lo,hi,view,viewid) in enumerate(groups):
            cellnames=[next(stream).strip().lstrip('\\') for _ in range(hi-lo)];nodehash=hashlib.sha256('\n'.join(cellnames).encode()).hexdigest();source=FOLD/'trans'/f'{view}.v';sourcehash=sha(source);folder=OUT/'views'/view;folder.mkdir(parents=True,exist_ok=True);done=folder/'COMPLETE.json'
            while memory_available_gib()<1.2 or shutil.disk_usage(ROOT).free/2**30<9:
                write(OUT/'state.json',dict(time=stamp(),phase='waiting_resources',view=view,completed=num,memory_gib=memory_available_gib(),disk_gib=shutil.disk_usage(ROOT).free/2**30));time.sleep(20)
            if done.exists():
                item=json.loads(done.read_text());assert item['source_sha']==sourcehash and item['ordered_cell_names_sha']==nodehash and item['sha256']==sha(folder/'features_and_edges.npz')
                with np.load(folder/'features_and_edges.npz') as z:
                    assert np.array_equal(dense[lo:hi],z['x'][:hi-lo])
                assert item['virtual_global_start']==N+virtualcount
                rows.append(item);edgecount+=item['edges'];virtualcount+=item['virtual_nodes'];continue
            g=parse(source,cellnames,lib);xx=features(g,mapping,gate_order);n=hi-lo;nv=len(g['virtual_nodes']);assert xx.shape==(n+nv,39) and np.array_equal(xx[:n,:26],old['x'][lo:hi,:26])
            dense[lo:hi]=xx[:n];dense.flush()
            cache=folder/'features_and_edges.npz'
            if cache.exists():raise RuntimeError(f'Incomplete cache retained; choose a new output version before repair: {cache}')
            with cache.open('xb') as f:np.savez_compressed(f,x=xx,edge_index=g['edge_index'],edge_roles=g['edge_roles'],global_range=np.array([lo,hi],np.int64))
            write(folder/'virtual_nodes.json',g['virtual_nodes'])
            legacy=old['x'][lo:hi];changes=(xx[:n]!=legacy).sum(0).tolist()
            olde=old['edge_index'];left,right=np.searchsorted(olde[0],[lo,hi]);pairs=set(zip(*(olde[:,left:right]-lo)));direct=set(zip(*g['edge_index']));symmetric=direct|{(b,a) for a,b in direct}
            item=dict(view=view,view_index=viewid,start=lo,stop=hi,nodes=n,virtual_nodes=nv,virtual_global_start=N+virtualcount,virtual_metadata_sha=sha(folder/'virtual_nodes.json'),edges=g['edge_index'].shape[1],source=str(source.relative_to(ROOT)),source_sha=sourcehash,ordered_cell_names_sha=nodehash,sha256=sha(cache),changed_nodes_by_column=changes,changed_any_node=int(np.any(xx[:n]!=legacy,axis=1).sum()),symmetric_edge_difference=len(pairs^symmetric),alias_statements=g['alias_statements'],alias_bits=g['alias_bits'],vector_declarations=g['vector_declarations'],new_SAT_queries=0)
            write(done,item);rows.append(item);edgecount+=item['edges'];virtualcount+=nv;write(OUT/'state.json',dict(time=stamp(),phase='building',completed=num+1,views=len(groups),nodes_done=hi,edges_done=edgecount,virtual_nodes=virtualcount,view=view,elapsed_seconds=time.perf_counter()-start));print(json.dumps(dict(view=view,completed=num+1,nodes=hi-lo,virtual=nv,changes=item['changed_any_node']),ensure_ascii=False),flush=True)
        assert stream.readline()==''
    edgepath=OUT/'edge_index_directed_v2.npy';rolepath=OUT/'edge_roles_v2.npy'
    if edgepath.exists() or rolepath.exists():raise RuntimeError('Incomplete global edge output retained; cannot overwrite')
    edges=np.lib.format.open_memmap(edgepath,mode='w+',dtype=np.int64,shape=(2,edgecount));roles=np.lib.format.open_memmap(rolepath,mode='w+',dtype=np.uint8,shape=(edgecount,));cursor=0
    virtualpath=OUT/'virtual_features39_v2.npy';virtual=np.lib.format.open_memmap(virtualpath,mode='w+',dtype=np.float32,shape=(virtualcount,39));vm=(OUT/'virtual_node_map.jsonl').open('x',encoding='utf-8')
    for item in rows:
        with np.load(OUT/'views'/item['view']/'features_and_edges.npz') as z:
            ec=z['edge_index'].shape[1];ee=z['edge_index'];n=item['nodes'];vstart=item['virtual_global_start'];edges[:,cursor:cursor+ec]=np.where(ee<n,ee+item['start'],ee-n+vstart);roles[cursor:cursor+ec]=z['edge_roles'];cursor+=ec
            nv=item['virtual_nodes'];virtual[vstart-N:vstart-N+nv]=z['x'][n:]
            meta=json.loads((OUT/'views'/item['view']/'virtual_nodes.json').read_text())
            for j,m in enumerate(meta):vm.write(json.dumps(dict(global_node=vstart+j,view=item['view'],view_index=item['view_index'],trusted_label=False,SAT_covered=False,**m),ensure_ascii=False)+'\n')
    vm.close();edges.flush();roles.flush();dense.flush();virtual.flush();assert cursor==edgecount
    totals=np.sum([r['changed_nodes_by_column'] for r in rows],axis=0).tolist()
    completion=dict(time=stamp(),contract=CONTRACT,nodes=N,virtual_nodes=virtualcount,total_graph_nodes=N+virtualcount,views=len(rows),edges=edgecount,rows=rows,changes_by_column=totals,changed_any_node=sum(r['changed_any_node'] for r in rows),symmetric_edge_difference=sum(r['symmetric_edge_difference'] for r in rows),elapsed_seconds=time.perf_counter()-start,outputs={p.name:sha(p) for p in [densepath,virtualpath,edgepath,rolepath,OUT/'virtual_node_map.jsonl']},training_ready=False,note='Original global rows unchanged; auxiliary assign operators use appended ids >= original N. Graph input requires concatenating original and virtual feature arrays. Auxiliary nodes have unknown labels and no SAT; no loader, region or training changed.',labels_read=False,training_runs=0)
    write(OUT/'COMPLETE.json',completion);write(OUT/'state.json',dict(time=stamp(),phase='complete',nodes=N,views=len(rows)));print('COMPLETE',OUT,flush=True)
if __name__=='__main__':main()
