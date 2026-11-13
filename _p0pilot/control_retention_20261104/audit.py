"""Offline control-object trace audit. No solver, training or production mutation."""
from pathlib import Path
import json,re,csv,hashlib,collections,datetime
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
F=ROOT/'generate_trans/folds/hosts_bt31'
def read(p):return p.read_text(encoding='utf-8-sig')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return s.strip().lstrip('\\')
def cells(p):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',read(p),flags=re.S)
    out={}
    for m in re.finditer(r'^\s*([\w$]+)\s+(\\[^\s]+|[\w.$\[\]/]+)\s*\((.*?)\)\s*;',text,re.M|re.S):
        if m[1] in ('module','assign','input','output','wire'):continue
        con={a:norm(b) for a,b in re.findall(r'\.\s*(\w+)\s*\(\s*([^)]*)\)',m[3])}
        if con:out[norm(m[2])]=(m[1],con)
    return out,text
def dump(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    split=json.loads(read(F/'views.json'));meta={r['view']:r for r in csv.DictReader(read(F/'views_meta.csv').splitlines())}
    prov=collections.defaultdict(list)
    for p in (ROOT/'generate_trans').glob('hosts*/*/provenance.json'):
        try:
            a=json.loads(read(p))
            if isinstance(a,list):
                for d in a:
                    if d.get('view'):prov[d['view']].append((p,d))
        except (ValueError,OSError):continue
    sources={};vr=[];nr=[];bindings={};groups=collections.Counter();clean_cache={}
    def interface(text):
        return re.sub(r'\s+','',re.search(r'\bmodule\s+[^\s(]+\s*\((.*?)\)\s*;',text,re.S)[1])
    def assignments(text):
        return sorted(re.sub(r'\s+','',x) for x in re.findall(r'\bassign\s+(.*?);',text,re.S))
    for sp,key in [('train','train_views'),('val','val_views'),('test','test_views')]:
        for view in split[key]:
            fam=view.split('__')[1]
            if not(fam.startswith('ctl') or fam.startswith('a4ctl')):continue
            m=meta[view];src=m['src_view'];sf=F/'orig'/(src+'.v');tf=F/'trans'/(view+'.v');mf=F/'mappings'/(view+'.json')
            if src not in sources:
                sc,st=cells(sf);choices=[(p,d) for p,d in prov[src] if d.get('new_gates') and all(norm(g) in sc for g in d['new_gates'])]
                lists={tuple(sorted(d['new_gates'])) for p,d in choices}
                if len(lists)!=1:raise ValueError(('ambiguous source provenance',src,len(lists)))
                pp,pd=choices[0];sources[src]=(sc,pp,pd)
            sc,pp,pd=sources[src];new=sorted(map(norm,pd['new_gates']));tc,tt=cells(tf);mp=json.loads(read(mf));align=mp.get('node_alignment',{})
            binding_ok=mp.get('src_view')==src and mp.get('rw_view')==view
            # A generated map provides lineage, not a function or one-to-one proof.
            counts=collections.Counter();targetset=set();missing=[];stale=[];shared=set();reverse=collections.defaultdict(set)
            for a,bs in align.items():
                for b in bs:reverse[norm(b)].add(norm(a))
            directmissing=[]
            for g in new:
                names=sorted({norm(x) for x in align.get(g,[])}) if binding_ok else []
                valid=[x for x in names if x in tc];invalid=[x for x in names if x not in tc]
                direct=g in tc
                # Exact surviving instance name is separate from historical map support.
                if direct and g not in valid:directmissing.append(g)
                found=sorted(set(valid+([g] if direct else [])))
                mixed=[x for x in found if reverse[x]-set(new)]
                shared.update(mixed);targetset.update(found)
                state='mapped' if found else 'unresolved'
                counts[state]+=1
                if not found:missing.append(g)
                if invalid:stale.append(g)
                nr.append(dict(split=sp,view=view,source_view=src,family=fam,source_gate=g,source_type=sc[g][0],status=state,
                    exact_name_present=direct,map_targets_valid='|'.join(valid),map_targets_missing='|'.join(invalid),all_trace_targets='|'.join(found),
                    target_types='|'.join(tc[x][0] for x in found),shared_with_host_sources='|'.join(mixed),functional_proof=False))
            n=len(new);k=counts['mapped']
            status='完整保留' if k==n else '部分保留' if k else '映射不明'
            clean=ROOT/'generate_trans/yslib_test'/m['host']/(m['host']+'_clean__'+m['op']+'.v')
            identical_clean=False
            if clean.exists():
                if clean not in clean_cache:clean_cache[clean]=cells(clean)
                cc,ct=clean_cache[clean]
                identical_clean=bool(tc) and tc==cc and interface(tt)==interface(ct) and assignments(tt)==assignments(ct)
                bindings[str(clean.relative_to(ROOT))]=sha(clean)
            if identical_clean and not k:status='消除'
            # Equality of existing gates/pin connections, module port lists and assigns
            # confirms no separate added gate object; not a new functional SAT proof.
            groups[(sp,status)]+=1
            vr.append(dict(split=sp,host=m['host'],family=fam,recipe=m['op'],view=view,source_view=src,status=status,
                source_added_nodes=n,traced_source_nodes=k,unresolved_source_nodes=n-k,trace_coverage=round(k/n,6),target_nodes=len(targetset),
                shared_target_nodes=len(shared),map_stale_source_nodes=len(stale),direct_name_only_nodes=len(directmissing),
                mapping_header_matches=binding_ok,unresolved_instances='|'.join(missing),target_instances='|'.join(sorted(targetset)),
                elimination_confirmed=status=='消除',identical_to_clean=identical_clean,
                clean_reference=str(clean.relative_to(ROOT)) if clean.exists() else '',
                functional_equivalence_certified=False,source_sha=sha(sf),target_sha=sha(tf),mapping_sha=sha(mf),provenance=str(pp.relative_to(ROOT))))
            for p in [sf,tf,mf,pp]:bindings[str(p.relative_to(ROOT))]=sha(p)
    dump('per_view.csv',vr);dump('per_source_node.csv',nr)
    summary=[]
    for key in ['split','family','recipe']:
        for v in sorted({r[key] for r in vr}):
            a=[r for r in vr if r[key]==v];d=dict(group_by=key,group=v,views=len(a))
            for st in ['完整保留','部分保留','消除','映射不明']:d[st]=sum(r['status']==st for r in a)
            d.update(source_node_occurrences=sum(r['source_added_nodes'] for r in a),traced_occurrences=sum(r['traced_source_nodes'] for r in a),target_occurrences=sum(r['target_nodes'] for r in a),shared_target_occurrences=sum(r['shared_target_nodes'] for r in a))
            summary.append(d)
    dump('summary.csv',summary)
    info=dict(time=datetime.datetime.now().astimezone().isoformat(),source_views=len(sources),transformed_views=len(vr),new_sat_queries=0,new_training_runs=0,
        counts=dict(collections.Counter(r['status'] for r in vr)),shared_target_views=sum(r['shared_target_nodes']>0 for r in vr),
        stale_map_views=sum(r['map_stale_source_nodes']>0 for r in vr),mapping_header_mismatch=sum(not r['mapping_header_matches'] for r in vr),
        definition='完整/部分保留 means lineage/name trace support only, not functional/role certification. 消除 additionally requires exact same existing cell/pin connections, port list and assigns as existing clean same-recipe reference; absence alone never sufficient.',input_hashes=bindings)
    (OUT/'audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k!='input_hashes'},ensure_ascii=False,indent=2))
    for x in summary:print(x)
if __name__=='__main__':main()
