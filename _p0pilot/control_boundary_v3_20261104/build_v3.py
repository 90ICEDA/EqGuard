"""Independent opt-in v3 39d inputs: only column30 uses actual PO output drivers."""
from pathlib import Path
import json,csv,sys,hashlib,shutil,importlib.util,collections,gc
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/round32_20261029';F=R/'generate_trans/folds/hosts_bt31'
sys.path.insert(0,str(R));sys.path.insert(0,str(O));from independent_net import raw_network
from phase2 import netlist_lib as NL
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
def clone():
 old=R/'phase2/ys/feature_encoding_v2.py';source=old.read_text(encoding='utf-8');changes={
 "CONTRACT='base39_bitwise_alias_boundary_v2_exact2_explicit_assign_nodes'":"CONTRACT='base39_v3_PO_output_driver_only_column30'",
 "'directed_distance_to_PO'":"'directed_distance_to_PO_driver'",
 "drivers=collections.defaultdict(list);cons=collections.defaultdict(list);types=[];pi_flag=[];po_flag=[];ports=[]":"drivers=collections.defaultdict(list);cons=collections.defaultdict(list);types=[];pi_flag=[];po_flag=[];ports=[];po_driver=[]",
 "typ,conn=cells[name];types.append(typ);ports.append(len(lib[typ]['input']));pi_flag.append(any(n in pi for p,n in conn));po_flag.append(any(n in po for p,n in conn))":"typ,conn=cells[name];types.append(typ);ports.append(len(lib[typ]['input']));pi_flag.append(any(n in pi for p,n in conn));po_flag.append(any(n in po for p,n in conn));po_driver.append(any(n in po and p in lib[typ]['output'] for p,n in conn))",
 "PO=np.array(po_flag),edge_index=edge":"PO=np.array(po_flag),PO_driver=np.array(po_driver),edge_index=edge",
 "x[:,30]=distance(pred,np.flatnonzero(g['PO']))":"x[:,30]=distance(pred,np.flatnonzero(g['PO_driver']))"}
 for a,b in changes.items():assert source.count(a)==1,(a,source.count(a));source=source.replace(a,b)
 path=O/'feature_encoding_v3_po.py'
 if path.exists():assert path.read_text(encoding='utf-8')==source
 else:path.write_text(source,encoding='utf-8')
 spec=importlib.util.spec_from_file_location('v3_PO',path);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v,old,path
def fixtures(v):
 folder=O/'boundary_fixtures';folder.mkdir(exist_ok=True);lib={'BUF':{'input':['A'],'output':['Y'],'scalar':True},'INV':{'input':['A'],'output':['Y'],'scalar':True}}
 cases=[
  ('po_consumer','module t(a,y); input a; output y; wire dead; BUF d(.A(a),.Y(y)); INV c(.A(y),.Y(dead)); endmodule',['d','c'],[True,False],[0,-1]),
  ('vector_concat_alias','module t(a,b,y); input a,b; output [1:0] y; wire w0,w1,dead; assign y = {w1,w0}; BUF d0(.A(a),.Y(w0)); BUF d1(.A(b),.Y(w1)); INV c(.A(y[0]),.Y(dead)); endmodule',['d0','d1','c'],[True,True,False],[0,0,-1]),
  ('undriven_output','module t(a,y); input a; output y; wire dead; BUF d(.A(a),.Y(dead)); endmodule',['d'],[False],[-1]),
  ('expression_output','module t(a,b,y); input a,b; output y; wire w,dead; BUF d(.A(a),.Y(w)); assign y = w & b; INV c(.A(y),.Y(dead)); endmodule',['d','c'],[False,False,True],[1,-1,0]),
  ('conditional_output','module t(a,b,s,y); input a,b,s; output y; wire dead; assign y = s ? a : b; INV c(.A(y),.Y(dead)); endmodule',['c'],[False,True],[-1,0])]
 out=[]
 for name,text,names,seeds,dist in cases:
  path=folder/(name+'.v');path.write_text(text,encoding='utf-8');g=v.parse(path,names,lib);d=v.distance(v.adjacency(g['edge_index'],len(g['types']),True),np.flatnonzero(g['PO_driver']));assert g['PO_driver'].tolist()==seeds and d.tolist()==dist,(name,g['PO_driver'],d)
  independent=raw_network(path,{'BUF':{'inputs':['A'],'outputs':['Y']},'INV':{'inputs':['A'],'outputs':['Y']}});nn=names+independent['virtual_names'];assert set(independent['reachable'])=={nn[i] for i in np.flatnonzero(d>=0)}
  out.append(dict(case=name,passed=True,driver_seeds=seeds,distance=dist))
 write(O/'boundary_tests.json',dict(passed=True,cases=out,training=0,SAT=0,forward=0));return out
def main():
 assert (O/'qualification.json').exists(),'finish qualification before building features'
 v,old,producer=clone();fixtures(v);c=read(P/'input_contract.json');lib=v.load_library(F/'verilog_lib.v');rawlib=NL.load_library(F/'verilog_lib.v');norm=np.load(P/'normalization.npz');output={};report=[];inputs={};train_values=[];changed_total=0;viewrecords=[]
 # Reject changed legacy inputs before writing any new training data.
 for key,h in c['files'].items():assert sha(R/key)==h,key
 for key,q in c['shared_inputs'].items():
  folder=O/'inputs'/key;folder.mkdir(parents=True,exist_ok=True);parent=R/q['folder'];oldx=np.load(parent/'x39.npy',mmap_mode='r');edge=np.load(parent/'edge_index.npy',mmap_mode='r');newx=np.lib.format.open_memmap(folder/'x39.npy',mode='w+',dtype=oldx.dtype,shape=oldx.shape);newx[:]=oldx
  namesfile=F/'data/processed/node_names_trans.txt' if key.startswith('trans') else P/'orig_names/node_names_orig.txt';names=namesfile.read_text(encoding='utf-8').splitlines();inputs[str(namesfile.relative_to(R))]=sha(namesfile);changed=0;badreach=0;oldmax=0;newmax=0
  for j,item in enumerate(q['views']):
   source=F/('trans' if key.startswith('trans') else 'orig')/(item['view']+'.v');physical_names=[s.strip().lstrip('\\') for s in names[item['old_start']:item['old_stop']]];loc=O/'view_cache'/key/item['view'];loc.mkdir(parents=True,exist_ok=True)
   mask=(edge[0]>=item['start'])&(edge[0]<item['stop']);ee=np.asarray(edge[:,mask])-item['start'];binding=dict(source_sha=sha(source),producer_sha=sha(producer),names_sha=hashlib.sha256('\n'.join(physical_names).encode()).hexdigest(),edge_sha=hashlib.sha256(ee.tobytes()).hexdigest(),library_sha=sha(F/'verilog_lib.v'))
   if (loc/'DONE.json').exists():
    done=read(loc/'DONE.json');assert done['binding']==binding and done['distance_sha']==sha(loc/'po_distance.npy');d=np.load(loc/'po_distance.npy');seed_count=done['output_driver_seeds'];reused=True
   else:
    g=v.parse(source,physical_names,lib);assert np.array_equal(g['edge_index'],ee),source;assert len(g['types'])==item['stop']-item['start'];assert np.array_equal(g['PO'],oldx[item['start']:item['stop'],28]>0)
    d=v.distance(v.adjacency(ee,len(g['types']),True),np.flatnonzero(g['PO_driver']));seed_count=int(g['PO_driver'].sum())
    # Independent pin/expression graph verifies true output reachability on every view.
    raw=raw_network(source,rawlib);nn=physical_names+raw['virtual_names'];assert len(nn)==len(d) and set(nn)==set(raw['cells']);assert np.array_equal(np.array([n in raw['reachable'] for n in nn]),d>=0),source
    ix={name:i for i,name in enumerate(nn)};re={(ix[u],ix[t]) for u,tt in raw['succ'].items() for t in tt};assert re==set(map(tuple,ee.T)),source
    assert raw['pocells']=={nn[i] for i in np.flatnonzero(d==0)},source
    np.save(loc/'po_distance.npy',d);write(loc/'DONE.json',dict(binding=binding,distance_sha=sha(loc/'po_distance.npy'),output_driver_seeds=seed_count,independent_reach_verified=True));del g,raw;reused=False
   prev=oldx[item['start']:item['stop'],30];assert not ((prev<0)&(d>=0)).any(),('new driver reach cannot extend touch reach',source);diff=int((prev!=d).sum());flips=int(((prev>=0)&(d<0)).sum());changed+=diff;badreach+=flips;oldmax=max(oldmax,int(prev.max()));newmax=max(newmax,int(d.max()));newx[item['start']:item['stop'],30]=d
   viewrecords.append(dict(key=key,view=item['view'],nodes=len(d),driver_seeds=seed_count,changed_column30=diff,old_reachable_new_unreachable=flips,reused_checkpoint=reused));inputs[str(source.relative_to(R))]=binding['source_sha']
   if (j+1)%10==0:print(key,j+1,'/',len(q['views']),'changed',changed,flush=True)
  newx.flush();assert np.array_equal(newx[:,:30],oldx[:,:30]) and np.array_equal(newx[:,31:],oldx[:,31:]);assert np.isfinite(newx).all();assert np.all(newx[:,30]>=-1)
  for name in ['edge_index','edge_roles','y','trusted','physical']:
   dst=folder/(name+'.npy');shutil.copyfile(parent/(name+'.npy'),dst);assert sha(dst)==sha(parent/(name+'.npy'))
  if key.endswith('_train'):
   physical=np.load(parent/'physical.npy');train_values.append(np.array(newx[physical,30],dtype=np.float64))
  report.append(dict(key=key,views=len(q['views']),nodes=len(oldx),changed_column30=changed,old_reachable_new_unreachable=badreach,other38_columns_identical=True,edges_roles_labels_masks_identical=True,old_max_distance=oldmax,new_max_distance=newmax))
  output[key]={**q,'folder':str(folder.relative_to(R))};changed_total+=changed;del names,newx,oldx,edge;gc.collect()
 mean=norm['mean'].copy();std=norm['std'].copy();train=np.concatenate(train_values);mean[30]=train.mean();std[30]=max(train.std(),1e-6);np.savez(O/'normalization.npz',mean=mean,std=std,fit_count=np.int64(len(train)))
 assert np.array_equal(np.delete(mean,30),np.delete(norm['mean'],30)) and np.array_equal(np.delete(std,30),np.delete(norm['std'],30))
 files={str(p.relative_to(R)):sha(p) for q in output.values() for p in (R/q['folder']).glob('*.npy')}
 newcontract={**c,'version':v.CONTRACT,'parent_contract':str((P/'input_contract.json').relative_to(R)),'parent_contract_sha':sha(P/'input_contract.json'),'shared_inputs':output,'columns39':v.COLS,'files':files,'normalization_file':str((O/'normalization.npz').relative_to(R)),'normalization':'Only column30 mean/std refit on same original+trans physical training rows; other38 normalization parameters identical; no validation/test fitting','change_scope':'Only x39 column30; true output-driving pins are seeds; touches_PO column28 unchanged; edges labels masks order unchanged'}
 write(O/'input_contract.json',newcontract)
 for n,aa in [('feature_change_summary.csv',report),('feature_changes_per_view.csv',viewrecords)]:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(aa[0]));w.writeheader();w.writerows(aa)
 write(O/'FEATURES_COMPLETE.json',dict(training=0,SAT=0,model_forward=0,parent_files_unchanged=True,only_column30_changed=True,total_changed_nodes=changed_total,summary=report,train_fit_count=len(train),old_mean30=float(norm['mean'][30]),new_mean30=float(mean[30]),old_std30=float(norm['std'][30]),new_std30=float(std[30]),parent_producer_sha=sha(old),new_producer_sha=sha(producer),inputs=inputs,contract_sha=sha(O/'input_contract.json'),normalization_sha=sha(O/'normalization.npz')))
 print('V3 COMPLETE',changed_total,flush=True)
if __name__=='__main__':main()
