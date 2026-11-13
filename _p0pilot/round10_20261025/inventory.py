"""Inventory all 40 existing boundaries and freeze a bounded pairing pilot.

Historical P1 proved rows are candidates only: source-bound fresh checks follow.
No labels, graph risks or SAT calls are used for this selection.
"""
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
TABLES=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'
OUT=TABLES/'sat_pair_round10'
WORK=ROOT/'generate_trans/folds/hosts_bt31'


def key(x):return hashlib.sha256(('r10|'+x).encode()).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rel=pd.concat([pd.read_csv(TABLES/f/f'{r}_nonlocal_relations.csv') for r,f in
        [('r5','sat_nonlocal_round5'),('r6','sat_expand_round6'),('r7','sat_repair_round7')]],ignore_index=True)
    need=defaultdict(set)
    for r in rel.itertuples():
        p=Path(r.design).stem.split('__');need[(p[0],p[1].removesuffix('_d1_s42'),p[-1].removeprefix('ys_'))].update(r.cut_nets.split(';')+[r.target])
    matches=defaultdict(set)
    for d in pd.read_csv(TABLES/'node_pairs_sat_node.csv',chunksize=100000):
        d=d[(d.status=='proved')&(d.inst_a==d.inst_b)]
        for r in d.itertuples():
            for a,b,na,nb in [(r.recipe_a,r.recipe_b,r.net_a,r.net_b),(r.recipe_b,r.recipe_a,r.net_b,r.net_a)]:
                base=(r.host,r.inst_a,str(a));na=str(na).lstrip('\\');nb=str(nb).lstrip('\\')
                if na in need.get(base,()):matches[base+(str(b),na)].add(nb)
    split=json.loads((WORK/'views.json').read_text());cec=pd.read_csv(WORK/'view_manifest_cec.csv').set_index('view_name')
    names_cache={};all_rows=[];candidates=[]
    def names(v):
        if v not in names_cache:
            names_cache[v]={m.group(1).lstrip('\\') for m in re.finditer(r'^\s*(?:wire|input|output)\s+(?:\[[^\]]*\]\s*)?(\\?[^\s;,]+)',(WORK/'trans'/(v+'.v')).read_text(),re.M)}
        return names_cache[v]
    for r in rel.itertuples():
        p=Path(r.design).stem.split('__');host,inst,recipe=p[0],p[1].removesuffix('_d1_s42'),p[-1].removeprefix('ys_')
        nets=r.cut_nets.split(';')+[r.target];options=[]
        for view in split[r.role+'_views']:
            z=view.split('__')
            if z[:2]!=p[:2] or z[-1]==p[-1] or view not in cec.index or cec.loc[view,'cec_status']!='PASS':continue
            source=WORK/'trans'/(view+'.v')
            if not source.exists():continue
            available=names(view);mapped=[];kinds=[];ambiguities=[]
            for net in nets:
                choices=matches.get((host,inst,recipe,z[-1].removeprefix('ys_'),net),set()) & available
                if choices:
                    mapped.append(sorted(choices,key=key)[0]);kinds.append('legacy_P1_candidate');ambiguities.append(len(choices))
                elif net in available:
                    mapped.append(net);kinds.append('same_name_unproved');ambiguities.append(1)
                else:mapped.append(None);kinds.append('missing');ambiguities.append(0)
            options.append(dict(partner=view,mapped_nets=mapped,mapping_origins=kinds,candidate_multiplicity=ambiguities,
                named=sum(x is not None for x in mapped),legacy=sum(x=='legacy_P1_candidate' for x in kinds),
                variant_equal=z[2:-1]==p[2:-1]))
        options.sort(key=lambda o:(-o['named'],-o['legacy'],-o['variant_equal'],key(o['partner'])))
        best=options[0] if options else {}
        row=dict(relation_id=r.relation_id,source_view=Path(r.design).stem,role=r.role,
            source_nets=nets,options=len(options),**best)
        all_rows.append(row)
        if best.get('named')==5 and len(set(best['mapped_nets'][:4]))==4:
            candidates.append(row)
    # Four train/four val with host/design round-robin, then hash. No outcome-based replacement.
    selected=[]
    for role in ['train','val']:
        pool=sorted([x for x in candidates if x['role']==role],key=lambda x:(-x['legacy'],key(x['relation_id'])))
        seen=set()
        for distinct in [True,False]:
            for x in pool:
                if sum(y['role']==role for y in selected)>=4:break
                if x in selected or (distinct and x['source_view'] in seen):continue
                selected.append(x);seen.add(x['source_view'])
    plan=dict(created=datetime.now().astimezone().isoformat(),inventory=all_rows,selected=selected,
        rule='existing P1/name candidates; complete 5-net bindings; four train/four val, distinct source views before repeats; hash ties; no labels',
        budget=dict(sat_subqueries=576,selected_relations=8,proofs_per_pair=6,tables_per_pair=64,reviews=16,timeout_s=5,wall_s=1800),
        prior_P1_rows_are_fresh_proofs=False,training_runs=0)
    plan['plan_sha256']=hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    (OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(all_rows).to_csv(OUT/'pair_inventory_40.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(selected)[['relation_id','partner','legacy']].to_string(index=False),flush=True)
    print('complete candidates',len(candidates),'of',len(rel),flush=True)


if __name__=='__main__':main()
