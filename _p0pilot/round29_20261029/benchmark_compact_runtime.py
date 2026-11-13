"""Validate smaller diagnostic display without changing proof conditions."""
import sys,json,re
from pathlib import Path
H=Path(__file__).resolve().parent;S=H.parent/'round27_20261027';sys.path.insert(0,str(S));import k4_runtime as R
from k4_fast_support import compact_display
sys.path.insert(0,str(R.ROOT/'phase2/ys'));import sat_functional_relations as P0
def main():
    formal=H/'pruned_model_checks/review_00000';cases=json.loads((formal/'report.json').read_text())['cases'];out=R.fresh_dir(H/'compact_runtime_checks','review');rows=[]
    for case_id in [10,13,16]:
        c=cases[case_id];q=R.PANEL/'views'/c['view']/'queries'/c['view']/c['batch'];paths=([q/'results.json'] if (q/'results.json').exists() else [])+sorted(q.glob('attempt_*/results.json'));p=paths[-1];saved=json.loads(p.read_text());old=(p.parent/'run.ys').read_text(encoding='utf-8')
        compact=compact_display(old)
        reverted=re.sub(r' -show pattern -show premise\[\d+\] -show target\[\d+\](?=\n)','',compact);assert reverted==old
        folder=R.fresh_dir(out,'case');(folder/'model.v').write_bytes((formal/f'case_{case_id:05d}'/'gate.v').read_bytes());actual=compact.replace(P0.wsl(p.parent),P0.wsl(folder))
        text=R.checked_yosys(actual,folder/'run.log',timeout=600);status=R.complete_statuses(text,len(saved['queries']),P0.parse_results);assert status==[q['status'] for q in saved['queries']]
        e=json.loads((folder/'run.execution.json').read_text());rows.append(dict(view=c['view'],batch=c['batch'],queries=len(status),seconds=e['seconds'],log_bytes=(folder/'run.log').stat().st_size,all_statuses_identical=True,proof_options_identical_after_display_removed=True))
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    R.write_new(out/'report.json',dict(cases=rows,all_statuses_identical=True,model_helpers_sha=R.sha(S/'k4_fast_support.py'),original_evidence_modified=False,new_training_runs=0));print('REPORT',out)
if __name__=='__main__':main()
