"""Three bounded timing pairs; all files new, original evidence untouched."""
import sys,json,time
from pathlib import Path
H=Path(__file__).resolve().parent;S=H.parent/'round27_20261027';sys.path.insert(0,str(S));import k4_runtime as R
sys.path.insert(0,str(R.ROOT/'phase2/ys'));import sat_functional_relations as P0

def main():
    formal=H/'pruned_model_checks/review_00000';r=json.loads((formal/'report.json').read_text());out=R.fresh_dir(H/'runtime_pairs','review');rows=[]
    # Predetermined mid-batches cover ABC/AIG/NAND and contain no label selection.
    for index,case_id in enumerate([10,13,16]):
        c=r['cases'][case_id];case=formal/f'case_{case_id:05d}';q=R.PANEL/'views'/c['view']/'queries'/c['view']/c['batch'];paths=([q/'results.json'] if (q/'results.json').exists() else [])+sorted(q.glob('attempt_*/results.json'));old=paths[-1].parent;saved=json.loads(paths[-1].read_text());script=(old/'run.ys').read_text(encoding='utf-8')
        result=dict(view=c['view'],batch=c['batch'],queries=len(saved['queries']),targets=len(saved['tables']))
        for variant in (['gold','gate'] if index%2==0 else ['gate','gold']):
            folder=R.fresh_dir(out,variant);(folder/'model.v').write_bytes((case/(variant+'.v')).read_bytes());actual=script.replace(P0.wsl(old),P0.wsl(folder));text=R.checked_yosys(actual,folder/'run.log',timeout=600)
            statuses=R.complete_statuses(text,len(saved['queries']),P0.parse_results);assert statuses==[q['status'] for q in saved['queries']]
            e=json.loads((folder/'run.execution.json').read_text());result[variant+'_seconds']=e['seconds'];result[variant+'_log_bytes']=(folder/'run.log').stat().st_size
        result['statuses_identical']=True;rows.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    R.write_new(out/'report.json',dict(pairs=rows,all_statuses_identical=True,timing_only_replayed_batches=2*len(rows),production_queries_recomputed=0,labels_read=False));print('REPORT',out,flush=True)

if __name__=='__main__':main()
