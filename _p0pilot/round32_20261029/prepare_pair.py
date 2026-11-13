"""Opt-in v2 original-side preparation and shared split contracts. No training/SAT."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,collections,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent
FOLD=ROOT/'generate_trans/folds/hosts_bt31';P=FOLD/'data/processed'
V=FOLD/'data/derived_v2/bitwise_alias_20261029_v2'
sys.path[:0]=[str(ROOT/'phase2/ys'),str(ROOT/'_p0pilot/round29_20261029')]
from feature_encoding_v2 import parse,features,load_library,COLS
from readonly_graph_arrays import arrays
from make_prim_feats import CELL2PRIM,PRIM
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    split=json.loads((FOLD/'views.json').read_text());role={v:s for s,key in [('train','train_views'),('val','val_views'),('test','test_views')] for v in split[key]}
    assert len(role)==388
    manifest=json.loads((V/'COMPLETE.json').read_text());assert manifest['total_graph_nodes']==3221975
    for filename,digest in manifest['outputs'].items():assert sha(V/filename)==digest
    old_o,_=arrays(P/'orig_graph.pt');old_t,_=arrays(P/'trans_graph.pt')
    meta=json.loads((FOLD/'data/for_train/metadata_orig.json').read_text())
    names=(H/'orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines()
    assert len(names)==len(old_o['y'])==len(meta['file_ids'])
    lookup=json.loads((FOLD/'gatelookup_recommended.json').read_text())['simplified_gate_type_order']
    mapping={r['full_gate_name']:r['simplified_gate_type'] for r in json.loads((FOLD/'gate_full_to_simplified_mapping.json').read_text())}
    lib=load_library(FOLD/'verilog_lib.v');rows=[]
    groups=[]
    for name,idx in __import__('itertools').groupby(enumerate(meta['file_ids']),lambda x:x[1]):
        indexes=[i for i,_ in idx];groups.append((name,indexes[0],indexes[-1]+1))
    for number,(view,lo,hi) in enumerate(groups):
        source=FOLD/'orig'/f'{view}.v';folder=H/'orig_v2'/view;done=folder/'COMPLETE.json'
        sourcehash=sha(source)
        if done.exists():
            item=json.loads(done.read_text());assert item['source_sha']==sourcehash and item['sha256']==sha(folder/'features_and_edges.npz')
        else:
            folder.mkdir(parents=True,exist_ok=True)
            g=parse(source,names[lo:hi],lib);x=features(g,mapping,lookup)
            assert np.array_equal(x[:hi-lo,:26],old_o['x'][lo:hi,:26])
            np.savez_compressed(folder/'features_and_edges.npz',x=x,edge_index=g['edge_index'],edge_roles=g['edge_roles'])
            item=dict(view=view,start=lo,stop=hi,nodes=hi-lo,virtual_nodes=len(g['virtual_nodes']),source_sha=sourcehash,sha256=sha(folder/'features_and_edges.npz'))
            write(done,item)
        rows.append(item);print('ORIG',number+1,len(groups),view,flush=True)
    # Read only the small original graph metadata to obtain verified source references.
    import torch
    torch.set_num_threads(1)
    original=torch.load(P/'orig_graph.pt',map_location='cpu',weights_only=False,mmap=True)
    refs=original.orig_view_map
    for item in rows:
        roles={role[v] for v in refs.get(item['view'],[]) if v in role}
        assert len(roles)<=1,('Source overlap',item['view'],roles)
        item['split']=next(iter(roles),'excluded')
    del original
    prim=np.zeros((25,7),np.float32)
    for j,name in enumerate(lookup):
        for p,count in CELL2PRIM[name].items():prim[j,PRIM.index(p)]=count
        prim[j]/=prim[j].sum()
    np.save(H/'primitive_matrix.npy',prim)
    transrows=manifest['rows']
    configs={};supervision={};train_sums=np.zeros(39,np.float64);train_squares=np.zeros(39,np.float64);train_count=0
    for domain,items,legacy in [('orig',rows,old_o),('trans',transrows,old_t)]:
        trust=np.load(P/f'trust_{domain}.npy');assert trust.shape==legacy['y'].shape and trust.dtype==np.bool_
        for s in ('train','val','test'):
            selected=[r for r in items if (r.get('split') if domain=='orig' else role.get(r['view'],'excluded'))==s]
            count=sum(r['nodes']+r['virtual_nodes'] for r in selected);ecount=0;loc=H/'inputs'/f'{domain}_{s}';loc.mkdir(parents=True,exist_ok=True)
            xout=np.lib.format.open_memmap(loc/'x39.npy',mode='w+',dtype=np.float32,shape=(count,39))
            yy=np.full(count,-1,np.int64);trusted=np.zeros(count,bool);originalmask=np.zeros(count,bool);views=[];offset=0;edges=[];edge_roles=[]
            for item in selected:
                view=item['view'];cache=(H/'orig_v2'/view if domain=='orig' else V/'views'/view)/'features_and_edges.npz'
                with np.load(cache) as z:
                    x=z['x'];n=item['nodes'];total=len(x)
                    assert total==n+item['virtual_nodes'] and np.isfinite(x).all()
                    assert np.array_equal(x[:n,:25],legacy['x'][item['start']:item['stop'],:25])
                    assert np.allclose(x[:,:25].sum(1),1)
                    e=z['edge_index'];assert e.min()>=0 and e.max()<total
                    xout[offset:offset+total]=x
                    edges.append(e+offset);edge_roles.append(z['edge_roles'])
                yy[offset:offset+n]=legacy['y'][item['start']:item['stop']]
                trusted[offset:offset+n]=trust[item['start']:item['stop']]
                originalmask[offset:offset+n]=True
                if s=='train':
                    # Fit solely on original physical training cells; auxiliary cells are context only.
                    a=x[:n].astype(np.float64);train_sums+=a.sum(0);train_squares+=(a*a).sum(0);train_count+=n
                views.append(dict(view=view,start=offset,stop=offset+total,physical_stop=offset+n,old_start=item['start'],old_stop=item['stop']))
                offset+=total
            assert offset==count
            xout.flush();ee=np.concatenate(edges,axis=1);er=np.concatenate(edge_roles)
            assert ee.shape[1]==len(er)
            for name,a in [('edge_index',ee),('edge_roles',er),('y',yy),('trusted',trusted),('physical',originalmask)]:np.save(loc/(name+'.npy'),a)
            assert not trusted[~originalmask].any() and np.all(yy[~originalmask]==-1)
            assert set(np.unique(yy[originalmask]))<= {0,1}
            key=f'{domain}_{s}';configs[key]=dict(folder=str(loc.relative_to(ROOT)),nodes=count,edges=ee.shape[1],views=views)
            supervision[key]=dict(views=len(views),physical_nodes=int(originalmask.sum()),auxiliary_nodes=int((~originalmask).sum()),trusted_nodes=int(trusted.sum()),trusted_positive=int((trusted&(yy==1)).sum()),legacy_positive=int((originalmask&(yy==1)).sum()),unknown_nodes=int((originalmask&~trusted).sum()))
            print(key,supervision[key],flush=True)
    mean=train_sums/train_count;std=np.sqrt(np.maximum(train_squares/train_count-mean*mean,0));std=np.maximum(std,1e-6)
    # Gate coding stays bounded and unstandardized. Shared 14 structural columns use identical train-only statistics.
    mean[:25]=0;std[:25]=1
    np.savez(H/'normalization.npz',mean=mean.astype(np.float32),std=std.astype(np.float32),fit_count=np.int64(train_count))
    filehashes={}
    for c in configs.values():
        for p in (ROOT/c['folder']).glob('*.npy'):filehashes[str(p.relative_to(ROOT))]=sha(p)
    write(H/'input_contract.json',dict(version='P2_A_v2_vs_primitive21_seed42_round32',shared_inputs=configs,
        normalization='Gate columns raw bounded; shared structural 14 columns train-only pooled orig/trans z-score clipped +/-10; no val/test fitting',
        graph='v2 directed all-pin edges, same order and roles in both arms; roles retained as metadata, no SAT',
        supervision='Trusted physical original cells only for train and primary evaluation; auxiliary and unknown excluded; legacy all-physical metrics secondary',
        original_rows=rows,columns39=COLS,columns21=PRIM+COLS[25:],primitive_matrix_sha=sha(H/'primitive_matrix.npy'),
        files=filehashes,split_sha=sha(FOLD/'views.json'),v2_completion_sha=sha(V/'COMPLETE.json')))
    write(H/'preflight.json',dict(passed=True,supervision=supervision,views_disjoint=True,original_sources_disjoint=True,
        auxiliary_supervision=False,loss_feature_position_read=False,SAT_features=False,training_started=False,
        primitive_matrix=prim.tolist(),source_graph_stats={p.name:dict(size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in [P/'orig_graph.pt',P/'trans_graph.pt']},
        note='Loader and producer audit. Numeric loss equivalence and forward/gradient smoke checks are required before 100 updates.'))
    print('PREPARED',flush=True)
if __name__=='__main__':main()
