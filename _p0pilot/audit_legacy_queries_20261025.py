"""Audit actual historical logs without assuming every old result is corrupted."""
import re
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/audit_20261025'


def main():
    d=pd.read_csv(ROOT/'_p0pilot/functional_relations_agnostic.csv',encoding='utf-8-sig').fillna('')
    d=d[d.design.str.startswith('rs232t1000__') & d.inst.isin(['injalpha','injepsilon'])]
    rows=[]
    for path,group in d.groupby('log',sort=False):
        log=ROOT/path
        row=dict(log=path,source_rows=len(group),expected_queries=4*len(group),exists=log.exists())
        if log.exists():
            statuses=[]
            with log.open(encoding='utf-8',errors='replace') as f:
                for line in f:
                    if 'Executing SAT pass ' in line or 'Executing SAT pass (' in line:
                        statuses.append('unknown')
                    elif statuses:
                        if 'no model found: SUCCESS' in line:
                            statuses[-1]='proved'
                        elif 'model found: FAIL' in line:
                            statuses[-1]='refuted'
            saved=group[['sat_q1','sat_q2','sat_q3','sat_q4']].to_numpy().reshape(-1).tolist()
            row.update(bytes=log.stat().st_size,logged_queries=len(statuses),
                       unresolved_queries=statuses.count('unknown'),
                       aligned_length=(len(statuses)==len(saved)))
            if len(statuses)==len(saved):
                row['saved_result_mismatches']=sum(a!=b for a,b in zip(statuses,saved))
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT/'legacy_query_alignment.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':
    main()
