"""Whole normal-control B/M/U and Trojan-view host pools, frozen labels only. No model/SAT."""
from pathlib import Path
import json,csv,hashlib,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;V=R/'_p0pilot/control_boundary_v3_20261104';P=R/'_p0pilot/round32_20261029';F=R/'generate_trans/folds/hosts_bt31'
HOST,MNEW,OTHER,POS,FOREIGN,UNKNOWN=1,2,4,8,16,32
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return s.strip().lstrip('\\')
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 O.mkdir(exist_ok=True);c=read(V/'input_contract.json');keys=['orig_train','orig_val','trans_train','trans_val'];meta={x['view']:x for x in rows(F/'views_meta.csv')};names={'orig':[norm(n) for n in (P/'orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines()],'trans':[norm(n) for n in (F/'data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()]};data={};views=[];sourcekind={}
 for key in keys:
  d=R/c['shared_inputs'][key]['folder'];data[key]={n:np.load(d/(n+'.npy'),mmap_mode='r') for n in ['x39','y','trusted','physical']}
  for j,v in enumerate(c['shared_inputs'][key]['views']):
   src=v['view'] if key.startswith('orig') else meta[v['view']]['src_view'];kind=meta[v['view']]['kind'] if key.startswith('trans') else next(x['kind'] for x in meta.values() if x['src_view']==src);sourcekind[src]=kind;views.append(dict(key=key,view_id=j,view=v['view'],source=src,host=src.split('__')[0],recipe='orig' if key.startswith('orig') else meta[v['view']]['op'],kind=kind,**{k:v[k] for k in ['start','stop','physical_stop','old_start','old_stop']}))
 prov=collections.defaultdict(list)
 for p in (R/'generate_trans').glob('hosts*/*/provenance.json'):
  try:
   a=read(p)
   if isinstance(a,list):
    for x in a:
     if x.get('view'):prov[x['view']].append((p,x))
  except (OSError,ValueError):pass
 srcinfo={};oflag=np.full(len(names['orig']),UNKNOWN,np.uint8);osrc=np.full(len(names['orig']),-1,np.int16);srcids={s:i for i,s in enumerate(sorted(sourcekind))};binding={}
 for v in views:
  if not v['key'].startswith('orig'):continue
  ns=names['orig'][v['old_start']:v['old_stop']];nsset=set(ns);candidates=[(p,x) for p,x in prov[v['source']] if x.get('new_gates') and {norm(n) for n in x['new_gates']}<=nsset];assert candidates,v['source'];assert len({tuple(sorted(x['new_gates'])) for p,x in candidates})==1
  pp,pd=candidates[0];new={norm(n) for n in pd['new_gates']};is_m=pd.get('kind')=='control' and pd.get('ctl_type') in ['matched','deep_xor'];srcinfo[v['source']]=dict(new=new,is_M=is_m,prefix=pd['prefix'],ctl_type=pd.get('ctl_type'),source_id=srcids[v['source']]);a=data[v['key']];tags=np.array([MNEW if (is_m or v['kind']=='trojan') and n in new else OTHER if n in new else HOST for n in ns],np.uint8);tags[a['y'][v['start']:v['physical_stop']]==1]|=POS;oflag[v['old_start']:v['old_stop']]=tags;osrc[v['old_start']:v['old_stop']]=srcids[v['source']];binding[str(pp.relative_to(R))]=sha(pp)
 expected=np.full(len(names['trans']),-1,np.int16)
 for v in views:
  if v['key'].startswith('trans'):expected[v['old_start']:v['old_stop']]=srcids[v['source']]
 flags=np.zeros(len(names['trans']),np.uint8);parent_count=np.zeros(len(names['trans']),np.uint16);alignment=read(F/'data/for_train/alignment.json')
 for oi,ti in alignment:
  if expected[ti]<0:continue
  flags[ti]|=oflag[oi];parent_count[ti]+=1
  if osrc[oi]!=expected[ti]:flags[ti]|=FOREIGN
 del alignment
 retention={x['view']:x for x in rows(R/'_p0pilot/control_retention_20261104/per_view.csv') if x['split'] in ['train','val']};summary=[];source_rows=[];normal_parts=collections.defaultdict(list);exclusions=collections.defaultdict(list);hpools=collections.defaultdict(list)
 for v in views:
  key=v['key'];dm,sp=key.split('_');a=data[key];ids=np.arange(v['start'],v['physical_stop'],dtype=np.int64);gids=np.arange(v['old_start'],v['old_stop'],dtype=np.int64);ns=names[dm][v['old_start']:v['old_stop']];si=srcinfo[v['source']];new=si['new'];complete=True;header=True;clean=False;traced=len(new)
  if dm=='orig':tag=oflag[gids].copy();parents=np.ones(len(ids),np.uint16)
  else:
   tag=flags[gids].copy();parents=parent_count[gids];mpath=F/'mappings'/(v['view']+'.json');mp=read(mpath);header=mp.get('src_view')==v['source'] and mp.get('rw_view')==v['view'];lookup={n:i for i,n in enumerate(ns)};traced=0
   if header:
    for s in new:
     tt={norm(t) for t in mp.get('node_alignment',{}).get(s,[]) if norm(t) in lookup}
     if s in lookup:tt.add(s)
     traced+=bool(tt)
     for t in tt:tag[lookup[t]]|=MNEW if si['is_M'] or v['kind']=='trojan' else OTHER
   complete=header and traced==len(new);old=retention.get(v['view'])
   if old:
    assert sha(F/'trans'/(v['view']+'.v'))==old['target_sha'] and sha(F/'orig'/(v['source']+'.v'))==old['source_sha'];clean=old['elimination_confirmed']=='True'
   binding[str(mpath.relative_to(R))]=sha(mpath)
  trusted=a['trusted'][ids];neg=a['y'][ids]==0;reason=np.zeros(len(ids),np.int16)
  if v['kind']=='control':
   assert not (trusted&~neg).any(),('unexpected control positive',v['view']);valid=trusted&neg;assert (parents[valid]>0).all();cat=np.full(len(ids),-1,np.int8)
   host=(tag==HOST)&(parents>0);mm=(tag==MNEW)&(parents>0)
   cat[valid]=2;reason[valid]=8
   cat[valid&mm]=1;reason[valid&mm]=3 if dm=='orig' else 4
   if dm=='orig' or complete or clean:cat[valid&host]=0;reason[valid&host]=1 if dm=='orig' else 2
   else:reason[valid&host]=7
   reason[valid&((tag&OTHER)>0)]=5;reason[valid&((tag&HOST)>0)&((tag&(MNEW|OTHER))>0)]=6;reason[valid&((tag&(FOREIGN|UNKNOWN|POS))>0)]=9
   reason[~trusted]=10
   normal_parts[key].append(dict(rows=ids[valid],category=cat[valid],reason=reason[valid],view_id=np.full(valid.sum(),v['view_id'],np.int16),gate=np.argmax(a['x39'][ids[valid],:25],axis=1).astype(np.int8)))
   exclusions[key].append(dict(rows=ids[~valid],reason=reason[~valid],view_id=np.full((~valid).sum(),v['view_id'],np.int16)))
   summary.append(dict(**v,physical_nodes=len(ids),trusted_negative=int(valid.sum()),B=int((cat==0).sum()),M=int((cat==1).sum()),U=int((cat==2).sum()),excluded_untrusted=int((~valid).sum()),source_added=len(new),traced_added=traced,complete_new_trace=complete,clean_equivalent_structure=clean,header_valid=header))
  elif sp=='train':
   valid=trusted&neg;pure=(tag==HOST)&(parents>0);strict=valid&pure&(complete or dm=='orig');rr=np.where(~pure,11,12).astype(np.int16);rr[strict]=0
   hpools[key].append(dict(rows=ids[valid],eligible=strict[valid],reason=rr[valid],view_id=np.full(valid.sum(),v['view_id'],np.int16),gate=np.argmax(a['x39'][ids[valid],:25],axis=1).astype(np.int8)))
   source_rows.append(dict(**v,all_trusted_negative=int(valid.sum()),pure_host_negative=int((valid&pure).sum()),strict_host_background=int(strict.sum()),held_non_host_or_mixed=int((valid&~pure).sum()),held_incomplete_T_trace=int((valid&pure&~strict).sum()),source_added=len(new),traced_added=traced,complete_new_trace=complete))
  if dm=='trans' and v['view_id']%30==0:print(key,v['view_id'],v['kind'],flush=True)
 for key,parts in normal_parts.items():
  np.savez_compressed(O/('normal_'+key+'.npz'),**{n:np.concatenate([p[n] for p in parts]) for n in ['rows','category','reason','view_id','gate']});aa=exclusions[key];np.savez_compressed(O/('normal_excluded_'+key+'.npz'),**{n:np.concatenate([p[n] for p in aa]) for n in ['rows','reason','view_id']})
 for key,parts in hpools.items():np.savez_compressed(O/('trojan_host_'+key+'.npz'),**{n:np.concatenate([p[n] for p in parts]) for n in ['rows','eligible','reason','view_id','gate']})
 dump('candidate_views.csv',summary);dump('trojan_background_views.csv',source_rows);dump('view_dictionary.csv',views)
 summ=[]
 for key,parts in normal_parts.items():
  aa=np.load(O/('normal_'+key+'.npz'));vv=[x for x in summary if x['key']==key];summ.append(dict(key=key,views=len(vv),sources=len({x['source'] for x in vv}),physical=sum(x['physical_nodes'] for x in vv),trusted_negative=len(aa['rows']),B=int((aa['category']==0).sum()),M=int((aa['category']==1).sum()),U=int((aa['category']==2).sum()),excluded_untrusted=sum(x['excluded_untrusted'] for x in vv)))
 dump('partition_summary.csv',summ)
 for p in [V/'input_contract.json',R/'_p0pilot/control_retention_20261104/per_view.csv',F/'data/for_train/alignment.json',P/'orig_names/node_names_orig.txt',F/'data/processed/node_names_trans.txt',F/'views_meta.csv',Path(__file__)]:binding[str(p.relative_to(R))]=sha(p)
 (O/'PARTITION_COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,labels_modified=False,normal_data_splits=['train','val'],test_positive_nodes_used=False,category=dict(B='pure host lineage plus complete added trace or confirmed clean equality',M='pure traced added matched/deep_xor region; no Trojan partner required',U='other added including dup, mixed lineage, incomplete view trace or unresolved partition; existing trusted negatives only'),H='trusted negative in Trojan training view, pure host lineage and complete Trojan added trace',reason_codes={1:'orig_host',2:'confirmed_trans_host',3:'orig_added_M',4:'trans_pure_added_M',5:'other_added_region',6:'mixed_added_host',7:'host_lineage_but_incomplete_added_trace',8:'unresolved_partition',9:'foreign_unknown_positive_parent',10:'outside_fixed_trusted_mask',11:'H_not_pure_host',12:'H_Trojan_added_trace_incomplete'},summary=summ,inputs=binding),ensure_ascii=False,indent=2),encoding='utf-8');print(summ)
if __name__=='__main__':main()
