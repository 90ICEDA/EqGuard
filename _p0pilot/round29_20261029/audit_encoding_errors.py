"""Bounded read-only audit. No torch load, model execution, training or solver."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import ctypes,json,csv,re,hashlib,time,datetime,collections,struct,sys,gc
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import rankdata,spearmanr
from readonly_graph_arrays import arrays
try:ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
except Exception:pass
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
FOLD=ROOT/'generate_trans/folds/hosts_bt31';P=FOLD/'data/processed'
OUT=HERE/('encoding_error_audit_v2' if os.environ.get('ENCODING_ONLY')=='1' else 'encoding_error_audit')
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(p,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def auc(p,n):
    if not len(p) or not len(n):return None
    a=np.r_[p,n];rr=rankdata(a);return float((rr[:len(p)].sum()-len(p)*(len(p)+1)/2)/(len(p)*len(n)))
def ap(y,s):
    if not y.any():return None
    order=np.argsort(-s,kind='stable');s=s[order];y=y[order]
    ends=np.r_[np.flatnonzero(s[:-1]!=s[1:]),len(s)-1];tp=np.cumsum(y)[ends]
    return float(np.sum(np.diff(np.r_[0,tp])*tp/(ends+1))/y.sum())
def group_regions(edge,isff,po=None):
    n=len(isff);src,dst=edge;lab=np.full(n,-1,np.int64)
    if po is None:
        has=np.zeros(n,bool);has[dst]=True;seeds=np.flatnonzero(isff|~has);keep=~isff[dst];s,t=src[keep],dst[keep]
    else:seeds=np.flatnonzero(po);keep=~isff[src];s,t=src[keep],dst[keep]
    lab[seeds]=seeds
    for _ in range(256):
        if po is None:m=(lab[t]<0)&(lab[s]>=0);dd,ss=t[m],lab[s[m]]
        else:m=(lab[s]<0)&(lab[t]>=0);dd,ss=s[m],lab[t[m]]
        if not m.any():break
        _,first=np.unique(dd,return_index=True);lab[dd[first]]=ss[first]
    missing=lab<0;lab[missing]=np.flatnonzero(missing)
    return np.unique(lab,return_inverse=True)[1]
def bfs(edges,n,seeds):
    adj=[[] for _ in range(n)]
    for u,v in edges:adj[u].append(v)
    d=np.full(n,-1,np.int32);q=collections.deque(sorted(set(seeds)));d[list(q)]=0
    while q:
        u=q.popleft()
        for v in adj[u]:
            if d[v]<0:d[v]=d[u]+1;q.append(v)
    return d,adj
def fan2(adj):
    exact=[];within=[]
    for i,nn in enumerate(adj):
        second={v for u in nn for v in adj[u]};second.discard(i)
        union=second|set(nn);union.discard(i)
        exact.append(np.log1p(len(second)));within.append(np.log1p(len(union)))
    return np.asarray(exact),np.asarray(within)
def source_graph(path,nodenames,lib):
    text=re.sub(r'//[^\n]*|/\*.*?\*/','',path.read_text(encoding='utf-8'),flags=re.S)
    parent={};decl_ranges={};decls=[]
    for m in re.finditer(r'(?:^|;)\s*(input|output|wire)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*([^;]+);',text):
        kind,msb,lsb,body=m.groups()
        for v in body.split(','):
            v=v.strip().lstrip('\\')
            if msb is not None:decl_ranges[v]=list(range(int(msb),int(lsb)+(1 if int(lsb)>=int(msb) else -1),1 if int(lsb)>=int(msb) else -1))
            if kind in ('input','output'):decls.append((kind,v))
    # Separate statement pass avoids the consuming-semicolon regex skipping adjacent declarations.
    for st in text.split(';'):
        m=re.match(r'^\s*(input|output|wire)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*([^;]+)$',st,re.S)
        if not m:continue
        kind,msb,lsb,body=m.groups()
        for v in body.split(','):
            v=v.strip().lstrip('\\')
            if msb is not None:decl_ranges[v]=list(range(int(msb),int(lsb)+(1 if int(lsb)>=int(msb) else -1),1 if int(lsb)>=int(msb) else -1))
            if kind in ('input','output') and (kind,v) not in decls:decls.append((kind,v))
    def bits(s):
        s=s.strip().lstrip('\\')
        if s.startswith('{') and s.endswith('}'):
            out=[]
            for a in s[1:-1].split(','):out+=bits(a)
            return out
        return [f'{s}[{b}]' for b in decl_ranges[s]] if s in decl_ranges else [s]
    def canon(x):
        x=x.strip().lstrip('\\');path=[]
        while x in parent and parent[x]!=x:path.append(x);x=parent[x]
        for k in path:parent[k]=x
        return x
    # Alias equality is independent of textual replacement direction.
    for m in re.finditer(r'\bassign\s+(.+?)\s*=\s*(.+?)\s*;',text,re.S):
        a,b=m.groups()
        aa,bb=bits(a),bits(b)
        if len(aa)==len(bb):
            for av,bv in zip(aa,bb):
                if not re.fullmatch(r'[\w.$/\[\]:]+',av) or not re.fullmatch(r'[\w.$/\[\]:]+',bv):continue
                ca,cb=canon(av),canon(bv)
                if ca!=cb:parent[ca]=cb
    pi=set();po=set();cells={}
    for st in text.split(';'):
        st=re.sub(r'\(\*.*?\*\)','',st,flags=re.S).strip()
        m=re.match(r'^([\w$]+)\s+(\\\S+|[^\s(]+)\s*\((.*)\)\s*$',st,re.S)
        if m and m[1] in lib:
            cells[m[2].lstrip('\\')]=(m[1],[(p,canon(n)) for p,n in re.findall(r'\.\s*(\w+)\s*\(\s*([^()]*)\s*\)',m[3])])
    for kind,v in decls:(pi if kind=='input' else po).update(canon(b) for b in bits(v))
    owners={s:i for i,s in enumerate(nodenames)};drivers=collections.defaultdict(list);cons=collections.defaultdict(list)
    gate=[];ports=[];tip=[];top=[];unmatched=[]
    for name in nodenames:
        if name not in cells:unmatched.append(name);gate.append('MISSING');ports.append(0);tip.append(0);top.append(0);continue
        typ,connections=cells[name];i=owners[name];gate.append(typ);ports.append(len(lib[typ]['input']))
        tip.append(int(any(net in pi for p,net in connections)));top.append(int(any(net in po for p,net in connections)))
        for pin,net in connections:
            if pin in lib[typ]['output']:drivers[net].append(i)
            if pin in lib[typ]['input']:cons[net].append(i)
    edges=[];mult=collections.Counter()
    for net,ds in drivers.items():
        for u in ds:
            for v in cons.get(net,[]):edges.append((u,v));mult[u]+=1;mult[v]+=1
    return gate,np.log1p(ports),np.array(tip),np.array(top),edges,np.log1p([mult[i] for i in range(len(gate))]),unmatched
def main():
    OUT.mkdir(exist_ok=False)
    start=time.perf_counter();a,desc=arrays(P/'trans_graph.pt');x=a['x'];e=a['edge_index'];y=a['y'];N=len(x)
    vi=np.load(HERE/'frozen/view_index_all.npy',mmap_mode='r');manifest=json.loads((HERE/'frozen/manifest.json').read_text());names=manifest['view_names'];views=json.loads((FOLD/'views.json').read_text());vsplit={v:s for s,k in [('train','train_views'),('val','val_views'),('test','test_views')] for v in views[k]}
    bounds={};basic=dict(nodes=N,shape=list(x.shape),header=desc,onehot_bad=0,feature_npy_mismatch_rows=0,edges_cross_view=0,edge_source_sorted=True,finite=True)
    diskx=np.load(FOLD/'data/for_train/feats_trans.npy',mmap_mode='r')
    for b in range(0,N,65536):
        z=x[b:b+65536];basic['onehot_bad']+=int(((z[:,:25].sum(1)!=1)|~np.isin(z[:,:25],[0,1]).all(1)).sum());basic['feature_npy_mismatch_rows']+=int(np.any(z!=diskx[b:b+65536].astype(np.float32),axis=1).sum());basic['finite'] &= bool(np.isfinite(z).all())
    for b in range(0,e.shape[1],131072):
        u,v=e[:,b:b+131072];basic['edges_cross_view']+=int((vi[u]!=vi[v]).sum());basic['edge_source_sorted'] &= bool(np.all(np.diff(e[0,max(0,b-1):b+131072])>=0))
    for i,v in enumerate(names):
        ids=np.flatnonzero(vi==i);assert np.all(np.diff(ids)==1);bounds[v]=(int(ids[0]),int(ids[-1]+1))
    assert basic['edge_source_sorted'];print('global invariants complete',flush=True)
    selected=[]
    for host in ['rs232t1000','s35932t200','s38417t100','s38584t100']:
        for recipe in ['ys_abc','ys_aig','ys_nand']:
            vv=sorted(v for v in names if v.startswith(host+'__injalpha_') and v.endswith('__'+recipe))
            if vv:selected.append(vv[0])
    wanted=set()
    for v in selected:wanted.update(range(*bounds[v]))
    nameby={}
    with (P/'node_names_trans.txt').open(encoding='utf-8') as f:
        for i,line in enumerate(f):
            if i in wanted:nameby[i]=line.strip().lstrip('\\')
    lib={};txt=(FOLD/'verilog_lib.v').read_text(encoding='utf-8')
    for m in re.finditer(r'module\s+(\w+)\b.*?;(.*?)endmodule',txt,re.S):
        lib[m[1]]={'input':[],'output':[]}
        for d in re.finditer(r'\b(input|output)\s+([^;]+);',m[2]):lib[m[1]][d[1]] += [s for s in re.split(r'[,\s]+',d[2].strip()) if s]
    mapping={r['full_gate_name']:r['simplified_gate_type'] for r in json.loads((FOLD/'gate_full_to_simplified_mapping.json').read_text())};order=json.loads((FOLD/'gatelookup_recommended.json').read_text())['simplified_gate_type_order'];directed_regions={};encoding=[];mismatches=[];casegraph={}
    for view in selected:
        lo,hi=bounds[view];xx=x[lo:hi];nn=[nameby[i] for i in range(lo,hi)];g,pins,pi,po,de,degree,missing=source_graph(FOLD/'trans'/f'{view}.v',nn,lib)
        assert not missing,(view,missing[:5]);n=len(xx);isff=np.array(['DFF' in t.upper() for t in g]);truth={25:pins,26:degree,27:pi,28:po}
        truthgate=np.array([order.index(mapping[t]) for t in g]);bad=truthgate!=xx[:,:25].argmax(1)
        eu=e[:,np.searchsorted(e[0],lo):np.searchsorted(e[0],hi)]-lo
        assert np.all((eu>=0)&(eu<n));storedpairs=set(zip(*eu));expectpairs=set(de)|{(v,u) for u,v in de}
        diff=storedpairs^expectpairs;rr=dict(view=view,nodes=n,gate_mismatch=int(bad.sum()),missing_source_cells=len(missing),undirected_edge_symmetric_difference=len(diff),directed_edges=len(set(de)),stored_edges=eu.shape[1])
        d0,adj=bfs(de,n,np.flatnonzero(pi));rev=[(v,u) for u,v in de];d1,pred=bfs(rev,n,np.flatnonzero(po));truth[29]=d0;truth[30]=d1
        truth[31],withinfi=fan2(pred);truth[32],withinfo=fan2(adj)
        fwd=[(u,v) for u,v in de if not isff[v]];revf=[(u,v) for u,v in de if not isff[u]]
        seeds0=sorted({v for u,v in de if isff[u]}) if isff.any() else np.flatnonzero(pi)
        seeds1=sorted({u for u,v in de if isff[v]}) if isff.any() else np.flatnonzero(po)
        d2,adj2=bfs(fwd,n,seeds0);d3,pred2=bfs([(v,u) for u,v in revf],n,seeds1);d2[isff]=0;d3[isff]=0;truth[33]=d2;truth[34]=d3
        _,predfi=bfs([(v,u) for u,v in fwd],n,[]);_,adjfo=bfs(revf,n,[])
        truth[35],_=fan2(predfi);truth[36],_=fan2(adjfo)
        mat=csr_matrix((np.ones(len(revf)),np.array(revf).T),shape=(n,n));_,scc=connected_components(mat,directed=True,connection='strong');sizes=np.bincount(scc);loops={u for u,v in revf if u==v};truth[37]=np.array([sizes[c]>1 or i in loops for i,c in enumerate(scc)],int);truth[38]=np.log1p(sizes[scc])
        for j,expected in truth.items():
            bad=~np.isclose(xx[:,j],expected,atol=2e-6,rtol=2e-6);rr[f'col{j}_mismatch']=int(bad.sum())
            for k in np.flatnonzero(bad)[:3]:mismatches.append(dict(view=view,node=int(lo+k),cell=nn[k],column=j,stored=float(xx[k,j]),expected=float(expected[k])))
        rr['fan31_within2_disagree']=int((~np.isclose(xx[:,31],withinfi)).sum());rr['fan32_within2_disagree']=int((~np.isclose(xx[:,32],withinfo)).sum())
        undreg=group_regions(eu,isff);dirreg=group_regions(np.array(de,dtype=np.int64).T,isff)
        directed_regions[view]=(undreg,dirreg)
        rr['undirected_regions']=len(np.unique(undreg));rr['directed_regions']=len(np.unique(dirreg));rr['undirected_components']=connected_components(csr_matrix((np.ones(eu.shape[1]),eu),shape=(n,n)),directed=False,return_labels=False)
        rr['undirected_symmetric']=len(storedpairs^{(v,u) for u,v in storedpairs})==0
        encoding.append(rr);casegraph[view]=(eu,nn,np.array(de,dtype=np.int64).T)
        print('source recompute',view,flush=True)
    csvout(OUT/'encoding_recompute_by_view.csv',encoding);csvout(OUT/'encoding_mismatch_examples.csv',mismatches);write(OUT/'global_invariants.json',basic)
    if os.environ.get('ENCODING_ONLY')=='1':
        write(OUT/'summary.json',dict(time=datetime.datetime.now().astimezone().isoformat(),checked_encoding_nodes=sum(r['nodes'] for r in encoding),selected_views=selected,new_sat_queries=0,training_runs=0,revision='Corrected auditor float32 comparison, pin multiplicity, vector bit aliases, f35/36 direction. Initial audit discrepancies in these areas are superseded.'))
        return
    # Existing predictions only. Validation is primary diagnosis; test is retrospective.
    positive_rows=[];errors=[];groups=[];viewrows=[];regionrows=[];bindings=[]
    trust=np.load(P/'trust_trans.npy',mmap_mode='r')
    cachepath=ROOT.parent/'_devcfg/region_cache/hosts_bt31_dff.npz';cache=np.load(cachepath)['inv'] if cachepath.exists() else None
    cachechecks=[]
    if cache is not None:
        for view,(ur,dr) in directed_regions.items():
            lo,hi=bounds[view];cr=np.unique(cache[lo:hi],return_inverse=True)[1]
            # Partition equality independent of numerical region ids.
            pairs=np.unique(np.stack([cr,ur],axis=1),axis=0)
            cachechecks.append(dict(view=view,cached_regions=len(np.unique(cr)),rebuilt_undirected_regions=len(np.unique(ur)),same_partition=len(pairs)==len(np.unique(cr))==len(np.unique(ur))))
    for model,prefix in [('B39','gnn_v31a_A2'),('region','gnn_v31r_l100')]:
      for seed in [42,1,2]:
        path=ROOT/'_devcfg'/f'{prefix}_s{seed}.npz';z=np.load(path);ids=z['idx'];scores=z['score'];test=z['test'];assert np.all(np.diff(ids)>0)
        bindings.append(dict(model=model,seed=seed,path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        for view in views['val_views']+views['test_views']:
            lo,hi=bounds[view];pos0,pos1=np.searchsorted(ids,[lo,hi]);ii=ids[pos0:pos1];assert np.array_equal(ii,np.arange(lo,hi));s=scores[pos0:pos1];yy=np.array(y[lo:hi],dtype=np.int8);xx=x[lo:hi];gate=xx[:,:25].argmax(1);isff=np.isin(gate,[4,5,6,19,20]);n=len(ii)
            split=vsplit[view];assert np.all(test[pos0:pos1]==(split=='test'))
            edge=e[:,np.searchsorted(e[0],lo):np.searchsorted(e[0],hi)]-lo
            # One symmetric adjacency is already stored in the graph.
            adj=csr_matrix((np.ones(edge.shape[1],np.int8),edge),shape=(n,n));reg=np.unique(cache[lo:hi],return_inverse=True)[1] if cache is not None else group_regions(edge,isff)
            ranks=rankdata(-s,method='min');ranksmax=rankdata(-s,method='max');rankmean=(ranks+ranksmax)/2;top=ranks<=max(1,int(n*.01))
            for j in np.flatnonzero(yy):
                rr=reg==reg[j];ng=(yy==0)&(gate==gate[j]);binpos=np.floor_divide(xx[:,30],4);ngp=ng&(binpos==binpos[j]);nr=np.flatnonzero(rr);localrank=1+int((s[rr]>s[j]).sum());localworst=int((s[rr]>=s[j]).sum());nbr=adj.indices[adj.indptr[j]:adj.indptr[j+1]]
                positive_rows.append(dict(model=model,seed=seed,split=split,view=view,node=int(lo+j),gate=order[gate[j]],score=float(s[j]),rank_best=int(ranks[j]),rank_worst=int(ranksmax[j]),view_nodes=n,rank_fraction=float(rankmean[j]/n),in_top1pct=bool(top[j]),region_size=int(rr.sum()),region_positive=int(yy[rr].sum()),region_rank_best=localrank,region_rank_worst=localworst,negative_same_gate=int(ng.sum()),auc_same_gate=float(np.mean((s[j]>s[ng])+.5*(s[j]==s[ng]))) if ng.any() else None,negative_same_gate_PO_bin=int(ngp.sum()),auc_same_gate_PO_bin=float(np.mean((s[j]>s[ngp])+.5*(s[j]==s[ngp]))) if ngp.any() else None,neighbor_count=len(nbr),neighbor_positive=int(yy[nbr].sum()),neighbor_dff=int(isff[nbr].sum()),PI_dist=float(xx[j,29]),PO_dist=float(xx[j,30]),trusted=bool(trust[lo+j])))
            for j in np.argsort(-s,kind='stable')[yy[np.argsort(-s,kind='stable')]==0][:5]:
                nb=adj.indices[adj.indptr[j]:adj.indptr[j+1]];rr=reg==reg[j]
                errors.append(dict(model=model,seed=seed,split=split,view=view,node=int(lo+j),gate=order[gate[j]],score=float(s[j]),rank=int(ranks[j]),degree=len(nb),neighbor_positive=int(yy[nb].sum()),neighbor_DFF=int(isff[nb].sum()),PO_dist=float(xx[j,30]),PI_dist=float(xx[j,29]),region_size=int(rr.sum()),region_positive=int(yy[rr].sum()),trusted=bool(trust[lo+j])))
            for g0 in np.unique(gate):
                m=gate==g0;neg=m&(yy==0);groups.append(dict(model=model,seed=seed,split=split,view=view,group_kind='gate',group=order[g0],nodes=int(m.sum()),positive=int(yy[m].sum()),negative_mean_score=float(s[neg].mean()) if neg.any() else None,top1pct_negative=int((top&neg).sum()),negative=int(neg.sum())))
            for b in sorted(np.unique(np.floor_divide(xx[:,30],4))):
                m=np.floor_divide(xx[:,30],4)==b;neg=m&(yy==0);groups.append(dict(model=model,seed=seed,split=split,view=view,group_kind='PO_distance_bin4',group=str(int(b)),nodes=int(m.sum()),positive=int(yy[m].sum()),negative_mean_score=float(s[neg].mean()) if neg.any() else None,top1pct_negative=int((top&neg).sum()),negative=int(neg.sum())))
            neg=yy==0;rho=float(spearmanr(xx[neg,30],s[neg]).statistic) if len(np.unique(xx[neg,30]))>1 and len(np.unique(s[neg]))>1 else None
            viewrows.append(dict(model=model,seed=seed,split=split,view=view,recipe=view.split('__')[-1],host=view.split('__')[0],nodes=n,positive=int(yy.sum()),AP=ap(yy,s),AUC=auc(s[yy==1],s[yy==0]),normal_mean_score=float(s[neg].mean()),normal_median_score=float(np.median(s[neg])),score_PO_spearman_negative=rho,top1pct_positive=int((top&(yy==1)).sum()),is_control='__inj' not in view))
            if view in directed_regions:
                ur,dr=directed_regions[view]
                for typ,rrr in [('stored_cache',reg),('recomputed_undirected',ur),('physical_direction',dr)]:
                    for j in np.flatnonzero(yy):
                        m=rrr==rrr[j];regionrows.append(dict(model=model,seed=seed,view=view,split=split,node=int(lo+j),region_type=typ,region_size=int(m.sum()),positive=int(yy[m].sum()),rank_best=1+int((s[m]>s[j]).sum()),rank_worst=int((s[m]>=s[j]).sum())))
        print('prediction diagnostics',model,seed,flush=True);del z,ids,scores,test;gc.collect()
    csvout(OUT/'positive_node_ranks.csv',positive_rows);csvout(OUT/'top_false_positive_neighbors.csv',errors);csvout(OUT/'score_groups.csv',groups);csvout(OUT/'view_diagnostics.csv',viewrows);csvout(OUT/'region_direction_comparison.csv',regionrows);csvout(OUT/'region_cache_checks.csv',cachechecks)
    write(OUT/'summary.json',dict(time=datetime.datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-start,read_only=True,training_runs=0,new_sat_queries=0,model_forwards=0,selected_encoding_views=selected,checked_encoding_nodes=sum(r['nodes'] for r in encoding),prediction_bindings=bindings,cache_path=str(cachepath),source_files=dict(parser='data/verilog_data/parser2.py',graph='process_pt2.py',region='phase2/ys/region_loss.py'),limitations=['Only existing frozen predictions. No interventions or new inference; observed dependence is descriptive.','Validation used for primary diagnosis; test is retrospective and no longer fresh for confirmation.','Graph input is undirected; physical directed regions are diagnostic alternatives, not a rerun of the trained model.','Source recomputation is independently implemented and mismatches require inspection before declaring a bug.','Normal means label zero; trust recorded separately.']))
    print(OUT,flush=True)
if __name__=='__main__':main()
