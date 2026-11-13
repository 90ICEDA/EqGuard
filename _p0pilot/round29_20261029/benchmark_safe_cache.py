"""Existing evidence only: byte equivalence and CPU construction benchmark."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import sys,json,time,gc,statistics,collections
from pathlib import Path
H=Path(__file__).resolve().parent;S=H.parent/'round27_20261027';sys.path.insert(0,str(S))
import k4_runtime as R
sys.path.insert(0,str(R.ROOT/'phase2/ys'));import native_boundary_extract as N
from k4_fast_support import model_from_logic

def main():
    out=R.fresh_dir(H/'acceleration_reviews','review');reports=[];runtime=[]
    wanted=[('s15850t100','ys_abc'),('s15850t100','ys_aig'),('s15850t100','ys_nand'),('s35932t200','ys_abc'),('s35932t200','ys_aig'),('s35932t200','ys_nand')]
    plan=R.read_plan(R.PANEL/'plan.json')['views']
    for host,recipe in wanted:
        item=next(i for i in plan if i['view'].startswith(host+'__') and i['view'].endswith('__'+recipe) and (R.PANEL/'views'/i['view']/'coverage.json').exists())
        folder=R.PANEL/'views'/item['view'];ss=json.loads((folder/'snapshots.json').read_text())[0];raw=R.ROOT/ss['folder']/'raw.json';assert R.sha(raw)==ss['raw_sha']
        m=next(iter(json.loads(raw.read_text())['modules'].values()))
        qr=folder/'queries'/item['view'];batches=sorted([p for p in qr.iterdir() if p.is_dir()]);indices=sorted({0,len(batches)//4,len(batches)//2,3*len(batches)//4,len(batches)-1});samples=[]
        for i in indices:
            batch=batches[i];paths=([batch/'results.json'] if (batch/'results.json').exists() else [])+sorted(batch.glob('attempt_*/results.json'))
            saved=json.loads(paths[-1].read_text());code=(paths[-1].parent/'model.v').read_text(encoding='utf-8')
            # Recover target/cut coordinates from the saved model formatting,
            # without loading every node record or any labels.
            targets={int(a):b for a,b in __import__('re').findall(r'assign target\[(\d+)\]=([^;]+);',code)}
            cuts={int(a):b for a,b in __import__('re').findall(r'assign premise\[(\d+)\]=\(\{([^}]+)\}==pattern',code)}
            def bit(s):
                if s.startswith('b') and s[1:].isdigit():return int(s[1:])
                if s in ("1'b0","1'b1"):return s[-1]
                raise ValueError(s)
            records=[dict(target_bit=bit(targets[j]),cut_bits=[bit(b) for b in reversed(cuts[j].split(','))]) for j in range(len(targets))]
            assert records and len(records)==len(cuts)
            samples.append((records,code,paths[-1],saved))
        start=time.perf_counter();lines,width=N.logic(m);cached_logic_seconds=time.perf_counter()-start
        old_t=[];fast_t=[]
        for records,code,path,saved in samples:
            t=time.perf_counter();old=N.model(m,records);old_t.append(time.perf_counter()-t)
            t=time.perf_counter();fast=model_from_logic(lines,width,records,N.bitref);fast_t.append(time.perf_counter()-t)
            assert old==fast==code,'Model formatting changed'
            assert R.sha(path.parent/'model.v')==saved['model_sha']
            exe=json.loads((path.parent/'run.execution.json').read_text()) if (path.parent/'run.execution.json').exists() else {}
            runtime.append(dict(host=host,recipe=recipe,view=item['view'],queries=len(saved['queries']),targets=len(saved['tables']),solver_seconds=exe.get('seconds'),batch_wall_seconds=saved.get('wall_s'),batch_bytes=sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file())))
        t=time.perf_counter();R.sha(raw);raw_hash=time.perf_counter()-t
        reports.append(dict(view=item['view'],nodes=json.loads((folder/'coverage.json').read_text())['splits']['train']['nodes'],batches=len(batches),sampled_models=len(samples),models_byte_identical=True,logic_build_seconds=cached_logic_seconds,old_model_median_seconds=statistics.median(old_t),fast_model_median_seconds=statistics.median(fast_t),raw_hash_seconds=raw_hash,estimated_avoidable_cpu_seconds_per_view=(statistics.median(old_t)-statistics.median(fast_t)+2*raw_hash)*len(batches)))
        print('CHECKED',item['view'],flush=True);del m,lines,samples;gc.collect()
    summary=dict(views=reports,batches=runtime,new_solver_calls=0,new_training_runs=0,model_bytes_identical=True)
    R.write_new(out/'benchmark.json',summary);print('REPORT',out);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
