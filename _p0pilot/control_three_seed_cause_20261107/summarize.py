from pathlib import Path
import collections,csv,hashlib,json,statistics
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def folder(s):return R/('_p0pilot/control_five_cause_20261107' if s==42 else f'_p0pilot/control_five_cause_seed{s}_20261107')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 protected={};sets={};defs=[('AP_decomposition_per_source.csv','AP_source'),('AP_decomposition_macro.csv','AP_macro'),('AP_role_contribution_per_source.csv','AP_role'),('threshold_score_per_source.csv','threshold_source'),('threshold_score_macro.csv','threshold_macro'),('manufacturing_coupling_source_class.csv','coupling')]
 for s in [42,1,2]:
  f=folder(s);assert read(f/'VERIFIED.json')['passed']
  for n,label in defs:
   sets.setdefault(label,[]).extend(dict(seed=s,**r) for r in rows(f/n));protected[str((f/n).relative_to(R))]=sha(f/n)
  protected[str((f/'VERIFIED.json').relative_to(R))]=sha(f/'VERIFIED.json')
 for label,rr in sets.items():table(label+'_all_seeds.csv',rr)
 # Exact sourcecontributions toseed1 macro change;each heldoutsource has equal mass.
 key=[r for r in sets['AP_source'] if r['seed']==1 and r['key']=='trans_test' and r['arm'] in ['GM','GBM']];decomp=[]
 for r in key:
  n=len({x['source'] for x in key if x['arm']==r['arm']});decomp.append(dict(arm=r['arm'],source=r['source'],source_AP_delta=float(r['AP_delta']),macro_AP_contribution=float(r['AP_delta'])/n,positive_score_effect=float(r['positive_score_effect']),negative_score_effect=float(r['negative_score_effect'])))
 table('SEED1_TEST_SOURCE_CONTRIBUTIONS.csv',decomp)
 role_macro=[]
 for seed in [42,1,2]:
  for arm in ['GM','GBM']:
   for key in ['orig_train','orig_val','orig_test','trans_train','trans_val','trans_test']:
    rr=[r for r in sets['AP_role'] if r['seed']==seed and r['arm']==arm and r['key']==key]
    for cl in sorted({r['role_class'] for r in rr}):
     vv=[float(r['AP_contribution_delta']) for r in rr if r['role_class']==cl];role_macro.append(dict(seed=seed,arm=arm,key=key,role_class=cl,AP_contribution_delta=statistics.mean(vv)))
 table('AP_ROLE_MACRO_all_seeds.csv',role_macro)
 for seed in [42,1,2]:
  for arm in ['GM','GBM']:
   for key in ['orig_train','orig_val','orig_test','trans_train','trans_val','trans_test']:
    actual=sum(r['AP_contribution_delta'] for r in role_macro if r['seed']==seed and r['arm']==arm and r['key']==key);expected=float(next(r['AP_delta'] for r in sets['AP_macro'] if r['seed']==seed and r['arm']==arm and r['key']==key));assert abs(actual-expected)<1e-12
 # Frozen node-name lookup for largest actual AP losses;names aid tracing,not newrolelabels.
 f=folder(1);ranks=[r for r in rows(f/'positive_rank_contributions.csv') if r['arm'] in ['GM','GBM'] and r['key']=='trans_test' and any(x in r['source'] for x in ['__injalpha_','__injgamma_'])];ranks=sorted(ranks,key=lambda r:float(r['view_AP_contribution_delta']))[:30];views={(r['key'],r['view']):r for r in rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv')};wanted=collections.defaultdict(list)
 for r in ranks:v=views[r['key'],r['view']];wanted[int(v['old_start'])+int(r['row'])-int(v['start'])].append(r)
 path=R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt';names={}
 with path.open(encoding='utf-8') as f:
  for i,line in enumerate(f):
   if i in wanted:names[i]=line.strip().lstrip('\\')
   if len(names)==len(wanted):break
 assert len(names)==len(wanted);table('SEED1_LARGEST_POSITIVE_RANK_LOSSES.csv',[dict(node_name=names[i],**r) for i,rs in wanted.items() for r in rs]);protected[str(path.relative_to(R))]=sha(path)
 # Recheck all newevidence hashes and oldevidence protected by the independent audits.
 for s in [42,1,2]:
  for p,h in read(folder(s)/'PROTECTED_INPUTS.json').items():assert sha(R/p)==h,p
 for p,h in protected.items():assert sha(R/p)==h,p
 (O/'VERIFIED.json').write_text(json.dumps(dict(passed=True,seeds=[42,1,2],source_role_additivity_checks=36,seed1_source_contributions_verified=True,per_seed_independent_verification=True,protected_inputs=protected,model_forwards=0,autograd=0,training=0,SAT=0,selection_causal_effect_not_identified=True),indent=2),encoding='utf-8');print('THREE_SEED_CACHED_CAUSE_VERIFIED')
if __name__=='__main__':main()
