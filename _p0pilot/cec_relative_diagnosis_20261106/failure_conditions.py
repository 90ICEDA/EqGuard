"""Same-anchor errors where gate/complexity similarity disagrees with CEC truth."""
from pathlib import Path
import collections,csv,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];OLD=R/'_p0pilot/cec_relative_seed42_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 panels=read(O/'panels.json');primary=read(OLD/'PRIMARY_RESULT.json')['primary_sources'];panels['val_primary']=[t for t in panels['val'] if t['source'] in primary];meta={m['cone_id']:m for m in rows(O/'cone_metadata.csv')};queries=[];summary=[]
 for panel in ['train_used','val_primary']:
  tt=panels[panel];domain='train' if panel=='train_used' else 'val'
  for arm in ['INIT','Z','A_R','A_P','S_R','S_P']:
   path=O/f'{domain}_{arm}_remap9000.npz' if domain=='train' or arm=='INIT' else OLD/f'val_{arm}_remap9000.npz'
   with np.load(path) as f:ids=f['cone_ids'].tolist();ix={c:j for j,c in enumerate(ids)};x=f['concat128'][:,:64].astype(np.float64)
   rr=[]
   for t in tt:
    for qi,(a,r,p) in enumerate([(0,1,3),(2,3,1),(1,0,2),(3,2,0)]):
     aa,real,wrong=[t['cones'][j] for j in [a,r,p]];am,rm,pm=[meta[c] for c in [aa,real,wrong]];dist=lambda c,d:float(np.sqrt(np.mean((x[ix[c]]-x[ix[d]])**2)));dr,dw=dist(aa,real),dist(aa,wrong)
     rg=am['gate']==rm['gate'];pg=am['gate']==pm['gate'];gate='conflict' if not rg and pg else 'favourable' if rg and not pg else 'tied'
     labels={}
     for key in ['members','depth']:
      d1=abs(np.log1p(int(am[key]))-np.log1p(int(rm[key])));d2=abs(np.log1p(int(am[key]))-np.log1p(int(pm[key])));labels[key]='conflict' if d1>d2+1e-12 else 'favourable' if d1<d2-1e-12 else 'tied'
     row=dict(panel=panel,arm=arm,source=t['source'],triple_id=t['triple_id'],query=qi,gate=gate,size=labels['members'],depth=labels['depth'],real_rms=dr,wrong_rms=dw,win=float(dr<dw)+.5*float(dr==dw));rr.append(row);queries.append(row)
   for cue in ['gate','size','depth']:
    for condition in ['conflict','favourable','tied']:
     selected=[r for r in rr if r[cue]==condition]
     if not selected:continue
     counts=collections.Counter(r['source'] for r in selected);wins=[np.mean([r['win'] for r in selected if r['source']==s]) for s in sorted(counts)];summary.append(dict(panel=panel,arm=arm,cue=cue,condition=condition,queries=len(selected),sources=len(counts),source_macro_win=float(np.mean(wins)),pooled_win=float(np.mean([r['win'] for r in selected]))))
 for name,records in [('failure_query_details.csv',queries),('failure_condition_summary.csv',summary)]:
  with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
 print('FAILURE_CONDITIONS_COMPLETE')
if __name__=='__main__':main()
