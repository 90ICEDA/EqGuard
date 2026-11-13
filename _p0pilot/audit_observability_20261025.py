"""SAT downstream sensitization audit using two copies and a target intervention.

Both copies share all primary inputs and exposed register state. Only target
is forced to opposite values. Outputs are original PO bits + physical D pins.
This is a combinational fault-propagation witness, NOT reset reachability and
NOT evidence that both intervention values are naturally jointly realizable.
Legacy cell model (including reset approximation) is retained and declared.
"""
from __future__ import annotations
import copy
import json
import re
import sys
import time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phase2/ys'))
import sat_functional_relations as P0
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/audit_20261025'
LOG=ROOT/'_p0pilot/audit_20261025_logs/observability'


def esc(name):
    return '\\'+name+' '


def main():
    LOG.mkdir(parents=True,exist_ok=True)
    relations=pd.read_csv(OUT/'two_case_relations.csv',encoding='utf-8-sig')
    rows=[]
    for view,group in relations.groupby('view',sort=False):
        v=ROOT/f'generate_trans/folds/hosts_bt31/trans/{view}.v'
        top=P0.module_name(v)
        base=LOG/f'{view}.statefree_v3.json'
        raw=LOG/f'{view}.raw.json'
        if not base.exists():
            # Keep all original wires, including every physical D/Q endpoint.
            # Otherwise opt may discard an unobserved FF and replace its old D
            # alias by X; comparing that X would not prove signal propagation.
            keep='w:*'
            script=(f'read_verilog "{P0.wsl(v)}"\nhierarchy -top {top}\nflatten\nproc\n'
                    f'write_json "{P0.wsl(raw)}"\nsetattr -set keep 1 {keep}\n'
                    f'techmap -autoproc -map {P0.CELL_MAP}\nopt -fast\nwrite_json "{P0.wsl(base)}"\n')
            log=P0.run_yosys(script,base.with_suffix('.log'))
            if 'ERROR:' in log:
                raise RuntimeError(str(base))
        data=json.loads(base.read_text(encoding='utf-8'))
        template=data['modules'][top]
        # expose does not handle every optimized $sdff variant. Abstract any
        # remaining register Q explicitly; both copies share this same input.
        for ci,(cn,cell) in enumerate(list(template['cells'].items())):
            typ=cell['type'].lower()
            if 'latch' in typ:
                raise RuntimeError('latch semantics require a separate protocol')
            if 'dff' in typ:
                outputs=[p for p,d in cell.get('port_directions',{}).items() if d=='output']
                assert outputs==['Q'], f'unsupported state ports {outputs}'
                pname=f'audit_state_{ci}'
                qbits=cell['connections']['Q']
                template['ports'][pname]=dict(direction='input',bits=qbits)
                template['netnames'][pname]=dict(hide_name=0,bits=qbits,attributes={})
                del template['cells'][cn]
        assert not any('dff' in c['type'].lower() or 'latch' in c['type'].lower() for c in template['cells'].values()), 'unexposed state'
        rawmod=json.loads(raw.read_text(encoding='utf-8'))['modules'][top]
        # Map physical D pins using stable aliases, never assume bit IDs survive techmap.
        aliases={}
        for name,info in rawmod['netnames'].items():
            for bit in info['bits']:
                if isinstance(bit,int):
                    aliases.setdefault(bit,[]).append(name)
        obs=[]
        for name,p in rawmod['ports'].items():
            if p['direction']=='output':
                obs.extend(template['ports'][name]['bits'])
        for cell in rawmod['cells'].values():
            if 'DFF' in cell['type'].upper() or 'LATCH' in cell['type'].upper():
                for bit in cell['connections'].get('D',[]):
                    for alias in aliases.get(bit,[]):
                        if alias in template['netnames']:
                            obs.extend(template['netnames'][alias]['bits'])
                            break
        obs=list(dict.fromkeys(obs))
        for _,r in group.iterrows():
            t0=time.perf_counter()
            mod=copy.deepcopy(template)
            bits=mod['netnames'].get(r.target,{}).get('bits',[])
            key=f'{view}_{len(rows):02d}'
            if len(bits)!=1 or not isinstance(bits[0],int):
                rows.append(dict(view=view,target=r.target,kind=r.kind,status='constant_target' if bits and all(b in ('0','1') for b in bits) else 'unsupported_target_width'))
                continue
            target=bits[0]
            inputs={n:p for n,p in mod['ports'].items() if p['direction']=='input'}
            if any(target in p['bits'] for p in inputs.values()):
                rows.append(dict(view=view,target=r.target,status='target_is_environment_input'))
                continue
            maxbit=max(b for n in mod['netnames'].values() for b in n['bits'] if isinstance(b,int))
            removed=0
            for cell in mod['cells'].values():
                for pin,bs in cell['connections'].items():
                    if cell.get('port_directions',{}).get(pin)=='output':
                        for j,b in enumerate(bs):
                            if b==target:
                                maxbit+=1
                                bs[j]=maxbit
                                removed+=1
            if removed!=1:
                rows.append(dict(view=view,target=r.target,status=f'driver_count_{removed}'))
                continue
            mod['ports']=dict(inputs)
            mod['ports']['audit_inject']=dict(direction='input',bits=[target])
            mod['ports']['audit_obs']=dict(direction='output',bits=obs)
            mod['attributes'].pop('top',None)
            model=LOG/f'{key}.model.json'
            model.write_text(json.dumps(dict(modules={'audit_design':mod})),encoding='utf-8')
            width=sum(len(p['bits']) for p in inputs.values())
            connections=[]
            off=0
            for name,p in inputs.items():
                k=len(p['bits'])
                connections.append(f'.{esc(name)}(env[{off+k-1}:{off}])')
                off+=k
            common=', '.join(connections)
            wrapper=LOG/f'{key}.v'
            wrapper.write_text(f'module audit_top(input [{width-1}:0] env, output diff);\n'
                               f'wire [{len(obs)-1}:0] a,b;\n'
                               f'audit_design left({common}, .audit_inject(1\'b0), .audit_obs(a));\n'
                               f'audit_design right({common}, .audit_inject(1\'b1), .audit_obs(b));\n'
                               'assign diff = |(a ^ b);\nendmodule\n',encoding='utf-8')
            witness=LOG/f'{key}.witness.json'
            if witness.exists():
                witness.unlink()
            logfile=LOG/f'{key}.sat.log'
            script=(f'read_json "{P0.wsl(model)}"\nread_verilog "{P0.wsl(wrapper)}"\n'
                    'hierarchy -top audit_top\nflatten\nopt_clean\n'
                    f'sat -prove diff 0 -show-inputs -show-outputs -timeout 5 -dump_json "{P0.wsl(witness)}"\n')
            out=P0.run_yosys(script,logfile,timeout=60)
            if 'ERROR:' in out:
                raise RuntimeError(str(logfile))
            if 'model found: FAIL' in out:
                status='sensitizable_sat'
            elif 'no model found: SUCCESS' in out:
                status='blocked_unsat'
            else:
                status='unknown'
            rows.append(dict(view=view,target=r.target,kind=r.kind,status=status,observed_bits=len(obs),
                             shared_input_bits=width,elapsed_s=time.perf_counter()-t0,
                             state_semantics='shared_arbitrary_state_legacy_cell_map',
                             legal_activation='not_proved_by_intervention',log=str(logfile.relative_to(ROOT)),
                             witness=str(witness.relative_to(ROOT)) if witness.exists() else ''))
            pd.DataFrame(rows).to_csv(OUT/'two_case_observability.csv',index=False,encoding='utf-8-sig')
            print(f'[observe] {view} {r.target} {status}',flush=True)
    print(pd.DataFrame(rows).to_string(index=False),flush=True)


if __name__=='__main__':
    main()
