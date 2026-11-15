"""Add the frozen task-one D loss to the exact historical H runner."""
import hashlib
import importlib.util
import sys
import types
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
ROOT = P.parent
BASE = P / 'version_baseline_multiseed_20261104'
V3 = P / 'control_boundary_v3_20261104'
CL = P / 'seed42_nc_ablation_20261109/cone_loss.py'
EXPECTED = {42: .2696, 1: .3035, 2: .3214}


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name,path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def predecessor(seed):
    return P / 'version_baseline_seed42_20261104' if seed == 42 else BASE


def engine(seed, cone):
    path = predecessor(seed) / 'frozen_engine_v3.py'
    mod = types.ModuleType('legacy_h_frozen')
    mod.__file__ = str(path)
    source = path.read_text(encoding='utf-8')
    if cone:
        changes = {
            "out=O/f'seed{seed}'/arm": "out=DEST/f'seed{seed}'/arm",
            "loss=T.domain_loss(logits,d['y'],ids);assert torch.isfinite(loss)":
                "loss=T.domain_loss(logits,d['y'],ids)\n"
                "    if dm=='trans':loss=loss+CONE.cone_loss(logits,CONES)\n"
                "    assert torch.isfinite(loss)",
            "loss='unchanged ASL +1.4 softmiss squared'":
                "loss='ASL +1.4 softmiss squared plus task-one D-cone BCE on trans'",
            "runner_sha=sha(Path(__file__))":
                "runner_sha=sha(Path(__file__)),addition_sha=sha(DRIVER),cone_sha=sha(Path(CONE.__file__)),cone_rows_sha=CONES['sha']",
        }
        for old,new in changes.items():
            assert source.count(old)==1, old
            source = source.replace(old,new)
        mod.DEST,mod.DRIVER = OUT,Path(__file__)
    exec(compile(source,str(path),'exec'),mod.__dict__)
    return mod


def configure(seed, cone):
    import json
    import numpy as np
    old = predecessor(seed)
    mod = engine(seed,cone)
    assert 'ginvenv_gpu' in sys.executable and mod.torch.cuda.is_available()
    mod.torch.set_num_threads(2)
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    prior = old/f'seed{seed}/H'
    cfg, binding, result = (read(prior/name) for name in ('config.json','binding.json','EVALUATED.json'))
    for file,key in [(old/'frozen_engine_v3.py','runner_sha'),(old/'manifest.json','manifest_sha'),
        (V3/'input_contract.json','feature_contract_sha'),(V3/'normalization.npz','normalization_sha'),
        (P/'control_best200_20261104/evaluate.py','model_source_sha'),
        (P/'p2b_main_20261031/train_ab.py','loader_sha'),(ROOT/'train_test2.2.py','loss_source_sha')]:
        assert sha(file)==binding[key], file
    assert cfg['updates']==200 and cfg['init_sha']==result['init_sha']==sha(old/f'init_s{seed}.pt')
    assert result['checkpoint_sha']==sha(prior/'best.pt')
    assert abs(result['test']['val_recall80']['trusted']['ap']-EXPECTED[seed])<.00006
    for split,h in result['prediction_sha'].items():
        assert sha(prior/f'{split}_scores.npy')==h
    manifest = read(old/'manifest.json')
    for name,h in manifest['files'].items():
        assert sha(old/name)==h
    assert mod.T.MASK_MODE=='old' and mod.T.ENCODING=='39' and not mod.T.EXTRA and mod.T.EQ==0
    mod.T.CONTRACT=read(V3/'input_contract.json')
    mod.T.NORM=np.load(V3/'normalization.npz')
    if not cone:
        return mod,manifest
    for name,h in mod.T.CONTRACT['files'].items():
        assert sha(ROOT/name)==h
    mod.CONE=load_module(CL,'task_one_d_loss')
    data=mod.T.arrays('trans','train')
    cones=mod.CONE.load_cones('train','D',trust=data['trusted'])
    mod.CONES=mod.CONE.cone_tensors(cones)
    assert (len(cones),mod.CONES['pos'],mod.CONES['neg'],mod.CONES['members'])==(11834,891,10943,202206)
    assert data['physical'][mod.CONES['flat']].all()
    population={}
    for dm in ('orig','trans'):
        d=mod.T.arrays(dm,'train')
        base=np.flatnonzero(np.load(old/f'{dm}_base_mask.npy'))
        slots=np.load(old/f'{dm}_H_slots.npy')
        assert slots.shape==(200,320)
        assert (d['physical'][slots]&d['trusted'][slots]&(d['y'][slots]==0)).all()
        assert (d['physical'][base]&d['trusted'][base]).all()
        assert (d['y'][base]==0).sum()==manifest['counts'][dm]['base_negative']
        assert (d['y'][base]==1).sum()==manifest['counts'][dm]['base_positive']
        population[dm]=dict(base_positive=int((d['y'][base]==1).sum()),base_negative=int((d['y'][base]==0).sum()),
                            slots_per_step=320, mask_sha=sha(old/f'{dm}_base_mask.npy'),
                            slots_sha=sha(old/f'{dm}_H_slots.npy'))
    mod.write(OUT/f'PREFLIGHT_S{seed}.json',dict(seed=seed,population=population,baseline=binding,
        preexisting_H_AP=result['test']['val_recall80']['trusted']['ap'],init_sha=result['init_sha'],
        train_cone_cache_sha=sha(mod.CONE.OUT/'CONE_CACHE_V2.csv'),members_sha=mod.CONES['sha'],
        cone_loss=dict(kind='D',domain='trans',weight=1,pos_weight=10)))
    return mod,manifest


if __name__=='__main__':
    for seed in map(int,sys.argv[1:] or [42,1,2]):
        mod,manifest=configure(seed,cone=True)
        print('VERIFIED',seed,flush=True)
        mod.train(seed,'H',manifest)
