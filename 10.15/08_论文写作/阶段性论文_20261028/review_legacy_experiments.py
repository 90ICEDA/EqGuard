"""Read-only audit of D:/GIN训练 archives for the staged manuscript."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import numpy as np
from docx import Document

HERE=Path(__file__).resolve().parent
OUT=HERE/'构建与核验/早期实验复核';OUT.mkdir(parents=True,exist_ok=True)
BASE=Path('D:/GIN训练')


def read(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    report=dict(archive=str(BASE),frozen_at=datetime.datetime.now().astimezone().isoformat(),
                errors=[],warnings=[],new_training_runs=0,inputs=[])
    results=BASE/'9.26/GIN_train/results'
    macro=read(results/'ALLFOLDS_groups_macro_amp.csv')
    actual=[];counts=[]
    for row in macro:
        source=results/row['Result_Dir']/'circuit_level_summary.csv'
        rows=read(source)
        selected=[r for r in rows if r['Circuit'] not in ('MACRO_MEAN','MACRO_STD')]
        value=float(np.mean([float(r['AP']) for r in selected]))
        if abs(value-float(row['AP']))>1e-12:report['errors'].append(str(source)+' AP aggregation')
        actual.append(dict(fold=row['Fold'],group=row['Group'],seed=int(row['Seed']),AP=value))
        counts.append(dict(path=str(source),actual_circuits=len(selected),reported_circuits=int(row['N_Circuits'])))
    assert len(macro)==120
    d2=[]
    for group in ('G1_OrigOnly','G2_EqAug','G3_RandCons','G4_PredHard'):
        vals=[r['AP'] for r in actual if r['fold']=='single_to_composed_d2' and r['group']==group]
        assert len(vals)==3
        d2.append(dict(group=group,AP=float(np.mean(vals)),SD=float(np.std(vals,ddof=1)),seeds=[42,43,44]))
    folds=sorted({r['fold'] for r in actual});deltas={}
    for group in ('G2_EqAug','G3_RandCons','G4_PredHard'):
        means=[]
        for fold in folds:
            lookup={(r['seed'],r['group']):r['AP'] for r in actual if r['fold']==fold}
            means.append(float(np.mean([lookup[(s,group)]-lookup[(s,'G1_OrigOnly')] for s in (42,43,44)])))
        deltas[group]=dict(mean_delta=float(np.mean(means)),positive_folds=sum(d>0 for d in means),folds=len(means))
    report['september']=dict(runs=120,folds=len(folds),d2=d2,cross_fold_deltas=deltas,
        aggregation_max_error=max(abs(r['AP']-float(s['AP'])) for r,s in zip(actual,macro)),
        inconsistent_circuit_count=sum(r['actual_circuits']!=r['reported_circuits'] for r in counts))
    if report['september']['inconsistent_circuit_count']:
        report['warnings'].append('Archived N_Circuits includes a macro aggregate row; corrected five-circuit AP equals the stored AP, but circuit counts are not six independent circuits.')
    method=read(BASE/'10.5/results/phase2/loco/loco_summary_ckpt.csv')
    details=read(BASE/'10.5/results/phase2/loco/loco_per_circuit_ckpt.csv')
    for row in method:
        rr=[r for r in details if r['group']==row['group']]
        assert len(rr)==5
        for key in ('AP_T','Recall@5%','FirstHitRank_Norm','AnyMiss@5%','Paired_MAE','Flip_Rate'):
            v=float(np.mean([float(r[key]) for r in rr]))
            if abs(v-float(row[key]))>.000051:report['errors'].append('October5 '+row['group']+' '+key)
    report['october5']=dict(seed=42,heldout_circuits=5,results=method,
        scope='Historical five-circuit LOCO; not current single-host LOCO')
    primrows=read(BASE/'10.13/step4_3seed_compare.csv');raw_results=[]
    for group,stem in [('primitive','rank_pct_g7_prim'),('39d','rank_pct_g5')]:
        for suffix,seed in [('',42),('_s43',43),('_s44',44)]:
            path=BASE/'10.13'/(stem+suffix+'.csv');rows=read(path)
            for mode in ('decomp3','ys_rt','ys_abc'):
                selected=[r for r in rows if r['mode']==mode]
                # The archived summary defines the exact set of positive views.
                view_ap=float(np.mean([float(r['AP']) for r in selected]))
                bpp=float(np.mean([float(r['best_pos_pct']) for r in selected]))
                target=next(r for r in primrows if r['run']==('prim_s'+str(seed) if group=='primitive' else 'g5_s'+str(seed)) and r['mode']==mode)
                if abs(view_ap-float(target['AP']))>.000051 or abs(bpp-float(target['best_pos_pct']))>.000051:
                    report['errors'].append('October13 '+group+' '+str(seed)+' '+mode)
                raw_results.append(dict(group=group,seed=seed,mode=mode,AP=view_ap,bpp=bpp,views=len(selected)))
    aggregate=[]
    for group in ('primitive','39d'):
        for mode in ('decomp3','ys_rt','ys_abc'):
            rows=[r for r in raw_results if r['group']==group and r['mode']==mode]
            aggregate.append(dict(group=group,mode=mode,AP=float(np.mean([r['AP'] for r in rows])),
                SD=float(np.std([r['AP'] for r in rows],ddof=1)),
                best_positive_rank_pct=float(np.mean([r['bpp'] for r in rows])),n=3))
    report['october13']=dict(three_seed_aggregates=aggregate,per_seed=raw_results,
        caveats=['Only rs232 held-out host; used in development',
                 'Feature remapping can also change fixed-column auxiliary losses',
                 'ys_aig has only one recorded positive per view'])
    docs=[]
    for p in sorted(BASE.glob('S-GIN*.docx')):
        d=Document(p);text='\n'.join(x.text for x in d.paragraphs if x.text.strip())
        table_text='\n'.join(' | '.join(c.text for c in row.cells) for t in d.tables for row in t.rows)
        (OUT/(p.stem+'.txt')).write_text(text+'\n\n'+table_text,encoding='utf-8')
        docs.append(dict(path=str(p),sha256=sha(p),paragraphs=len(d.paragraphs),tables=len(d.tables)))
    report['may_june_documents']=docs
    paths=[results/'ALLFOLDS_groups_macro_amp.csv',results/'identity_control_vs_real_transform.csv',
           results/'labelgated_vs_labelfree.csv',BASE/'9.26.md',BASE/'10.5/report/task6_loco_first.md',
           BASE/'10.5/results/phase2/loco/loco_summary_ckpt.csv',BASE/'10.5/results/phase2/loco/loco_per_circuit_ckpt.csv',
           BASE/'10.5/results/phase2/loco/single_to_composed_d2_loco_amp_summary.csv',
           BASE/'10.13/step4_3seed_compare.csv',BASE/'10.13/第四步_四组对比.md',BASE/'10.13/baseline/01_历史数字.md']
    for path in paths:
        report['inputs'].append(dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size))
        if path.suffix=='.csv':
            name=('0926_' if '9.26' in path.parts else '1005_' if '10.5' in path.parts else '1013_')+path.name
            (OUT/name).write_bytes(path.read_bytes())
    (OUT/'历史实验复核.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('inputs','may_june_documents')},ensure_ascii=False))
    if report['errors']:raise SystemExit(1)


if __name__=='__main__':main()
