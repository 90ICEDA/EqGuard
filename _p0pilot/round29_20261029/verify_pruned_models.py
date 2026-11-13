"""Bounded label-blind equivalence checks for cone-pruned native SAT models."""
import sys,json,re,time,gc,statistics
from pathlib import Path
H=Path(__file__).resolve().parent;S=H.parent/'round27_20261027';sys.path.insert(0,str(S))
import k4_runtime as R
sys.path.insert(0,str(R.ROOT/'phase2/ys'));import native_boundary_extract as N
from k4_fast_support import compile_logic,pruned_model

def records_from_code(code):
    targets={int(a):b for a,b in re.findall(r'assign target\[(\d+)\]=([^;]+);',code)}
    cuts={int(a):b for a,b in re.findall(r'assign premise\[(\d+)\]=\(\{([^}]+)\}==pattern',code)}
    def bit(s):
        if s.startswith('b') and s[1:].isdigit():return int(s[1:])
        if s in ("1'b0","1'b1"):return s[-1]
        raise ValueError(s)
    return [dict(target_bit=bit(targets[j]),cut_bits=[bit(b) for b in reversed(cuts[j].split(','))]) for j in range(len(targets))]

def main():
    reference=json.loads((H/'acceleration_reviews/review_00001/benchmark.json').read_text());out=R.fresh_dir(H/'pruned_model_checks','review');reports=[]
    for summary in reference['views']:
        v=summary['view'];folder=R.PANEL/'views'/v;ss=json.loads((folder/'snapshots.json').read_text())[0];raw=R.ROOT/ss['folder']/'raw.json';assert R.sha(raw)==ss['raw_sha']
        m=next(iter(json.loads(raw.read_text())['modules'].values()));lines,width=N.logic(m);compiled=compile_logic(lines)
        batches=sorted(p for p in (folder/'queries'/v).iterdir() if p.is_dir())
        for idx in [0,len(batches)//2,len(batches)-1]:
            batch=batches[idx];results=([batch/'results.json'] if (batch/'results.json').exists() else [])+sorted(batch.glob('attempt_*/results.json'));p=results[-1]
            old=(p.parent/'model.v').read_text(encoding='utf-8');saved=json.loads(p.read_text());assert R.sha(p.parent/'model.v')==saved['model_sha'];rows=records_from_code(old);assert N.model(m,rows)==old
            t=time.perf_counter();new=pruned_model(compiled,width,rows,N.bitref);prune_seconds=time.perf_counter()-t
            case=R.fresh_dir(out,'case');(case/'gold.v').write_text(old,encoding='utf-8',newline='\n');(case/'gate.v').write_text(new,encoding='utf-8',newline='\n')
            wsl=lambda path:'/mnt/'+str(path.resolve()).replace('\\','/')[0].lower()+str(path.resolve()).replace('\\','/')[2:]
            script=f'read_verilog "{wsl(case/"gold.v")}"\nrename check gold\nread_verilog "{wsl(case/"gate.v")}"\nrename check gate\nmiter -equiv -flatten gold gate miter\nhierarchy -top miter\nproc\nopt\nsat -verify -prove trigger 0 -timeout 30\n'
            text=R.checked_yosys(script,case/'equivalence.log',timeout=90)
            if 'SAT proof finished - no model found: SUCCESS!' not in text:raise ValueError('Equivalence not proved')
            reports.append(dict(view=v,batch=batch.name,full_bytes=len(old.encode()),pruned_bytes=len(new.encode()),prune_seconds=prune_seconds,equivalence_proved=True,proof_log=str((case/'equivalence.log').relative_to(R.ROOT)),queries=len(saved['queries'])))
            print('PROVED',v,batch.name,'bytes',len(old),len(new),flush=True)
        del m,lines,compiled;gc.collect()
    report=dict(time=__import__('datetime').datetime.now().astimezone().isoformat(),cases=reports,all_proved=True,formal_miter_queries=len(reports),extraction_queries_repeated=0,labels_read=False,new_training_runs=0,original_helper_sha=R.sha(R.ROOT/'phase2/ys/native_boundary_extract.py'),optimized_helper_sha=R.sha(S/'k4_fast_support.py'))
    R.write_new(out/'report.json',report);print('REPORT',out,flush=True)

if __name__=='__main__':main()
