"""Label-blind validation/test k4 completion using unchanged round27 solvers.

Preparation and extraction are queued after the current training supervisor.
No training or label-based candidate/feature selection occurs here.
"""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import argparse,array,collections,datetime,gc,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
import numpy as np
import psutil
HERE=Path(__file__).resolve().parent
SCRIPTS=HERE.parent/'round27_20261027';sys.path.insert(0,str(SCRIPTS))
import k4_runtime as R
ROOT=R.ROOT;META=ROOT/'generate_trans/folds/hosts_bt31/data/for_train/metadata_trans.json'
GRAPH=ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt'
VIEWS=ROOT/'generate_trans/folds/hosts_bt31/views.json'
PANELS={s:R.TABLES/f'sat_k4_{s}_round29' for s in ('validation','test')}
FROZEN=HERE/'frozen'
NOW=lambda:datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);R.write_new(p,d)

def stream_file_ids(path,chunk=65536):
    """Stream only metadata file_ids; no labels and no 160MB JSON tree."""
    dec=json.JSONDecoder();pattern=re.compile(r'"file_ids"\s*:\s*\[')
    with Path(path).open(encoding='utf-8-sig') as f:
        buf=''
        while True:
            more=f.read(chunk)
            if not more:raise ValueError('file_ids array missing')
            buf+=more;m=pattern.search(buf)
            if m:buf=buf[m.end():];break
            buf=buf[-256:]
        idx=0
        while True:
            while idx<len(buf) and (buf[idx].isspace() or buf[idx]==','):idx+=1
            if idx<len(buf) and buf[idx]==']':return
            try:value,end=dec.raw_decode(buf,idx)
            except json.JSONDecodeError:
                more=f.read(chunk)
                if not more:raise ValueError('Unterminated file_ids array')
                buf=buf[idx:]+more;idx=0;continue
            if not isinstance(value,str):raise ValueError('Expected file_ids strings')
            yield value;idx=end
            if idx>chunk:buf=buf[idx:];idx=0

def freeze():
    if FROZEN.exists():raise RuntimeError('Frozen directory already exists; retained unchanged')
    FROZEN.mkdir(parents=True)
    split=json.loads(VIEWS.read_text());names=split['train_views']+split['val_views']+split['test_views']
    assert len(names)==len(set(names))==388 and len(split['val_views'])==65 and len(split['test_views'])==64
    lookup={v:i for i,v in enumerate(names)};indices=array.array('h');other=collections.Counter()
    for v in stream_file_ids(META):
        indices.append(lookup.get(v,-1))
        if v not in lookup:other[v]+=1
    vi=np.asarray(indices,dtype=np.int16);assert len(vi)==3220146
    np.save(FROZEN/'view_index_all.npy',vi)
    counts=np.bincount(vi[vi>=0],minlength=len(names));assert np.all(counts>0)
    template=R.read_plan(R.PANEL/'plan.json');summary={}
    for label,key,short in [('validation','val_views','val'),('test','test_views','test')]:
        panel=PANELS[label]
        if panel.exists():raise RuntimeError(f'Existing panel retained: {panel}')
        panel.mkdir(parents=True);plan={k:v for k,v in template.items() if k not in ('views','created','scope','selection','split','sample_rule')}
        plan.update(created=NOW(),scope=f'all frozen GLOBAL {label} views; native k4 all graph cells',selection='ALL graph cells; labels never inspected',split=short,sample_rule='all graph cells; no label-based candidates',views=[])
        for v in split[key]:
            src=ROOT/'generate_trans/folds/hosts_bt31/trans'/(v+'.v');assert src.exists()
            item=dict(view=v,family=v.split('__')[1],split=short,source=str(src.relative_to(ROOT)),source_sha=R.sha(src),bytes=src.stat().st_size,nodes=int(counts[lookup[v]]))
            plan['views'].append(item)
        plan['plan_sha']=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest();write(panel/'plan.json',plan)
        for item in plan['views']:
            one=dict(plan);one.pop('plan_sha');one['views']=[item];one['selection']='single frozen GLOBAL holdout view; all cells; label blind'
            one['plan_sha']=hashlib.sha256(json.dumps(one,sort_keys=True).encode()).hexdigest();write(panel/'views'/item['view']/'plan.json',one)
        summary[label]=dict(views=len(plan['views']),nodes=sum(i['nodes'] for i in plan['views']),panel=str(panel.relative_to(ROOT)),plan_sha=R.sha(panel/'plan.json'))
    source=dict(created=NOW(),view_names=names,view_counts=counts.tolist(),graph_nodes=len(vi),unlisted_nodes=dict(other),split_views_sha=R.sha(VIEWS),metadata_sha=R.sha(META),view_index_sha=R.sha(FROZEN/'view_index_all.npy'),graph_file=dict(path=str(GRAPH),size=GRAPH.stat().st_size,mtime_ns=GRAPH.stat().st_mtime_ns),panels=summary,labels_read=False,new_training_runs=0,new_sat_queries=0,
        contract={k:template[k] for k in ['context','cut_rule','target_rule','sat_timeout','sat_batch_nodes']},solver_scripts={n:R.sha(SCRIPTS/n) for n in ['extract_k4_alltrain.py','k4_runtime.py','run_one_k4_alltrain.py','run_all_k4_alltrain.py']})
    write(FROZEN/'manifest.json',source);print(json.dumps(source['panels'],ensure_ascii=False),flush=True)

def assert_frozen():
    m=json.loads((FROZEN/'manifest.json').read_text());assert R.sha(VIEWS)==m['split_views_sha']
    assert GRAPH.stat().st_size==m['graph_file']['size'] and GRAPH.stat().st_mtime_ns==m['graph_file']['mtime_ns']
    assert R.sha(FROZEN/'view_index_all.npy')==m['view_index_sha']
    for n,h in m['solver_scripts'].items():
        current=R.sha(SCRIPTS/n)
        if current!=h:
            approval=json.loads((HERE/'acceleration_approval.json').read_text())
            assert approval['original_scripts'].get(n)==h and approval['approved_scripts'].get(n)==current
            for filename,digest in approval['support_files'].items():assert R.sha(ROOT/filename)==digest
            assert approval['semantics_unchanged'] and approval['formal_miter_cases']==18
    return m

def prepare(label):
    m=assert_frozen();panel=PANELS[label];plan=R.read_plan(panel/'plan.json')
    if (panel/'base_inputs.npz').exists():
        if not (panel/'base_binding.json').exists():raise RuntimeError('Incomplete base retained; inspect before resuming')
        b=json.loads((panel/'base_binding.json').read_text());assert R.sha(panel/'base_inputs.npz')==b['base_sha'];return
    import torch
    torch.set_num_threads(1);g=torch.load(GRAPH,map_location='cpu',weights_only=False,mmap=True)
    vi=np.load(FROZEN/'view_index_all.npy',mmap_mode='r');assert len(g.file_ids)==len(vi)
    # Exact comparison with the processed graph, never g.y or class maps.
    selected_names={a['view'] for a in plan['views']};indices={v:i for i,v in enumerate(m['view_names'])};localview={indices[a['view']]:i for i,a in enumerate(plan['views'])}
    gids=np.flatnonzero(np.isin(vi,list(localview)));assert len(gids)==m['panels'][label]['nodes']
    for j in gids:assert g.file_ids[int(j)]==m['view_names'][int(vi[j])]
    selected_vi=np.array([localview[int(v)] for v in vi[gids]],dtype=np.int16)
    attempt=R.fresh_dir(panel/'base_builds','build');n=len(gids);width=int(g.x.shape[1]);dtype=g.x[:1].numpy().dtype
    x=np.lib.format.open_memmap(attempt/'x.npy',mode='w+',dtype=dtype,shape=(n,width))
    for start in range(0,n,32768):x[start:start+32768]=g.x[torch.from_numpy(gids[start:start+32768])].numpy()
    x.flush();rev=np.full(len(vi),-1,np.int32);rev[gids]=np.arange(n,dtype=np.int32)
    edges=g.edge_index.numpy();assert edges.shape[0]==2
    def chunks():
        for start in range(0,edges.shape[1],262144):
            e=edges[:,start:start+262144];a=rev[e[0]];b=rev[e[1]];keep=a>=0
            assert np.all(b[keep]>=0),'Cross-split edge'
            ee=np.stack([a[keep],b[keep]]).astype(np.int64)
            if ee.size:assert np.all(selected_vi[ee[0]]==selected_vi[ee[1]]),'Cross-view edge'
            yield ee
    ne=sum(e.shape[1] for e in chunks());ei=np.lib.format.open_memmap(attempt/'edge_index.npy',mode='w+',dtype=np.int64,shape=(2,ne));offset=0
    for e in chunks():ei[:,offset:offset+e.shape[1]]=e;offset+=e.shape[1]
    ei.flush();assert offset==ne
    with (attempt/'base_inputs.npz').open('xb') as f:np.savez_compressed(f,global_ids=gids,x=x,edge_index=ei,view_index=selected_vi)
    with (attempt/'base_inputs.npz').open('rb') as f,(panel/'base_inputs.npz').open('xb') as dst:shutil.copyfileobj(f,dst,1024*1024)
    write(panel/'base_binding.json',dict(time=NOW(),nodes=n,edges=ne,feature_width=width,base_sha=R.sha(panel/'base_inputs.npz'),processed_graph_sha=R.sha(GRAPH),frozen_manifest_sha=R.sha(FROZEN/'manifest.json'),labels_read=False,all_selected_file_ids_verified=True))
    print('PREPARED',label,n,ne,flush=True)

def merge(label):
    panel=PANELS[label];plan=R.read_plan(panel/'plan.json');gids=[];features=[];bindings=[];columns=None
    for item in plan['views']:
        folder=panel/'views'/item['view'];ok,detail=R.validate_complete(folder)
        if not ok:raise ValueError((item['view'],detail))
        c=json.loads((folder/'coverage.json').read_text());s=item['split']
        assert c['splits'][s]['nodes']==item['nodes'] and all(not d['nodes'] for k,d in c['splits'].items() if k!=s)
        if columns is None:columns=c['columns']
        assert c['columns']==columns
        with np.load(R.view_base_path(folder)) as z:gids.append(z['global_ids'])
        features.append(np.load(folder/'real.npy'));bindings.append(dict(view=item['view'],real_sha=R.sha(folder/'real.npy'),coverage_sha=R.sha(folder/'coverage.json')))
    ids=np.concatenate(gids);x=np.concatenate(features);assert len(np.unique(ids))==len(ids);order=np.argsort(ids)
    out=R.fresh_dir(panel/'exports','export')
    with (out/'real_k4.npz').open('xb') as f:np.savez_compressed(f,global_ids=ids[order],features=x[order],columns=np.array(columns))
    write(out/'summary.json',dict(time=NOW(),split=plan['split'],views=len(plan['views']),nodes=len(ids),covered=int(x[:,18].sum()),columns=columns,plan_sha=R.sha(panel/'plan.json'),export_sha=R.sha(out/'real_k4.npz'),inputs=bindings,labels_read=False,permuted_outputs_not_approved_for_training=True))
    print('MERGED',label,out,flush=True)

def full_export():
    m=assert_frozen();vi=np.load(FROZEN/'view_index_all.npy',mmap_mode='r');split=json.loads(VIEWS.read_text());names=m['view_names'];name_split={v:i for i,k in enumerate(['train_views','val_views','test_views']) for v in split[k]}
    split_by_view=np.array([name_split[v] for v in names],np.int8);expected=np.full(len(vi),-1,np.int8);keep=vi>=0;expected[keep]=split_by_view[vi[keep]]
    sources=[sorted((R.PANEL/'full_training_exports').glob('export_*/all_training_k4.npz'))[-1]]+[sorted((PANELS[s]/'exports').glob('export_*/real_k4.npz'))[-1] for s in ['validation','test']]
    out=R.fresh_dir(HERE/'all_split_exports','export');dense=np.lib.format.open_memmap(out/'all_splits_real_k4.npy',mode='w+',dtype=np.float32,shape=(len(vi),19));dense[:]=0;seen=np.zeros(len(vi),bool);bindings=[]
    for i,p in enumerate(sources):
        with np.load(p) as z:ids=z['global_ids'];x=z['features']
        assert x.shape==(len(ids),19) and np.isfinite(x).all() and np.all((x>=0)&(x<=1));assert len(np.unique(ids))==len(ids)
        assert not seen[ids].any() and np.all(expected[ids]==i);assert np.array_equal(np.sort(ids),np.flatnonzero(expected==i))
        assert np.isin(x[:,18],[0,1]).all() and not np.any(x[x[:,18]==0,:18]);dense[ids]=x;seen[ids]=True
        bindings.append(dict(split=['train','val','test'][i],path=str(p),sha=R.sha(p),nodes=len(ids),covered=int(x[:,18].sum())))
        del x;gc.collect()
    assert np.array_equal(seen,expected>=0);dense.flush();np.save(out/'split_index.npy',expected)
    write(out/'summary.json',dict(time=NOW(),graph_nodes=len(vi),covered_scope_nodes=int(seen.sum()),unlisted_nodes=int((~seen).sum()),shape=list(dense.shape),feature_sha=R.sha(out/'all_splits_real_k4.npy'),split_sha=R.sha(out/'split_index.npy'),sources=bindings,labels_read=False,offline_coordinate_precheck_passed=True,training_started=False,experiment_ready=False,note='Real SAT input only. Fresh within-current-split gate/k/role permutation and training-only preprocessing still required; old diagnostic permutations are not approved.'))
    print('ALL_SPLITS_EXPORTED',out,flush=True)

def state(out,phase,**kw):
    d=dict(time=NOW(),phase=phase,**kw);(out/'state.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(d,ensure_ascii=False),flush=True)

def resources(out,stage,min_disk=10,min_memory=1.75):
    while shutil.disk_usage(ROOT).free/2**30<min_disk or R.memory_available_gib()<min_memory:
        state(out,'waiting_resources',stage=stage,disk_free_gib=shutil.disk_usage(ROOT).free/2**30,memory_available_gib=R.memory_available_gib(),required_disk_gib=min_disk,required_memory_gib=min_memory);time.sleep(60)

def queue(out):
    request=json.loads((out/'request.json').read_text());assert_frozen()
    while True:
        alive=[]
        for p in request['wait_for']:
            try:
                process=psutil.Process(p['pid'])
                if abs(process.create_time()-p['create_time'])<.01:alive.append(p['pid'])
            except psutil.NoSuchProcess:pass
        if not alive:break
        state(out,'waiting_training_extraction_and_audit',pids=alive);time.sleep(30)
    counter=0
    def call(script,args=(),panel=None):
        nonlocal counter
        counter+=1;log=out/f'{counter:03d}_{Path(script).stem}.log';env=os.environ.copy()
        if panel is not None:env['SAT_K4_PANEL']=str(panel)
        with log.open('xb') as f:
            p=subprocess.Popen([str(ROOT/'ginvenv/Scripts/python.exe'),'-B','-X','utf8',str(script),*args],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
            state(out,'running',script=str(script),panel=str(panel),pid=p.pid,log=str(log));rc=p.wait()
        return rc,log,p.pid
    # If the prior training run stopped short, finish it before the held-out jobs.
    pending=[a for a in R.read_plan(R.PANEL/'plan.json')['views'] if not (R.PANEL/'views'/a['view']/'coverage.json').exists()]
    if pending:
        while True:
            resources(out,'resume_training')
            rc,log,pid=call(SCRIPTS/'run_all_k4_alltrain.py',['--run','--workers','1','--max-workers','2','--min-memory-gib','1.25'])
            if rc==0:break
            text=log.read_text(encoding='utf-8',errors='replace')
            if any(s in text for s in ['Insufficient disk/memory','Disk/STOP guard','Stopped at batch boundary']):continue
            raise RuntimeError(f'Training extraction unfinished: {log}')
        rc,log,_=call(SCRIPTS/'finish_fullrun.py',['--pid',str(pid)])
        if rc:raise RuntimeError(f'Training final audit unfinished: {log}')
    if not list((R.PANEL/'full_training_exports').glob('export_*/all_training_k4.npz')):raise RuntimeError('Verified full-training export missing; inspect training completion report')
    for label,panel in PANELS.items():
        resources(out,'prepare_'+label,min_disk=12,min_memory=1.75)
        rc,log,_=call(HERE/'holdout_k4.py',['--prepare',label])
        if rc:raise RuntimeError(f'Preparation failed; retained output: {log}')
        retries=0
        while True:
            resources(out,'extract_'+label,min_disk=10,min_memory=1.5)
            rc,log,_=call(SCRIPTS/'run_all_k4_alltrain.py',['--run','--workers','1','--max-workers','2','--min-memory-gib','1.25','--min-free-gib','8'],panel)
            if rc==0:break
            text=log.read_text(encoding='utf-8',errors='replace')
            if any(s in text for s in ['Insufficient disk/memory','Disk/STOP guard','Stopped at batch boundary']):continue
            if retries>=1:raise RuntimeError(f'Extraction failed twice: {log}')
            retries+=1
        resources(out,'merge_'+label,min_memory=1.5)
        rc,log,_=call(HERE/'holdout_k4.py',['--merge',label])
        if rc:raise RuntimeError(f'Holdout merge audit failed: {log}')
    resources(out,'all_splits_export',min_memory=1.75)
    rc,log,_=call(HERE/'holdout_k4.py',['--export'])
    if rc:raise RuntimeError(f'All-split export failed: {log}')
    state(out,'complete',new_training_runs=0)
    append_note('验证及测试129个视图提取、逐视图核验、分集合合并和全图坐标加载预检已完成。未训练，合格置换和正式训练协议仍待另行准备。',out)

def append_note(text,out):
    note=f'\n\n### SATk4验证与测试补齐任务 {NOW()}\n\n{text}\n证据：{out.relative_to(ROOT)}。\n'
    for name in ['SAT作用证明.md','SAT工作总结.md']:
        with (ROOT/'10.15/00_说明'/name).open('a',encoding='utf-8') as f:f.write(note)

def launch():
    for p in psutil.process_iter(['name','cmdline']):
        cmd=' '.join(p.info['cmdline'] or [])
        if 'python' in (p.info['name'] or '').lower() and 'holdout_k4.py --queue' in cmd:raise RuntimeError('Holdout queue already running')
    assert_frozen();out=R.fresh_dir(HERE/'queue_runs','run');wait=[]
    for pid in [19068,8848]:
        try:p=psutil.Process(pid);wait.append(dict(pid=pid,create_time=p.create_time(),command=p.cmdline()))
        except psutil.NoSuchProcess:pass
    write(out/'request.json',dict(time=NOW(),wait_for=wait,panels={k:str(v) for k,v in PANELS.items()},new_training_runs=0))
    cmd=[str(ROOT/'ginvenv/Scripts/python.exe'),'-B','-X','utf8',str(HERE/'holdout_k4.py'),'--queue',str(out)]
    with (out/'queue.out.log').open('xb') as stdout,(out/'queue.err.log').open('xb') as stderr:
        flags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
        try:p=subprocess.Popen(cmd,cwd=ROOT,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,creationflags=flags|subprocess.CREATE_BREAKAWAY_FROM_JOB)
        except OSError as e:
            if e.winerror!=5:raise
            p=subprocess.Popen(cmd,cwd=ROOT,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,creationflags=flags)
    write(out/'launch.json',dict(time=NOW(),pid=p.pid,command=cmd))
    append_note('已冻结验证65视图和测试64视图的同合同k4全量计划，全部图单元、不读取标签。后台串行队列已启动，等待当前训练提取与自动审计退出后准备输入、提取、核验与导出。保留所有旧证据；磁盘或内存不足时等待，不删除或移动文件。此为已排队任务，尚未完成129视图提取。',out)
    print(json.dumps(dict(out=str(out),pid=p.pid),ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--prepare',choices=list(PANELS));p.add_argument('--merge',choices=list(PANELS));p.add_argument('--export',action='store_true');p.add_argument('--launch',action='store_true');p.add_argument('--queue',type=Path);a=p.parse_args()
    if a.freeze:freeze()
    elif a.prepare:prepare(a.prepare)
    elif a.merge:merge(a.merge)
    elif a.export:full_export()
    elif a.launch:launch()
    elif a.queue:
        try:queue(a.queue)
        except Exception as e:
            state(a.queue,'failed',error=repr(e));append_note('补齐队列未完成，需检查state.json与日志；错误：'+repr(e),a.queue);raise
    else:p.error('Choose a stage')
