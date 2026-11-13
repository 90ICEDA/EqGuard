"""Bounded native-context migration and counterpart validation for frozen pairs."""
import itertools
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import native as N

sys.path.insert(0,str(N.ROOT/'_p0pilot/round9_20261025'))
from boundary_repr import COLS,parse_table,summarize,canonical,context_key


def truth(rows):
    d=pd.DataFrame(rows);result={}
    states={('proved','proved'):('infeasible','not_applicable'),('proved','refuted'):('feasible','1'),
            ('refuted','proved'):('feasible','0'),('refuted','refuted'):('feasible','undecided')}
    for pat,g in d.groupby('pattern'):
        s=g.set_index('prove').status.to_dict();result[pat]=states.get((s[1],s[0]),('unknown','unknown'))
    return result


def table_wrapper(code,module,spec):
    return code+f'''\nmodule check(input [{spec['width']-1}:0] env,input [3:0] pattern,output premise,output target);
wire [4:0] p;wire [{len(spec['obs'])-1}:0] obs;
{module} impl(env,p,obs);assign premise=(p[3:0]==pattern);assign target=p[4];endmodule
'''


def main():
    plan=json.loads((N.OUT/'plan.json').read_text());source_rows={}
    for rd,folder in [('r5','sat_nonlocal_round5'),('r6','sat_expand_round6'),('r7','sat_repair_round7')]:
        for r in pd.read_csv(N.OUT.parent/folder/f'{rd}_nonlocal_relations.csv').itertuples():source_rows[r.relation_id]=r
    context=dict(model='native_unrestricted_combinational_physical_Q_v1',constraints={},
        state_pairing='same named physical Q; QN=complement',input_roles='generic_cut_inputs',reachability='not_proved')
    context['context_id']=context_key(context)
    (N.OUT/'aligned_context.json').write_text(json.dumps(context,indent=2),encoding='utf-8')
    outcomes=[];tables=[];review_candidates=[]
    for i,item in enumerate(plan['selected']):
        base=dict(relation_id=item['relation_id'],role=item['role'],source_view=item['source_view'],partner_view=item['partner'],context_id=context['context_id'])
        try:
            a=N.load(item['source_view']);b=N.load(item['partner'])
            ca,sa=N.emit(a,'left_design',item['source_nets']);cb,sb=N.emit(b,'right_design',item['mapped_nets'])
            if (sa['ports'],sa['states'],sa['obs'])!=(sb['ports'],sb['states'],sb['obs']):
                outcomes.append(dict(**base,status='state_or_interface_schema_mismatch',fresh_root_proofs=0));continue
        except (ValueError,KeyError) as e:
            outcomes.append(dict(**base,status='model_or_mapping_error',detail=str(e),fresh_root_proofs=0));continue
        eqcode=ca+'\n'+cb+f'''\nmodule check(input [{sa['width']-1}:0] env,output [4:0] delta,output observation_diff);
wire [4:0] a,b;wire [{len(sa['obs'])-1}:0] oa,ob;
left_design l(env,a,oa);right_design r(env,b,ob);assign delta=a^b;assign observation_diff=|(oa^ob);endmodule
'''
        qs=[dict(pair_index=i,kind='fresh_boundary_equivalence',pattern=str(j),prove=0,args=f'-prove delta[{j}] 0') for j in range(5)]
        qs.append(dict(pair_index=i,kind='fresh_PO_D_equivalence',pattern='all',prove=0,args='-prove observation_diff 0'))
        proofs=N.run(N.OUT/'pairs'/str(i)/'equivalence',eqcode,qs)
        count=sum(q['status']=='proved' for q in proofs[:5])
        for r in proofs[:2]:review_candidates.append(r)
        if count!=5:
            outcomes.append(dict(**base,status='boundary_not_proved',fresh_root_proofs=count,
                rejected=[j for j,q in enumerate(proofs[:5]) if q['status']!='proved'],global_equivalence=proofs[5]['status']));continue
        measured=[]
        for label,code,module,spec in [('source',ca,'left_design',sa),('partner',cb,'right_design',sb)]:
            qs=[dict(pair_index=i,kind='aligned_'+label,pattern=p,prove=v,
                 args=f"-set pattern 4'b{''.join(reversed(p))} -set premise 1 -prove target {v}")
                for p in map(''.join,itertools.product('01',repeat=4)) for v in (1,0)]
            # p[j] belongs to source slot j, while a Verilog vector prints MSB first.
            rr=N.run(N.OUT/'pairs'/str(i)/label,table_wrapper(code,module,spec),qs)
            t=truth(rr);measured.append(t)
            desc,per=summarize(t,4)
            tables.append(dict(pair_index=i,side=label,view=item['source_view'] if label=='source' else item['partner'],
                relation_id=item['relation_id'],context_id=context['context_id'],truth=t,features=desc,inputs=per,
                source_sha=N.sha(N.WORK/'trans'/((item['source_view'] if label=='source' else item['partner'])+'.v'))))
        old=parse_table(source_rows[item['relation_id']].truth_table,4)
        fa=summarize(measured[0],4)[0];fb=summarize(measured[1],4)[0]
        outcome=dict(**base,status='paired_validated' if measured[0]==measured[1] else 'paired_table_mismatch',
            fresh_root_proofs=5,global_equivalence=proofs[5]['status'],old_context_migration_equal=old==measured[0],
            identical_named_order_truth=measured[0]==measured[1],
            feature_max_abs_diff=max(abs(fa[c]-fb[c]) for c in COLS),
            canonical_equal=canonical(measured[0],4)['signature']==canonical(measured[1],4)['signature'])
        outcomes.append(outcome)
        print(json.dumps(outcome,ensure_ascii=False),flush=True)
    # At most 16 independent process checks, including failed candidate proofs.
    reviews=[]
    for i,q in enumerate(review_candidates[:16]):
        folder=N.ROOT/q['folder'];code=(folder/'model.v').read_text()
        row=N.run(N.OUT/'reviews'/str(i),code,[dict(pair_index=q['pair_index'],kind='review',pattern=q['pattern'],prove=q['prove'],
                    args=q['args'],original_status=q['status'])])[0]
        reviews.append(row)
    pd.DataFrame(N.ROWS).to_csv(N.OUT/'queries.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(outcomes).to_csv(N.OUT/'pilot_outcomes.csv',index=False,encoding='utf-8-sig')
    (N.OUT/'aligned_tables.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(frozen_pairs=len(plan['selected']),outcomes=pd.Series([r['status'] for r in outcomes]).value_counts().to_dict(),
        subqueries=len(N.ROWS),budget=576,review_queries=len(reviews),review_agree=sum(r['status']==r['original_status'] for r in reviews),
        training_runs=0,safety_labels_copied=False)
    (N.OUT/'pilot_manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
