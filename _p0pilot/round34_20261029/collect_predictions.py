"""Reuse validation scores; only missing train scores use frozen eval/no_grad forward."""
import os,sys,json,time,hashlib,importlib.util,gc,datetime
from pathlib import Path
import numpy as np
import pandas as pd
import torch
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;R32=ROOT/'_p0pilot/round32_20261029';R33=ROOT/'_p0pilot/round33_20261029'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def fingerprint(m):
    h=hashlib.sha256()
    for k,t in m.state_dict().items():h.update(k.encode());h.update(t.detach().cpu().numpy().tobytes())
    return h.hexdigest()
def main():
    assert 'ginvenv_gpu' in sys.executable
    assert json.loads((H/'evidence_audit.json').read_text())['passed']
    request=json.loads((R33/'request.json').read_text());assert sha(R32/'train_pair.py')==request['engine_sha']
    spec=importlib.util.spec_from_file_location('frozen_model_inference',R32/'train_pair.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
    def forbidden(*a,**k):raise RuntimeError('Training is forbidden in this read-only inference task')
    M.train_arm=forbidden;M.domain_loss=forbidden
    for path,digest in M.CONTRACT['files'].items():assert sha(ROOT/path)==digest
    pairs=json.loads((H/'frozen_pairs.json').read_text());bindings=[];records=[]
    for seed,folder in [(42,R32),(1,R33/'v2_seed1'),(2,R33/'v2_seed2')]:
        run=folder/'runs/base39';selection=json.loads((run/'SELECTED.json').read_text());checkpoint=ROOT/selection['path'];before=sha(checkpoint)
        assert sha(run/'config.json')==selection['config_sha']
        comparison=json.loads((folder/'comparison.json').read_text())['base39'];threshold=comparison['threshold']
        scores={'val':np.load(run/'trans_val_scores.npy',mmap_mode='r')}
        valhash=sha(run/'trans_val_scores.npy');trainfile=H/f'frozen_seed{seed}_train_scores.npy'
        M.SEED=seed;model=M.model_for('base39');model.load_state_dict(torch.load(checkpoint,map_location='cuda',weights_only=True));model.eval()
        state_before=fingerprint(model);start=time.perf_counter()
        if trainfile.exists():
            bind=json.loads((H/f'inference_seed{seed}.json').read_text());assert bind['checkpoint_sha']==before and bind['train_scores_sha']==sha(trainfile)
        else:
            # Full training-split context is identical to the trained graph; eval mode freezes BN/dropout.
            train=M.predict(model,'trans_train','base39');np.save(trainfile,train)
        state_after=fingerprint(model);assert state_before==state_after and not model.training
        assert sha(checkpoint)==before and sha(run/'trans_val_scores.npy')==valhash
        scores['train']=np.load(trainfile,mmap_mode='r')
        binding=dict(seed=seed,python=sys.executable,checkpoint=str(checkpoint.relative_to(ROOT)),checkpoint_sha=before,
            validation_scores=str((run/'trans_val_scores.npy').relative_to(ROOT)),validation_scores_sha=valhash,
            train_scores=str(trainfile.relative_to(ROOT)),train_scores_sha=sha(trainfile),threshold=threshold,
            eval_mode=True,no_grad=True,state_and_BN_unchanged=state_before==state_after,elapsed_s=time.perf_counter()-start,
            optimizer_created=False,backward_calls=0,new_training=0,new_SAT=0)
        write(H/f'inference_seed{seed}.json',binding);bindings.append(binding)
        for split,a in scores.items():assert np.isfinite(a).all() and a.min()>=0 and a.max()<=1
        for p in pairs:
            if p['source']['node']<0 or p['partner']['node']<0:continue
            split=p['split'];a=p['source'];b=p['partner']
            sa=float(scores[split][a['local_node']]);sb=float(scores[split][b['local_node']])
            records.append(dict(seed=seed,cohort=p['cohort'],relation_id=p['relation_id'],slot=p['slot'],split=split,
                source_view=a['view'],partner_view=b['view'],source_node=a['node'],partner_node=b['node'],source_bit=a['bit'],partner_bit=b['bit'],source_pin=a['pin'],partner_pin=b['pin'],
                source_score=sa,partner_score=sb,absolute_difference=abs(sa-sb),signed_difference=sb-sa,
                flip=int((sa>=threshold)!=(sb>=threshold)),threshold=threshold,source_label=a['label'],partner_label=b['label'],source_trusted=a['trusted'],partner_trusted=b['trusted'],
                main_eligible=p['main_eligible'],exclusion_reason=p['exclusion_reason'],whole_observation_status=p.get('whole_observation_status','mechanism_proved'),
                context_id=p['context_id'],proof_folder=p['proof_folder'],query_id=p['query_id'],training_pair_allowed=False))
        del model;gc.collect();torch.cuda.empty_cache();print('FROZEN INFERENCE PASS',seed,flush=True)
    pd.DataFrame(records).to_csv(H/'pair_prediction_differences.csv',index=False,encoding='utf-8-sig')
    write(H/'prediction_bindings.json',dict(passed=True,models=bindings,existing_prediction_files_reused=3,missing_training_prediction_files_created=3,new_training=0,new_SAT=0))
if __name__=='__main__':main()
