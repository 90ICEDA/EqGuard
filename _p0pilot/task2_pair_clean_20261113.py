"""Build the minimal matched clean keep panel and score frozen Task 1 models."""
import itertools
import os
import re
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evaluate_task2_nokeep_20261113 import (
    CAL, CONFIRM, NORM, OUT, P, ROOT, RUN, SEEDS, dump, inspect_log, module, read, sha,
    validation_threshold, write_csv,
)

DEST = OUT / os.environ.get('EQGUARD_CLEAN_PANEL_DIR', 'CLEAN_PAIRED_V2')
HOSTS = ('s38417t100', 's38584t100')
RECIPES = {'abc': 'AND,OR,XOR,XNOR,MUX', 'nand': 'NAND,NOR'}
VALI = ROOT.parent / 'GraphSAINT-train/vali'


def linux(path):
    p = path.resolve().as_posix()
    return f'/mnt/{p[0].lower()}{p[2:]}'


def build(phase):
    b = module('task2_clean_pair_builder', CONFIRM / 'build.py')
    a = sys.modules['audit']
    if phase == 'prepare':
        DEST.mkdir(exist_ok=False)
    jobs, manifests = [], []
    for host in HOSTS:
        src = ROOT / f'generate_trans/hosts_bt2/{host}/base/{host}_clean.v'
        assert sha(src) == sha(ROOT / f'generate_trans/hosts/{host}/base/{host}_clean.v')
        raw, _, outputs = a.endpoints(src)
        assert not re.search(r'\(\*[^*]*\bkeep\b', src.read_text(encoding='utf-8'), re.I)
        historical = ROOT / f'generate_trans/keepab_panel_20_stage2b/logs/{host}__injdelta_d1_s42__keepcur__ys_abc.ys'
        selected = re.findall(r'\bw:([^\s]+)', next(l for l in historical.read_text().splitlines() if l.startswith('setattr')))
        # Use only clean-source nets from the existing delta policy. Inserted-only names have no clean counterpart.
        text = src.read_text(encoding='utf-8')
        nets = [n for n in selected if re.search(r'(?<![\w$])'+re.escape(n)+r'(?![\w$])', text)
                and not n.startswith('Trojan')]
        assert nets and set(nets) <= raw['drivers'].keys() | outputs
        (DEST/'raw'/host).mkdir(parents=True,exist_ok=True)
        for recipe, keep in itertools.product(RECIPES, ('keepcur','keepnone')):
            stem = f'{host}_clean__{keep}'
            view = f'{stem}__ys_{recipe}'
            raw_path = DEST/'raw'/host/f'{view}.v'
            target = DEST/'conv'/host/f'{view}.v'
            script = DEST/f'{view}.ys'
            clear = 'setattr -unset keep w:*'
            checks = ['select -assert-none a:keep']
            if keep == 'keepcur':
                checks += [f'select -assert-count 1 w:{n}' for n in nets]
                checks += ['setattr -set keep 1 ' + ' '.join(f'w:{n}' for n in nets)]
                checks += [f'select -assert-count {len(nets)} a:keep']
            script_text='\n'.join([f'read_verilog -sv {linux(VALI / "verilog_lib.v")}', f'read_verilog -sv {linux(src)}',
                f'hierarchy -top {host}_clean', clear, *checks, f'write_rtlil {linux(DEST / (view+"_preopt.il"))}',
                'proc','opt -full','flatten','techmap','opt -full',f'abc -g {RECIPES[recipe]}','opt_clean',
                f'rename -top {view}',f'write_verilog -noattr {linux(raw_path)}',''])
            if phase=='prepare':
                script.write_text(script_text,encoding='utf-8',newline='\n')
            else:
                assert script.read_text(encoding='utf-8')==script_text
            jobs.append(dict(host=host,recipe=recipe,keep=keep,view=view,source=str(src),target=str(target),
                             keep_nets=nets if keep=='keepcur' else [],policy_reference=str(historical)))
            manifests.append(dict(host=host,kind='clean',stem=stem,recipe=recipe,rc=0,bytes=0,always=0,cells=0,cec='PASS(bypass-gate)',secs=0))
    if phase=='prepare':
        return

    def check_synth(j):
        v=j['view']
        il=(DEST/f'{v}_preopt.il').read_text(encoding='utf-8')
        top=il.split(f'\nmodule \\{j["host"]}_clean\n',1)[1].split('\nend\n',1)[0]
        observed=sorted(re.findall(r'(?m)^  attribute \\keep 1\n(?:  attribute [^\n]+\n)*  wire[^\n]* \\([^\s]+)$',top))
        assert observed == sorted(j['keep_nets']), (v,observed)

    for j in jobs:
        check_synth(j)
    if phase=='convert':
        write_csv(DEST/'synth_manifest.csv',manifests)
        with (DEST/'convert.log').open('xb') as f:
            subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'phase2/ys/assign_to_gates.py'),
                        '--manifest',str(DEST/'synth_manifest.csv'),'--ys-root',str(DEST/'raw'),'--out-root',str(DEST/'conv')],
                           stdout=f,stderr=subprocess.STDOUT,check=True)
        return

    def cec(j):
        v=j['view']; target=Path(j['target']); src=Path(j['source']); log=DEST/f'{v}_cec.log'
        gold, observed, proven=inspect_log(log)
        assert gold==src and observed==target
        j.update(proven=proven,unproven=0,source_sha256=sha(src),target_sha256=sha(target),cec_sha256=sha(log))
        print(v,proven,flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(cec,jobs))
    dump(DEST/'MANIFEST.json',jobs)


def score():
    import numpy as np
    import torch
    b=module('task2_clean_pair_eval',CONFIRM/'build.py')
    a=sys.modules['audit']; s=b.S
    lib=b.V.load_library(s.F/'verilog_lib.v')
    mapping={r['full_gate_name']:r['simplified_gate_type'] for r in read(s.F/'gate_full_to_simplified_mapping.json')}
    order=read(s.F/'gatelookup_recommended.json')['simplified_gate_type_order']
    with np.load(NORM) as norm:
        mean,std=norm['mean'][25:],norm['std'][25:]
    model=module('task2_clean_paired_model',P/'control_best200_20261104/evaluate.py').Model().cuda().eval().requires_grad_(False)
    cal=read(CAL)
    graphs=[]
    for j in read(DEST/'MANIFEST.json'):
        p=Path(j['target']); assert sha(p)==j['target_sha256'] and j['unproven']==0
        raw=a.endpoints(p)[0]; names=[n for n in raw['cells'] if n not in set(raw['virtual_names'])]
        _,parsed,x,_,_=b.graph(p,names,lib,mapping,order)
        x[:,25:]=np.clip((x[:,25:]-mean)/std,-10,10)
        graphs.append((j,len(names),torch.as_tensor(x,device='cuda'),torch.as_tensor(parsed['edge_index'],device='cuda')))
    rows=[]
    for seed,arm,point in itertools.product(SEEDS,('N','NC'),('best','last')):
        suffix='' if seed==42 else f'_s{seed}'
        ckpt=RUN/f'{arm}{suffix}_{point}.pt'
        model.load_state_dict(torch.load(ckpt,map_location='cpu',weights_only=True),strict=True)
        threshold=validation_threshold(seed,arm,point,cal)
        for j,n,x,edges in graphs:
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                logits=model(x,edges).float()
            m=(logits[:,1]-logits[:,0]).cpu().numpy()[:n]; assert np.isfinite(m).all()
            hits=int((m>=threshold).sum()); assert bool(hits)==bool(m.max()>=threshold)
            rows.append(dict(**{k:j[k] for k in ('view','host','recipe','keep')},seed=seed,arm=arm,point=point,
                             physical=n,alarm=int(hits>0),alarm_nodes=hits,alarm_fraction=hits/n,max_margin=float(m.max()),
                             threshold=threshold,checkpoint_sha256=sha(ckpt)))
    assert len(rows)==96
    write_csv(DEST/'ALARMS.csv',rows)
    indexed={(r['host'],r['recipe'],r['keep'],r['seed'],r['arm'],r['point']):r for r in rows}
    assert len(indexed)==len(rows)
    summary=[]
    for host,recipe,arm,point in itertools.product(HOSTS,RECIPES,('N','NC'),('best','last')):
        keep=[indexed[host,recipe,'keepcur',seed,arm,point] for seed in SEEDS]
        none=[indexed[host,recipe,'keepnone',seed,arm,point] for seed in SEEDS]
        deltas=[b['alarm_fraction']-a['alarm_fraction'] for a,b in zip(keep,none)]
        summary.append(dict(host=host,recipe=recipe,arm=arm,point=point,
                            keep_alarms=sum(r['alarm'] for r in keep),none_alarms=sum(r['alarm'] for r in none),
                            alarm_transitions='|'.join(f"{a['alarm']}->{b['alarm']}" for a,b in zip(keep,none)),
                            keep_fraction=statistics.mean(r['alarm_fraction'] for r in keep),
                            none_fraction=statistics.mean(r['alarm_fraction'] for r in none),
                            fraction_delta=statistics.mean(deltas),fraction_delta_sd=statistics.stdev(deltas)))
    write_csv(DEST/'PAIRED_SUMMARY.csv',summary)
    print('alarms',sum(r['alarm'] for r in rows),'/',len(rows),flush=True)


if __name__=='__main__':
    action=sys.argv[1]
    if action=='score':
        score()
    else:
        assert action in ('prepare','convert','verify')
        build(action)
