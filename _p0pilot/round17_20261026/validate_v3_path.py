"""Exercise actual v3 rename/keep/seq1/marker path on six combinational cases."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'phase2/ys'))
import sat_functional_relations as P0
import sat_functional_relations_v3 as V3

OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_audit_round17/v3_path'


def main():
    if OUT.exists():
        raise RuntimeError('Choose a fresh evidence directory')
    OUT.mkdir()
    v=OUT/'toy.v'
    v.write_text('''module toy(input S0,input A,input B,
output ymux,output yand,output yor,output yxor,output ynand,output yselector);
assign ymux=S0?B:A; assign yand=S0&A&B; assign yor=S0|A|B;
assign yxor=S0^A^B; assign ynand=~(S0&A&B); assign yselector=S0;
endmodule
''',encoding='utf-8')
    raw=OUT/'raw.json'
    P0.run_yosys(f'read_verilog "{P0.wsl(v)}"\nhierarchy -top toy\nproc\nwrite_json "{P0.wsl(raw)}"\n',OUT/'prepare.log')
    g=P0.load_graph(raw,'toy')
    cases=[dict(kind='mux' if target=='ymux' else 'gate',target=target,
                cut={'S0':'S0','A':'A','B':'B'})
           for target in ('ymux','yand','yor','yxor','ynand','yselector')]
    # The direct-set guard must reject target=selector, even under another name.
    rejected=0
    accepted=[]
    for c in cases:
        try:V3.validate_case_boundary(g,c)
        except ValueError:
            rejected+=1;continue
        accepted.append(c)
    assert rejected==1  # yselector aliases S0, cannot be a useful independent cut.
    script=V3.build_script_v3(v,'toy',accepted,OUT/'sat.json',5,set(g['ports']),8)
    log=P0.run_yosys(script,OUT/'solver.log',timeout=180)
    res=P0.parse_results(log)
    assert len(res)==80
    records=[]
    for i,c in enumerate(accepted):
        row=V3.parse_case(c,res[i*16:(i+1)*16]);assert row['decided']==1
        assert row['influence_changed_i']==('2;2;2' if c['kind']=='mux' else
                                           '4;4;4' if c['target']=='yxor' else '1;1;1')
        records.append(dict(target=c['target'],**row))
    info=dict(actual_sat_queries=80,cases=records,all_passed=True,self_cut_rejected=rejected,
              model_sha=hashlib.sha256(v.read_bytes()).hexdigest(),
              script_sha=hashlib.sha256(script.encode()).hexdigest(),
              log_sha=hashlib.sha256((OUT/'solver.log').read_bytes()).hexdigest())
    (OUT/'validation.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(dict(actual_sat_queries=80,all_passed=True,self_cut_rejected=rejected))


if __name__=='__main__':main()
