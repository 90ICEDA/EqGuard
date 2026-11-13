import ast,re,json,csv
from pathlib import Path
import numpy as np
from audit_encoding_errors import source_graph,FOLD,OUT as INITIAL_OUT,ROOT,HERE
from readonly_graph_arrays import arrays
OUT=HERE/'encoding_error_audit_v2'
src=(ROOT/'data/verilog_data/parser2.py').read_text(encoding='utf-8')
tree=ast.parse(src);body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fixassigns']
env={'re':re,'_TOK':re.compile(r'[\\\w.\[\]$]+')};exec(compile(ast.Module(body=body,type_ignores=[]),'<read-only parser fixassigns>','exec'),env)
a,_=arrays(FOLD/'data/processed/trans_graph.pt');x=a['x'];e=a['edge_index'];vi=np.load(HERE/'frozen/view_index_all.npy',mmap_mode='r');names=json.loads((HERE/'frozen/manifest.json').read_text())['view_names']
lib={};txt=(FOLD/'verilog_lib.v').read_text(encoding='utf-8')
for m in re.finditer(r'module\s+(\w+)\b.*?;(.*?)endmodule',txt,re.S):
    lib[m[1]]={'input':[],'output':[]}
    for d in re.finditer(r'\b(input|output)\s+([^;]+);',m[2]):lib[m[1]][d[1]] += [s for s in re.split(r'[,\s]+',d[2].strip()) if s]
views=['s35932t200__injalpha_d1_s42__ys_abc']+[v for v in names if v.startswith('rs232t1000__injalpha_') and '__keepbnd__' in v and v.endswith(('__ys_abc','__ys_aig','__ys_nand'))]
bounds={v:np.flatnonzero(vi==names.index(v)) for v in views};wanted=set(int(i) for ids in bounds.values() for i in ids);ns={}
with (FOLD/'data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
    for i,line in enumerate(f):
        if i in wanted:ns[i]=line.strip().lstrip('\\')
reports=[]
for view in views:
    path=FOLD/'trans'/f'{view}.v';text=path.read_text(encoding='utf-8');lines=text.split(';');legacy=env['fixassigns']([[lines]])[0][0]
    folder=OUT/'alias_replays'/view;folder.mkdir(parents=True)
    replay=folder/'parser_alias_replay.v';replay.write_text(';\n'.join(legacy),encoding='utf-8')
    ids=bounds[view];lo=int(ids[0]);hi=int(ids[-1])+1;nodenames=[ns[int(i)] for i in ids]
    *_,de,degree,missing=source_graph(replay,nodenames,lib)
    # Return tuple = gate,pins,pi,po,edges,degree,missing.
    legacyset=set(de)|{(v,u) for u,v in de};eu=e[:,np.searchsorted(e[0],lo):np.searchsorted(e[0],hi)]-lo
    r=dict(view=view,nodes=len(ids),missing=missing,legacy_edge_difference=len(legacyset^set(zip(*eu))),legacy_degree_mismatch=int((~np.isclose(x[ids,26],degree)).sum()))
    if view.startswith('s35932'):
        old=next(s.strip() for s in lines if 'g__0000__1 ' in s);new=next(s.strip() for s in legacy if 'g__0000__1 ' in s)
        k=nodenames.index('g__0000__1');r.update(original_cell=old,after_parser_alias=new,original_input_declaration='input RESET;',global_node=int(ids[k]),stored_touches_PI=float(x[ids[k],27]),stored_PI_distance=float(x[ids[k],29]))
    reports.append(r)
(OUT/'alias_replay_verification.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(reports,ensure_ascii=False,indent=2))
