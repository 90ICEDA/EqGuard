"""Read-only rebind existing proofs to current node coordinates. No solver calls."""
import sys,re,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent
TABLES=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables';FOLD=ROOT/'generate_trans/folds/hosts_bt31'
sys.path[:0]=[str(ROOT/'_p0pilot/round10_20261025'),str(ROOT/'_p0pilot/round8_20261025'),str(ROOT/'_p0pilot/round29_20261029')]
import native as N
import case_chain as C8
from readonly_graph_arrays import arrays
def forbidden(*a,**k):raise RuntimeError('No solver execution is permitted in this audit')
N.P0.run_yosys=forbidden
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def module(code,name):
    found=re.findall(r'\bmodule\s+'+re.escape(name)+r'\b.*?endmodule',code,re.S);assert len(found)==1
    return found[0]
def bitref(bit):return f'b{bit}' if isinstance(bit,int) else "1'b"+bit
def proof(row,label='Q'):
    folder=ROOT/row['folder'];model=(folder/'model.v').read_text(encoding='utf-8');script=(folder/'run.ys').read_text(encoding='utf-8');log=(folder/'run.log').read_text(encoding='utf-8')
    assert sha(folder/'model.v')==row['model_sha'] and sha(folder/'run.log')==row['log_sha']
    assert hashlib.sha256(script.encode()).hexdigest()==row['script_sha']
    assert row['status']=='proved' and 'ERROR:' not in log
    sat=[line for line in script.splitlines() if line.startswith('sat ')];i=int(row['query_id'])
    assert sat[i].startswith('sat '+row['args']+' -timeout ')
    key=(f'Q{i:04d}' if label=='Q' else f'QUERY{i:04d}')
    blocks=re.split(r'^'+(r'Q\d{4}' if label=='Q' else r'QUERY\d{4}')+r'\s*$',log,flags=re.M)
    assert len(blocks)>i+1
    block=blocks[i+1];assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block
    return model
def main():
    contract=json.loads((ROOT/'_p0pilot/round32_20261029/input_contract.json').read_text())
    viewmap={v['view']:(split,v) for split in ('train','val','test') for v in contract['shared_inputs']['trans_'+split]['views']}
    coords=pd.read_csv(TABLES/'sat_pair_round15/signal_coordinates.csv');pairs=json.loads((TABLES/'sat_pair_round15/validated_pairs_cumulative_round15.json').read_text())['pairs']
    sig=pd.concat([pd.read_csv(TABLES/f'sat_pair_round{r}/validated_signal_pairs.csv') for r in (10,11)],ignore_index=True)
    queries=pd.concat([pd.read_csv(TABLES/'sat_pair_round10/queries_with_repairs.csv'),pd.read_csv(TABLES/'sat_pair_round11/queries_batch3.csv')],ignore_index=True)
    queries['folder']=queries.folder.astype(str)
    old,_=arrays(FOLD/'data/processed/trans_graph.pt');trust=np.load(FOLD/'data/processed/trust_trans.npy')
    needed=set(int(x) for x in coords.node_index.dropna() if x>=0)
    attach=pd.read_csv(TABLES/'sat_boundary_round9/case_graph_attachments.csv');needed.update(int(x) for x in attach.node_index if x>=0)
    names={}
    with (FOLD/'data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
        for i,line in enumerate(f):
            if i in needed:names[i]=line.strip().lstrip('\\')
            if len(names)==len(needed):break
    raws={};inputs={};proofrows=[];out=[];excluded=[]
    def bind(c):
        view=c['view'];snapshot=ROOT/c['raw_snapshot'];source=FOLD/'trans'/(view+'.v')
        if view not in raws:
            assert sha(source)==c['source_sha'] and sha(snapshot/'raw.json')==c['raw_sha']
            m=next(iter(json.loads((snapshot/'raw.json').read_text())['modules'].values()));raws[view]=m
            inputs[str(source.relative_to(ROOT))]=sha(source);inputs[str((snapshot/'raw.json').relative_to(ROOT))]=sha(snapshot/'raw.json')
        m=raws[view];bits=m['netnames'].get(c['net'],m['ports'].get(c['net'],{}))['bits'];assert bits==[int(c['bit'])]
        if bool(c['valid_index']):
            n=int(c['node_index']);assert names[n]==c['driver_cell']==c['node_name']
            assert m['cells'][c['driver_cell']]['connections'][c['output_pin']]==bits
            split,v=viewmap[view];assert split==c['split'] and v['old_start']<=n<v['old_stop']
            return dict(view=view,node=n,local_node=v['start']+n-v['old_start'],split=split,bit=int(c['bit']),pin=c['output_pin'],cell=c['driver_cell'],driver_type=c['driver_type'],trusted=bool(trust[n]),label=int(old['y'][n]))
        assert bool(c['pi_valid'])
        return dict(view=view,node=-1,split=viewmap[view][0],bit=int(c['bit']),pin='PI',trusted=False,label=None)
    for pair in pairs:
        rid=pair['relation_id'];cp=coords[coords.relation_id==rid]
        assert pair['complete_truth_equal'] and pair['training_pair_allowed'] is False
        for slot in range(5):
            left=cp[(cp.slot==slot)&(cp.side=='source')].iloc[0].to_dict();right=cp[(cp.slot==slot)&(cp.side=='partner')].iloc[0].to_dict();a=bind(left);b=bind(right)
            assert a['split']==b['split']==pair['role']
            refs=sig[(sig.relation_id==rid)&(sig.slot==slot)&(sig.status=='proved')];assert len(refs)
            ref=refs.iloc[0];q=queries[(queries.folder==ref.proof_folder)&(queries.query_id==int(ref.query_id))].iloc[0].to_dict()
            code=proof(q)
            match=re.fullmatch(r'-prove delta\[(\d+)\] 0',q['args'])
            if match:proof_slot=int(match[1])
            else:
                assert q['args']=='-prove mismatch 0'
                match=re.search(r'assign mismatch=a\[(\d+)\]\^b\[\1\];',module(code,'check'));assert match
                proof_slot=int(match[1])
            generated=[]
            for side,co,landing,modname,nets in [('source',left,a,'left_design',pair['source_nets']),('partner',right,b,'right_design',pair['partner_nets'])]:
                m=raws[co['view']];expected,layout=N.emit(m,modname,nets);actual=module(code,modname)
                strip=lambda s:re.sub(r'assign sigs=\{.*?\};','assign sigs=BOUND;',s)
                assert strip(expected)==strip(actual),('Native model differs from raw',rid,slot,side)
                terms=re.search(r'assign sigs=\{(.*?)\};',actual).group(1).split(',')
                assert terms[4-proof_slot]==bitref(landing['bit'])
                generated.append(layout)
            assert generated[0]['ports']==generated[1]['ports'] and generated[0]['states']==generated[1]['states']
            wrapper=module(code,'check')
            assert ('assign delta=a^b;' in wrapper if q['args'].startswith('-prove delta') else f'assign mismatch=a[{proof_slot}]^b[{proof_slot}];' in wrapper)
            identity=(str(ref.proof_folder),int(ref.query_id));proofrows.append(dict(relation_id=rid,slot=slot,folder=identity[0],query_id=identity[1],model_sha=q['model_sha'],script_sha=q['script_sha'],log_sha=q['log_sha'],native_regenerated=True,status='proved'))
            reason=''
            if a['node']<0 or b['node']<0:reason='PI_anchor_has_no_node_prediction'
            elif not (a['trusted'] and b['trusted']):reason='unknown_endpoint_label'
            elif a['label']!=b['label']:reason='independent_labels_disagree'
            elif slot!=4:reason='cut_signal_driver_not_target_object'
            row=dict(cohort='blind_target' if slot==4 else 'blind_boundary',relation_id=rid,slot=slot,split=a['split'],context_id=pair['context_id'],source=a,partner=b,main_eligible=not reason,exclusion_reason=reason,whole_observation_status=pair['fresh_PO_D_equivalence'],proof_folder=identity[0],query_id=identity[1],training_pair_allowed=False)
            out.append(row)
    # Privileged mechanism cases are explicitly kept separate from the blind cohort.
    r8=TABLES/'sat_cases_round8';q8=pd.read_csv(r8/'queries.csv');sources=pd.read_csv(r8/'sources.csv')
    boundary=json.loads((TABLES/'sat_boundary_round9/boundary_records.json').read_text());byview={r['view']:r for r in boundary}
    mapped=pd.read_csv(TABLES/'sat_boundary_round9/proven_boundary_pairs.csv')
    for r in mapped.to_dict('records'):
        arow=attach[(attach.view==r['view_a'])&(attach.role==r['role'])].iloc[0];brow=attach[(attach.view==r['view_b'])&(attach.role==r['role'])].iloc[0]
        aa=[];mods=[]
        for ar in (arow,brow):
            sr=sources[sources.view==ar.view].iloc[0];raw=r8/ar.view/'raw.json'
            assert sha(ROOT/sr.source)==sr.source_sha and sha(raw)==sr.raw_sha
            m=next(iter(json.loads(raw.read_text())['modules'].values()));node=int(ar.node_index);split,v=viewmap[ar.view]
            assert names[node]==ar.driver and m['cells'][ar.driver]['connections'][ar.output_pin]==[int(ar.bit)]
            spec=byview[ar.view];nets=[spec['role_bindings'][k] for k in ('selector','data_A','data_B','target')]+['rec_readyH']
            modname='design_ys_id' if ar.view.endswith('ys_id') else 'design_ys_abc'
            emitted,layout=C8.emit(m,modname,'TrojanA' if r['instance']=='injalpha' else 'TrojanE',probe_names=nets)
            mods.append((emitted,layout,modname));aa.append(dict(view=ar.view,node=node,local_node=v['start']+node-v['old_start'],split=split,bit=int(ar.bit),pin=ar.output_pin,cell=ar.driver,trusted=bool(trust[node]),label=int(old['y'][node])))
            inputs[str(raw.relative_to(ROOT))]=sha(raw);inputs[str(Path(sr.source))]=sr.source_sha
        q=q8[(q8.folder==r['evidence_folder'])&(q8.query_id==int(r['query_id']))].iloc[0].to_dict();code=proof(q,'QUERY')
        for emitted,layout,name in mods:assert module(code,name)==emitted
        assert mods[0][1]['input_offsets']==mods[1][1]['input_offsets'] and mods[0][1]['state_offsets']==mods[1][1]['state_offsets']
        assert "left(env,1'b0,1'b0" in code and "right(env,1'b0,1'b0" in code
        out.append(dict(cohort='privileged_mechanism',relation_id=r['instance']+'|'+r['role'],slot=int(r['query_id']),split=aa[0]['split'],context_id=byview[aa[0]['view']]['context_id'],source=aa[0],partner=aa[1],main_eligible=False,exclusion_reason='privileged_case_not_blind; no automatic cell-role equivalence',proof_folder=r['evidence_folder'],query_id=int(r['query_id']),training_pair_allowed=False))
        proofrows.append(dict(relation_id=r['instance']+'|'+r['role'],slot=int(r['query_id']),folder=r['evidence_folder'],query_id=int(r['query_id']),model_sha=q['model_sha'],script_sha=q['script_sha'],log_sha=q['log_sha'],native_regenerated=True,status='proved'))
    for p in [TABLES/'sat_pair_round15/signal_coordinates.csv',TABLES/'sat_pair_round15/validated_pairs_cumulative_round15.json',TABLES/'sat_boundary_round9/proven_boundary_pairs.csv'] :inputs[str(p.relative_to(ROOT))]=sha(p)
    pd.DataFrame(proofrows).to_csv(H/'proof_bindings.csv',index=False,encoding='utf-8-sig')
    write(H/'frozen_pairs.json',out);write(H/'evidence_audit.json',dict(passed=True,coordinate_records=len(coords),blind_relations=len(pairs),audited_slot_pairs=55,mechanism_pairs=len(mapped),raw_bound_models=True,proof_rows=len(proofrows),unique_proof_queries=len(set((r['folder'],r['query_id']) for r in proofrows)),main_by_split={s:sum(r['main_eligible'] and r['split']==s for r in out) for s in ('train','val','test')},inputs=inputs,new_SAT_queries=0,new_training=0,scope='Signal-output equivalence under shared named unrestricted physical Q and PI; no sequential reachability or hidden/cell embedding equivalence claimed'))
    print('AUDIT PASS',len(out),flush=True)
if __name__=='__main__':main()
