"""Bitwise aliases and boundary-consistent 39-column features.

Separate opt-in producer: never writes legacy parser outputs, .pt or SAT data.
Supports the flattened structural Verilog subset present in the frozen fold;
unsupported statements, width mismatches and missing cells fail closed.
"""
from __future__ import annotations
import re,collections
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

CONTRACT='base39_bitwise_alias_boundary_v2_exact2_explicit_assign_nodes'
SYNTHETIC={'V2_ASSIGN_AND':(['A','B'],'ANDX'),'V2_ASSIGN_OR':(['A','B'],'ORX'),'V2_ASSIGN_XOR':(['A','B'],'XORX'),'V2_ASSIGN_NOT':(['A'],'INVX'),'V2_ASSIGN_MUX':(['S','A','B'],'MUXX')}
COLS=[f'gate_{s}' for s in ['ANDX','AOIX','AOX','BUFX','DFFARX','DFFNX','DFFX','HADDX','HARD_INC','INVX','ISOLANDX','LSDNENX','LSDNX','MUXX','NANDX','NORX','OAIX','OAX','ORX','SDFFSRX','SDFFX','TOP_HARD','TOP_RVT','XNORX','XORX']]+['log1p_connection_input_ports','log1p_incident_connection_count','touches_PI','touches_PO','directed_distance_from_PI','directed_distance_to_PO','log1p_exact2_fanin','log1p_exact2_fanout','register_reset_input_side_distance','register_reset_output_side_distance','log1p_register_reset_exact2_fanin','log1p_register_reset_exact2_fanout','in_combinational_SCC','log1p_combinational_SCC_size']
def clean(s):return s.strip().lstrip('\\')
def split_top(s):
    out=[];depth=0;start=0
    for i,ch in enumerate(s):
        if ch in '{(':depth+=1
        elif ch in '})':depth-=1
        elif ch==',' and depth==0:out.append(s[start:i].strip());start=i+1
    if depth:raise ValueError('Unbalanced concatenation')
    out.append(s[start:].strip());return out
def load_library(path):
    text=re.sub(r'//[^\n]*|/\*.*?\*/','',Path(path).read_text(encoding='utf-8'),flags=re.S);out={}
    for m in re.finditer(r'\bmodule\s+(\w+)\b.*?;(.*?)\bendmodule',text,re.S):
        d={'input':[],'output':[],'scalar':True}
        for st in m[2].split(';'):
            q=re.match(r'^\s*(input|output)\s+(.+)$',st,re.S)
            if q:
                if '[' in q[2]:d['scalar']=False
                body=re.sub(r'\[[^\]]*\]','',q[2])
                d[q[1]] += [clean(s) for s in split_top(body)]
        out[m[1]]=d
    return out
class Union:
    def __init__(self):self.parent={}
    def find(self,s):
        p=self.parent;root=s
        while root in p and p[root]!=root:root=p[root]
        while s in p and p[s]!=s:nxt=p[s];p[s]=root;s=nxt
        return root
    def join(self,a,b):
        a,b=self.find(a),self.find(b)
        if a==b:return
        # Constants of the same value share one signal; conflicting assignments fail.
        if a.startswith('#') and b.startswith('#'):
            if a!=b:raise ValueError(f'Conflicting constant alias {a} {b}')
            return
        if a.startswith('#'):self.parent[b]=a
        else:self.parent[a]=b
def parse(path,node_names,lib):
    text=Path(path).read_text(encoding='utf-8');text=re.sub(r'//[^\n]*|/\*.*?\*/','',text,flags=re.S);text=re.sub(r'\(\*.*?\*\)','',text,flags=re.S)
    statements=[s.strip() for s in text.split(';') if s.strip()];ranges={};decls={'input':[],'output':[],'inout':[]};aliases=[];cell_st=[]
    for st in statements:
        q=re.match(r'^(input|output|inout|wire|reg)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*(.*)$',st,re.S)
        if q:
            kind,high,low,body=q.groups()
            for name in split_top(body):
                name=clean(name)
                if high is not None:
                    hi,lo=int(high),int(low);ranges[name]=list(range(hi,lo+(1 if lo>=hi else -1),1 if lo>=hi else -1))
                if kind in decls:decls[kind].append(name)
        elif st.startswith('assign '):
            q=re.fullmatch(r'assign\s+(.+?)\s*=\s*(.+)',st,re.S)
            if not q:raise ValueError('Malformed assign')
            aliases.append((q[1],q[2]))
        elif re.match(r'^(module|endmodule)\b',st):continue
        else:cell_st.append(st)
    def bits(s):
        s=s.strip()
        if s.startswith('{') and s.endswith('}'):
            body=s[1:-1].strip();rep=re.fullmatch(r'(\d+)\s*\{(.*)\}',body,re.S)
            if rep:return bits('{'+rep[2]+'}')*int(rep[1])
            out=[]
            for part in split_top(body):out.extend(bits(part))
            return out
        lit=re.fullmatch(r"(\d+)'([bBoOdDhH])([0-9a-fA-FxXzZ_]+)",s)
        if lit:
            width=int(lit[1]);base=lit[2].lower();digits=lit[3].replace('_','').lower()
            if base=='b':values=list(digits)
            elif any(c in digits for c in 'xz'):
                if len(set(digits))!=1:raise ValueError('Mixed unknown digit literal unsupported')
                values=list(digits[0]*width)
            else:values=list(bin(int(digits,{'o':8,'d':10,'h':16}[base]))[2:])
            fill=values[0] if values and values[0] in 'xz' else '0';values=([fill]*width+values)[-width:]
            return ['#'+v for v in values]
        if s in ['0','1']:return ['#'+s]
        if s.startswith('\\'):
            token=clean(s)
            if re.search(r'\s',token):raise ValueError(f'Invalid escaped identifier {s}')
            return [token] # Brackets in an escaped identifier are literal, not a select.
        q=re.fullmatch(r'([A-Za-z_$][\w$./]*)\[\s*(\d+)\s*:\s*(\d+)\s*\]',s)
        if q:
            hi,lo=int(q[2]),int(q[3]);return [f'{q[1]}[{i}]' for i in range(hi,lo+(1 if lo>=hi else -1),1 if lo>=hi else -1)]
        if not re.fullmatch(r'[A-Za-z_$][\w$./]*(?:\[\d+\])?',s):raise ValueError(f'Unsupported signal expression {s!r}')
        return [f'{s}[{i}]' for i in ranges[s]] if s in ranges else [s]
    uf=Union();alias_bits=0;expressions=[]
    for lhs,rhs in aliases:
        aa=bits(lhs)
        try:bb=bits(rhs)
        except ValueError:
            if len(aa)!=1:raise ValueError('Only scalar continuous expression outputs supported')
            expressions.append((aa[0],rhs));continue
        if len(aa)!=len(bb):raise ValueError(f'Alias width mismatch {lhs}={rhs}: {len(aa)} != {len(bb)}')
        for a,b in zip(aa,bb):uf.join(a,b);alias_bits+=1
    pi={uf.find(bit) for key in ['input','inout'] for name in decls[key] for bit in bits(name)}
    po={uf.find(bit) for key in ['output','inout'] for name in decls[key] for bit in bits(name)}
    cells={}
    for st in cell_st:
        q=re.fullmatch(r'([\w$]+)\s+(\\\S+|[^\s(]+)\s*\((.*)\)',st,re.S)
        if not q or q[1] not in lib:raise ValueError(f'Unsupported or unknown cell: {st[:100]}')
        typ,name,body=q.groups();name=clean(name)
        if not lib[typ].get('scalar',True):raise ValueError(f'Non-scalar instantiated library cell {typ}')
        if name in cells:raise ValueError('Duplicate cell name')
        connections=[]
        for part in split_top(body):
            pin=re.fullmatch(r'\.\s*(\w+)\s*\((.*)\)',part,re.S)
            if not pin:raise ValueError(f'Non-named cell port {part}')
            if pin[1] not in lib[typ]['input']+lib[typ]['output']:raise ValueError(f'Unknown pin {typ}.{pin[1]}')
            if not pin[2].strip():continue
            bb=bits(pin[2])
            if len(bb)!=1:raise ValueError(f'Non-scalar cell pin {typ}.{pin[1]}')
            connections.append((pin[1],uf.find(bb[0])))
        cells[name]=(typ,connections)
    if set(cells)!=set(node_names):raise ValueError(f'Cell coordinates differ: missing={list(set(node_names)-set(cells))[:3]} extra={list(set(cells)-set(node_names))[:3]}')
    lib=dict(lib)
    for typ,(pins,_) in SYNTHETIC.items():lib[typ]={'input':pins,'output':['Y']}
    virtual=[]
    def expression_ast(text):
        token=re.compile(r"\s*(\\[^\s]+|\d+'[bBoOdDhH][0-9a-fA-FxXzZ_]+|[A-Za-z_$][\w$./]*(?:\[\d+\])?|[01]|[~&|^?:()])")
        tokens=[];pos=0
        while pos<len(text):
            if not text[pos:].strip():break
            m=token.match(text,pos)
            if not m:raise ValueError(f'Unsupported continuous expression {text!r}')
            tokens.append(m[1]);pos=m.end()
        i=0
        def atom():
            nonlocal i
            if i>=len(tokens):raise ValueError('Incomplete expression')
            s=tokens[i];i+=1
            if s=='~':return ('~',atom())
            if s=='(':
                out=conditional()
                if i>=len(tokens) or tokens[i]!=')':raise ValueError('Unbalanced expression')
                i+=1;return out
            bb=bits(s)
            if len(bb)!=1:raise ValueError('Scalar continuous operands required')
            return ('leaf',uf.find(bb[0]))
        def binary(level):
            nonlocal i
            ops=['|','^','&']
            out=atom() if level==3 else binary(level+1)
            if level==3:return out
            while i<len(tokens) and tokens[i]==ops[level]:
                op=tokens[i];i+=1;out=(op,out,binary(level+1))
            return out
        def conditional():
            nonlocal i
            out=binary(0)
            if i<len(tokens) and tokens[i]=='?':
                i+=1;yes=conditional()
                if i>=len(tokens) or tokens[i]!=':':raise ValueError('Incomplete conditional')
                i+=1;out=('?',out,yes,conditional())
            return out
        ast=conditional()
        if i!=len(tokens):raise ValueError('Trailing expression tokens')
        return ast
    def emit(ast,output=None,origin=''):
        if ast[0]=='leaf':return ast[1]
        vals=[emit(t,origin=origin) for t in ast[1:]];typ={'&':'V2_ASSIGN_AND','|':'V2_ASSIGN_OR','^':'V2_ASSIGN_XOR','~':'V2_ASSIGN_NOT','?':'V2_ASSIGN_MUX'}[ast[0]]
        name=f'__v2_assign_{len(virtual):06d}'
        if name in cells:raise ValueError('Synthetic name collision')
        net=output if output is not None else f'@v2_net_{len(virtual):06d}'
        pins=SYNTHETIC[typ][0];cells[name]=(typ,list(zip(pins,vals))+[('Y',net)])
        virtual.append(dict(name=name,type=typ,expression=origin,output=net,inputs=vals));return net
    for lhs,rhs in expressions:emit(expression_ast(rhs),output=uf.find(lhs),origin=f'{lhs} = {rhs}')
    all_names=list(node_names)+[r['name'] for r in virtual]
    drivers=collections.defaultdict(list);cons=collections.defaultdict(list);types=[];pi_flag=[];po_flag=[];ports=[]
    for i,name in enumerate(all_names):
        typ,conn=cells[name];types.append(typ);ports.append(len(lib[typ]['input']));pi_flag.append(any(n in pi for p,n in conn));po_flag.append(any(n in po for p,n in conn))
        for p,n in conn:
            if p in lib[typ]['output']:drivers[n].append(i)
            if p in lib[typ]['input']:
                role=1
                if 'DFF' in typ.upper():
                    up=p.upper()
                    role=1 if up=='D' else 2 if up in ['CK','CLK','CLOCK'] else 4 if up in ['SI','SCANIN'] else 8 if up in ['RN','SN','RST','RESET','RESETN','SET','SETN','CLR','PRE'] else 16 if up in ['SE','EN','ENABLE'] else 64
                cons[n].append((i,role))
    degree=np.zeros(len(all_names),np.int64);edges={};multidrivers=[]
    for net,owners in drivers.items():
        if net.startswith('#') and cons.get(net):raise ValueError('A driven net aliases a constant')
        if len(set(owners))>1:multidrivers.append(net)
        for u in owners:
            for v,role in cons.get(net,[]):
                edges[u,v]=edges.get((u,v),0)|role;degree[u]+=1;degree[v]+=1
    if multidrivers:raise ValueError(f'Multiple cell drivers: {multidrivers[:3]}')
    pairs=sorted(edges);edge=np.array(pairs,dtype=np.int64).T if pairs else np.empty((2,0),np.int64)
    roles=np.array([edges[p] for p in pairs],np.uint8)
    return dict(types=types,input_ports=np.array(ports),PI=np.array(pi_flag),PO=np.array(po_flag),edge_index=edge,edge_roles=roles,incident_count=degree,alias_statements=len(aliases),alias_bits=alias_bits,vector_declarations=len(ranges),original_nodes=len(node_names),virtual_nodes=virtual,port_boundary_contract='All connected pins; aliases normalized identically to primary ports; constants are not PI; continuous operators are explicit auxiliary nodes')
def adjacency(edge,n,reverse=False):
    src,dst=(edge[1],edge[0]) if reverse else edge
    return csr_matrix((np.ones(len(src),np.int8),(src,dst)),shape=(n,n))
def distance(adj,seeds):
    n=adj.shape[0];d=np.full(n,-1,np.int32);q=collections.deque(sorted(set(int(s) for s in seeds)));d[list(q)]=0
    while q:
        i=q.popleft()
        for j in adj.indices[adj.indptr[i]:adj.indptr[i+1]]:
            if d[j]<0:d[j]=d[i]+1;q.append(int(j))
    return d
def exact2(adj):
    n=adj.shape[0];ind,ptr=adj.indices,adj.indptr;out=np.zeros(n,np.float64)
    for i in range(n):
        second=set()
        for j in ind[ptr[i]:ptr[i+1]]:second.update(ind[ptr[j]:ptr[j+1]])
        second.discard(i);out[i]=np.log1p(len(second))
    return out
def features(g,mapping,gate_order):
    n=len(g['types']);x=np.zeros((n,39),np.float32);lookup={s:i for i,s in enumerate(gate_order)}
    for i,typ in enumerate(g['types']):x[i,lookup[SYNTHETIC[typ][1] if typ in SYNTHETIC else mapping[typ]]]=1
    e=g['edge_index'];isff=np.array(['DFF' in s.upper() for s in g['types']]);succ=adjacency(e,n);pred=adjacency(e,n,True)
    x[:,25]=np.log1p(g['input_ports']);x[:,26]=np.log1p(g['incident_count']);x[:,27]=g['PI'];x[:,28]=g['PO'];x[:,29]=distance(succ,np.flatnonzero(g['PI']));x[:,30]=distance(pred,np.flatnonzero(g['PO']));x[:,31]=exact2(pred);x[:,32]=exact2(succ)
    fwd=e[:,~isff[e[1]]];rev=e[:,~isff[e[0]]]
    fs=adjacency(fwd,n);fp=adjacency(fwd,n,True);rs=adjacency(rev,n);rp=adjacency(rev,n,True)
    seeds0=set(e[1,isff[e[0]]]) if isff.any() else np.flatnonzero(g['PI']);seeds1=set(e[0,isff[e[1]]]) if isff.any() else np.flatnonzero(g['PO'])
    d0=distance(fs,seeds0);d1=distance(rp,seeds1);d0[isff]=0;d1[isff]=0
    x[:,33]=d0;x[:,34]=d1;x[:,35]=exact2(fp);x[:,36]=exact2(rs)
    _,labels=connected_components(rs,directed=True,connection='strong');sizes=np.bincount(labels);loops=set(e[0,(e[0]==e[1])&~isff[e[0]]]);x[:,37]=[sizes[c]>1 or i in loops for i,c in enumerate(labels)];x[:,38]=np.log1p(sizes[labels])
    if not np.isfinite(x).all():raise ValueError('Nonfinite features')
    return x
