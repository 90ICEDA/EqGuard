
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import csv,json,statistics,hashlib
from pathlib import Path
R=Path(_eqguard_path(''))
O=R/'_p0pilot/midterm_ppt_20261105/achievements'
O.mkdir(parents=True,exist_ok=True)
sources={}
def read(p):
 p=Path(p);sources[str(p)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def stats(v):return {'mean':statistics.mean(v),'sample_sd':statistics.stdev(v),'values':v}
D=Path(r'D:\GIN训练\9.26\GIN_train\results')
allrows=read(D/'ALLFOLDS_groups_macro_amp.csv')
metrics=['AP','Recall@5%','Paired_MAE','Flip_Rate']
verified=[]
for a in allrows:
 raw=read(D/a['Result_Dir']/'circuit_level_summary.csv')
 raw=[q for q in raw if q['Circuit'] not in ('MACRO_MEAN','MACRO_STD')]
 assert len(raw)==5,(a['Result_Dir'],len(raw))
 for m in metrics:
  v=statistics.mean(float(q[m]) for q in raw)
  assert abs(v-float(a[m]))<1e-9,(m,v,a[m])
 verified.append(a)
groups=sorted({a['Group'] for a in verified})
summaries={}
for g in groups:
 rows=[a for a in verified if a['Group']==g and a['Fold']=='single_to_composed_d2']
 assert len(rows)==3
 summaries[g]={m:stats([float(q[m]) for q in rows]) for m in metrics}
folds={}
for fold in sorted({a['Fold'] for a in verified}):
 rows={g:{q['Seed']:q for q in verified if q['Fold']==fold and q['Group']==g} for g in groups}
 folds[fold]={g:stats([float(rows[g][s]['AP'])-float(rows[groups[0]][s]['AP']) for s in rows[g]]) for g in groups[1:]}
identity=read(D/'identity_control_vs_real_transform.csv')
family=read(D/'ALLFOLDS_meanstd_amp.csv')
prim=read(Path(r'D:\GIN训练\10.13\step4_3seed_compare.csv'))
primitive={}
for mode in ['decomp3','ys_rt','ys_abc']:
 primitive[mode]={}
 for arm in ['g5','prim']:
  rows=[a for a in prim if a['mode']==mode and a['run'] in [f'{arm}_s{s}' for s in (42,43,44)]]
  assert len(rows)==3
  primitive[mode][arm]={m:stats([float(q[m]) for q in rows]) for m in ['AP','best_pos_pct','Recall@5%']}
insp=read(Path(r'D:\GIN训练\10.5\results\phase2\task5_viewpolicy\single_to_composed_d2_per_view.csv'))
inspection={}
for arm in sorted({a['model'] for a in insp}):
 rows=[a for a in insp if a['model']==arm]
 assert len(rows)==240
 inspection[arm]={m:statistics.mean(float(q[m]) for q in rows) for m in ['AP_T','Recall@1%','Recall@5%','FirstHitRank_Norm']}
formal=read(R/'10.15/03_特征与模型/N2_双分支复核/tables/t13_per_seed.csv')
formal_stats={}
for model in sorted({a['model'] for a in formal}):
 rows=[a for a in formal if a['model']==model]
 formal_stats[model]={m:stats([float(q[m]) for q in rows]) for m in ['view_ap','view_auc','r5','dff_view_ap','po_cone_view_ap']}
stage4=read(R/'10.12/results/stage4_3seed.csv')
training={c:stats([float(a['AP_T']) for a in stage4 if a['配置']==c]) for c in sorted({a['配置'] for a in stage4})}
data={'raw_historical_runs_verified':len(verified),'actual_circuits_per_run':5,'d2':summaries,'fold_gains':folds,'family':family,'identity':identity,'primitive':primitive,'inspection':inspection,'formal':formal_stats,'training':training,'sources':sources}
(O/'EVIDENCE_AUDIT.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
brief={
 'runs_verified':len(verified),'folds':len(folds),
 'positive_fold_counts':{g:sum(v[g]['mean']>0 for v in folds.values()) for g in groups[1:]},
 'd2':{g:{m:round(v[m]['mean'],6) for m in metrics} for g,v in summaries.items()},
 'primitive_rt':primitive['ys_rt'], 'inspection':inspection,
 'region_ap_gain_positive_seeds':sum(float(a['view_ap'])>float(next(q['view_ap'] for q in formal if q['model']=='A3 +cone5 (base)' and q['seed']==a['seed'])) for a in formal if a['model']=='A5 +region l10')}
print(json.dumps(brief,ensure_ascii=False,indent=2))
