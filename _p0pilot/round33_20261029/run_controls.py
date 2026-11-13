"""Reuse frozen round32 engine; six new authorized/control fits, zero SAT."""
import os,sys,json,time,shutil,hashlib,importlib.util,gc,datetime
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;PRE=ROOT/'_p0pilot/round32_20261029'
spec=importlib.util.spec_from_file_location('frozen_round32',PRE/'train_pair.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
JOBS=[dict(case='old_features_fixed_v2_seed42',seed=42,contract=H/'fixed_contract.json',norm=H/'old_normalization.npz',arms=['base39']),
      dict(case='old_graph_old_features_seed42',seed=42,contract=H/'old_graph_contract.json',norm=H/'old_normalization.npz',arms=['base39']),
      dict(case='v2_seed1',seed=1,contract=PRE/'input_contract.json',norm=PRE/'normalization.npz',arms=['base39','primitive21']),
      dict(case='v2_seed2',seed=2,contract=PRE/'input_contract.json',norm=PRE/'normalization.npz',arms=['base39','primitive21'])]
def configure(job):
    case=H/job['case'];case.mkdir(exist_ok=True)
    M.H=case;M.SEED=job['seed'];M.CONTRACT=json.loads(job['contract'].read_text());M.NORM=np.load(job['norm'])
    if job['seed']==42 and not (case/'common_init.pt').exists():shutil.copy2(PRE/'common_init.pt',case/'common_init.pt')
    return case
def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    assert json.loads((H/'PREPARED.json').read_text())['passed']
    request=dict(created=datetime.datetime.now().astimezone().isoformat(),engine_sha=M.sha(PRE/'train_pair.py'),
        previous_seed42_comparison_sha=M.sha(PRE/'comparison.json'),jobs=[dict(case=j['case'],seed=j['seed'],arms=j['arms'],contract=str(j['contract'].relative_to(ROOT)),contract_sha=M.sha(j['contract']),normalization_sha=M.sha(j['norm'])) for j in JOBS],
        common=dict(epochs=100,updates=100,lr=.0002,weight_decay=.001,hidden=64,layers=4,amp='BF16',validation_every=5,SAT=False),
        test_policy='No new test evaluation until all six model selections are fixed; historical test already observed, these are controlled confirmations not fresh blind tests.')
    if not (H/'request.json').exists():M.write(H/'request.json',request)
    check=M.loss_check();M.write(H/'loss_check.json',check)
    for job in JOBS:
        case=configure(job)
        for path,digest in M.CONTRACT['files'].items():assert M.sha(ROOT/path)==digest
        M.write(case/'case_contract.json',dict(job=request['jobs'][JOBS.index(job)],engine=request['engine_sha'],graph=M.CONTRACT['graph'],feature_note=M.CONTRACT.get('feature_note','v2/primitive representation control'),normalization=M.CONTRACT['normalization']))
        for arm in job['arms']:
            begin=time.perf_counter();torch.cuda.reset_peak_memory_stats()
            M.train_arm(arm)
            M.write(case/(arm+'_execution.json'),dict(case=job['case'],arm=arm,seed=job['seed'],wall_s=time.perf_counter()-begin,selected=str((case/'runs'/arm/'SELECTED.json').relative_to(ROOT))))
        print('SELECTED',job['case'],flush=True)
    selections={j['case']:{a:json.loads((H/j['case']/'runs'/a/'SELECTED.json').read_text()) for a in j['arms']} for j in JOBS}
    M.write(H/'ALL_SELECTED.json',dict(time=datetime.datetime.now().astimezone().isoformat(),selected=selections))
    results={}
    for job in JOBS:
        case=configure(job)
        if (case/'comparison.json').exists():results[job['case']]=json.loads((case/'comparison.json').read_text());continue
        summary={}
        for arm in job['arms']:
            out=case/'runs'/arm;selected=selections[job['case']][arm];model=M.model_for(arm)
            model.load_state_dict(torch.load(ROOT/selected['path'],map_location='cuda',weights_only=True))
            val=M.predict(model,'trans_val',arm);a=M.arrays('trans_val');neg=val[a['trusted']&(a['y']==0)]
            threshold=float(np.nextafter(np.quantile(neg,.95),np.inf))
            summary[arm]=dict(selected=selected,threshold=threshold)
            for key in ('trans_val','trans_test'):
                scores=val if key=='trans_val' else M.predict(model,key,arm)
                metrics,rows=M.metrics(scores,key,threshold);summary[arm][key]=metrics
                np.save(out/(key+'_scores.npy'),scores);M.save_rows(out/(key+'_per_view.csv'),rows)
            del model;gc.collect();torch.cuda.empty_cache()
        M.write(case/'comparison.json',summary);results[job['case']]=summary
        print('EVALUATED',job['case'],json.dumps(summary),flush=True)
    assert M.sha(PRE/'comparison.json')==request['previous_seed42_comparison_sha']
    results['v2_seed42_reused']=json.loads((PRE/'comparison.json').read_text())
    M.write(H/'comparisons.json',results)
    M.write(H/'TRAINING_COMPLETE.json',dict(time=datetime.datetime.now().astimezone().isoformat(),new_training_runs=6,new_updates=600,reused_seed42_runs=2,SAT_queries=0,comparisons_sha=M.sha(H/'comparisons.json')))
    print('TRAINING_COMPLETE',flush=True)
if __name__=='__main__':main()
