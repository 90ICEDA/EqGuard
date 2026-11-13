"""Prepare old physical features on fixed v2 graph and untouched old graph controls."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,copy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;PRE=ROOT/'_p0pilot/round32_20261029'
sys.path.insert(0,str(ROOT/'_p0pilot/round29_20261029'))
from readonly_graph_arrays import arrays
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for a in iter(lambda:f.read(1048576),b''):h.update(a)
    return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    if (H/'PREPARED.json').exists():print('Prepared controls retained');return
    source=json.loads((PRE/'input_contract.json').read_text())
    for name,digest in source['files'].items():assert sha(ROOT/name)==digest
    fixed=copy.deepcopy(source);full=copy.deepcopy(source)
    fixed.update(version='old_physical39_on_fixed_v2_graph',graph=source['graph'],feature_note='Old physical-cell39; same v2 auxiliary context features. Isolates physical feature replacement on fixed topology.')
    full.update(version='old39_on_old_graph',graph='Untouched historical graph edges, same physical train/val/test nodes; no v2 auxiliary nodes',feature_note='Old physical39 plus old topology; whole preprocessing package control, not feature-only attribution.')
    sums=np.zeros(39,np.float64);squares=sums.copy();count=0;checks={}
    for domain in ('orig','trans'):
        legacy,_=arrays(ROOT/f'generate_trans/folds/hosts_bt31/data/processed/{domain}_graph.pt')
        for split in ('train','val','test'):
            key=f'{domain}_{split}';conf=source['shared_inputs'][key];base=ROOT/conf['folder']
            a={n:np.load(base/(n+'.npy'),mmap_mode='r') for n in ('x39','y','trusted','physical')}
            fd=H/'control_inputs/fixed_v2_graph'/key;ld=H/'control_inputs/old_graph'/key
            fd.mkdir(parents=True,exist_ok=True);ld.mkdir(parents=True,exist_ok=True)
            x=np.lib.format.open_memmap(fd/'x39.npy',mode='w+',dtype=np.float32,shape=a['x39'].shape);x[:]=a['x39']
            n=int(a['physical'].sum());lx=np.lib.format.open_memmap(ld/'x39.npy',mode='w+',dtype=np.float32,shape=(n,39))
            ly=np.empty(n,np.int64);lt=np.empty(n,bool);reverse=np.full(len(legacy['y']),-1,np.int64);cursor=0;lviews=[]
            for v in conf['views']:
                lo,hi=v['old_start'],v['old_stop'];size=hi-lo;vstart=v['start']
                assert size==v['physical_stop']-vstart
                assert np.array_equal(legacy['y'][lo:hi],a['y'][vstart:vstart+size])
                x[vstart:vstart+size]=legacy['x'][lo:hi]
                lx[cursor:cursor+size]=legacy['x'][lo:hi];ly[cursor:cursor+size]=legacy['y'][lo:hi];lt[cursor:cursor+size]=a['trusted'][vstart:vstart+size]
                reverse[lo:hi]=np.arange(cursor,cursor+size)
                lviews.append(dict(view=v['view'],start=cursor,stop=cursor+size,physical_stop=cursor+size,old_start=lo,old_stop=hi))
                if split=='train':
                    z=legacy['x'][lo:hi].astype(np.float64);sums+=z.sum(0);squares+=(z*z).sum(0);count+=size
                cursor+=size
            x.flush();lx.flush();assert cursor==n
            # Fixed-graph paths share the original edge/label/mask files byte for byte.
            # Folder-based loader needs hard links, never copies/modifies existing data.
            for name in ('edge_index','y','trusted','physical','edge_roles'):
                target=fd/(name+'.npy')
                if not target.exists():os.link(base/(name+'.npy'),target)
            edges=[];e=legacy['edge_index']
            for start in range(0,e.shape[1],262144):
                sub=e[:,start:start+262144];u=reverse[sub[0]];v=reverse[sub[1]];keep=u>=0
                assert np.all(v[keep]>=0),'Old cross-split edge'
                edges.append(np.stack([u[keep],v[keep]]))
            ee=np.concatenate(edges,1);owner=np.empty(n,np.int32)
            for j,v in enumerate(lviews):owner[v['start']:v['stop']]=j
            assert np.array_equal(owner[ee[0]],owner[ee[1]])
            for name,z in [('y',ly),('trusted',lt),('physical',np.ones(n,bool)),('edge_index',ee)]:np.save(ld/(name+'.npy'),z)
            fixed['shared_inputs'][key]={**conf,'folder':str(fd.relative_to(ROOT))}
            full['shared_inputs'][key]=dict(folder=str(ld.relative_to(ROOT)),nodes=n,edges=ee.shape[1],views=lviews)
            checks[key]=dict(physical_labels_identical=True,physical_trust_identical=True,fixed_edges_identical=True,old_nodes=n,old_edges=ee.shape[1],fixed_nodes=conf['nodes'],fixed_edges=conf['edges'],no_cross_view_edges=True)
            print(key,checks[key],flush=True)
    mean=sums/count;std=np.maximum(np.sqrt(np.maximum(squares/count-mean*mean,0)),1e-6);mean[:25]=0;std[:25]=1
    np.savez(H/'old_normalization.npz',mean=mean.astype(np.float32),std=std.astype(np.float32),fit_count=np.int64(count))
    for name,contract in [('fixed',fixed),('old_graph',full)]:
        contract['files']={str(p.relative_to(ROOT)):sha(p) for c in contract['shared_inputs'].values() for p in (ROOT/c['folder']).glob('*.npy')}
        write(H/(name+'_contract.json'),contract)
    write(H/'PREPARED.json',dict(passed=True,controls=checks,normalization_fit='Same train-only pooled physical orig/trans procedure, own old-feature statistics; not fitted on validation/test',previous_contract_sha=sha(PRE/'input_contract.json'),previous_comparison_sha=sha(PRE/'comparison.json'),SAT_queries=0))
    print('PREPARED',flush=True)
if __name__=='__main__':main()
