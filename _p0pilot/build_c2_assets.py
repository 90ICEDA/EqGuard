"""Build C2 fold assets: train graph, val/test subgraphs, node supervision, cones, normalization."""
import json,csv,hashlib
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
PREP=R/'_p0pilot/seed42_supervised_prep_20261109'; B=R/'_p0pilot/control_boundary_v3_20261104'
OUT=R/'_p0pilot/c2_heldout_20261111'; OUT.mkdir(exist_ok=True)
c=json.load(open(B/'input_contract.json',encoding='utf-8'))
g=np.load(FG/'group_B.npz'); gy=g['y']; gtr=g['trusted']; gph=g['physical']; grows=g['rows']; gx=g['x']; ge=g['edge']; loc={r:i for i,r in enumerate(grows.tolist())}
# split arrays
val={n:np.load(B/'inputs/trans_val'/(n+'.npy')) for n in ('y','trusted','physical','x39','edge_index')}
test={n:np.load(B/'inputs/trans_test'/(n+'.npy')) for n in ('y','trusted','physical','x39','edge_index')}
def views(split): return [v for v in c['shared_inputs'][f'trans_{split}']['views'] if 'ctl' not in v['view']]
tv={s:views(s) for s in ('train','val','test')}
def build_sub(x,edge,y,tr,ph,ranges):
    keep=np.zeros(len(y),bool)
    for a,b in ranges: keep[a:b]=True
    idx=np.where(keep)[0]; mp=np.full(len(y),-1,np.int64); mp[idx]=np.arange(len(idx))
    ee=edge[:, (mp[edge[0]]>=0)&(mp[edge[1]]>=0)]
    ee=np.stack([mp[ee[0]],mp[ee[1]]])
    return dict(x=np.asarray(x[idx],np.float32),edge=ee.astype(np.int64),y=np.asarray(y[idx],np.int8),trusted=np.asarray(tr[idx],bool),physical=np.asarray(ph[idx],bool)),idx,mp
for h in ('ys_abc','ys_aig','ys_nand'):
    trv=[v for v in tv['train'] if v['view'].split('__')[-1]!=h]
    vav=[v for v in tv['val'] if v['view'].split('__')[-1]!=h]
    tev=[v for v in tv['test'] if v['view'].split('__')[-1]==h]
    tr_ranges=[(v['start'],v['stop']) for v in trv]
    # train graph from group_B local
    keep=np.zeros(len(grows),bool)
    for a,b in tr_ranges:
        ids=grows[(grows>=a)&(grows<b)]; keep[[loc[int(x)] for x in ids]]=True
    tidx=np.where(keep)[0]; mp=np.full(len(grows),-1,np.int64); mp[tidx]=np.arange(len(tidx))
    ee=ge[:, (mp[ge[0]]>=0)&(mp[ge[1]]>=0)]; ee=np.stack([mp[ee[0]],mp[ee[1]]])
    x=gx[tidx]; y=gy[tidx]; tr=gtr[tidx]; ph=gph[tidx]
    mean=x[:,25:].mean(0); std=x[:,25:].std(0); std=np.where(std<1e-6,1.0,std)
    # cone cache: selected train views, map members to fold local
    pos=[]; neg=[]; noisy=0
    with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['split']!='train' or r['kind']!='D' or int(r['n_phys'])<2: continue
            if r['view'] not in {v['view'] for v in trv}: continue
            mem=[]
            for z in r['phys_rows'].split('|'):
                if not z: continue
                gi=loc.get(int(z))
                if gi is None or mp[gi]<0: continue
                mem.append(int(mp[gi]))
            if len(mem)<2: continue
            mem=np.array(sorted(set(mem)),dtype=np.int64); t=tr[mem]; yy=y[mem]
            if ((yy==1)&t).any():
                if len(mem)>20:
                    rng=np.random.default_rng(len(mem)); mem=np.sort(rng.choice(mem,20,replace=False))
                pos.append(mem)
            else:
                nneg=int(((yy==0)&t).sum())
                if nneg>=1 and nneg/len(mem)>=0.5:
                    neg.append(mem); noisy+=int(((yy==1)&~t).sum())
    # node sup filtered/remapped
    sup=np.load(FG/'sup_B.npz',allow_pickle=True); new=[]; sh=[]
    for ids in sup['idx']:
        ids=np.asarray(ids,dtype=np.int64); ni=mp[ids]; ni=ni[ni>=0]
        new.append(ni.astype(np.int64)); sh.append(hashlib.sha256(ni.tobytes()).hexdigest())
    # save train
    np.savez_compressed(OUT/f'{h}_train.npz',x=x,edge=ee,y=y,trusted=tr,physical=ph,mean=mean,std=std,
        view=np.array([v['view'] for v in trv]),start=np.array([v['start'] for v in trv]),stop=np.array([v['stop'] for v in trv]))
    np.savez_compressed(OUT/f'{h}_sup.npz',idx=np.array(new,dtype=object),stepsha=np.array(sh))
    # cones
    flat=[]; ptr=[0]; lab=[]; vv=[]
    for mem in pos:
        flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(1); vv.append('pos')
    for mem in neg:
        flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(0); vv.append('neg')
    np.savez_compressed(OUT/f'{h}_cones.npz',rows=np.array(flat,np.int64),ptr=np.array(ptr,np.int64),label=np.array(lab,np.int8),view=np.array(vv))
    # val/test subgraphs (use fold normalization later)
    vr=[(v['start'],v['stop']) for v in vav]; trr=[(v['start'],v['stop']) for v in tev]
    vg,vi,vmap=build_sub(val['x39'],val['edge_index'],val['y'],val['trusted'],val['physical'],vr)
    tg,ti,tmap=build_sub(test['x39'],test['edge_index'],test['y'],test['trusted'],test['physical'],trr)
    vstart=np.array([int(vmap[v['start']]) for v in vav]); vstop=np.array([int(vmap[v['stop']-1])+1 for v in vav])
    tstart=np.array([int(tmap[v['start']]) for v in tev]); tstop=np.array([int(tmap[v['stop']-1])+1 for v in tev])
    np.savez_compressed(OUT/f'{h}_val.npz',**vg,mean=mean,std=std,view=np.array([v['view'] for v in vav]),
        start=vstart,stop=vstop)
    np.savez_compressed(OUT/f'{h}_test.npz',**tg,mean=mean,std=std,view=np.array([v['view'] for v in tev]),
        start=tstart,stop=tstop)
    json.dump(dict(h=h,train_views=len(trv),val_views=len(vav),test_views=len(tev),train_nodes=len(x),train_edges=ee.shape[1],
        train_pos=int(((y==1)&tr&ph).sum()),train_neg=int(((y==0)&ph).sum()),pos_cones=len(pos),neg_cones=len(neg),noisy=noisy,
        mean=[float(z) for z in mean],std=[float(z) for z in std],sup_steps=len(new),sup_mean_len=float(np.mean([len(z) for z in new]))),
        open(OUT/f'{h}_build.json','w'),indent=2)
    print(h,'train',len(x),'edges',ee.shape[1],'pos',len(pos),'neg',len(neg),'val',len(vg['y']),'test',len(tg['y']),flush=True)
