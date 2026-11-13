import sys,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'phase2/ys'))
from feature_encoding_v2 import parse,features,exact2,adjacency,CONTRACT
H=Path(__file__).resolve().parent/'validation';H.mkdir(parents=True,exist_ok=True)
lib={'INVX0':{'input':['IN'],'output':['QN']},'AND2X2':{'input':['IN1','IN2'],'output':['Q']},'SDFFX1':{'input':['D','CLK','SI','SE'],'output':['Q','QN']}}
cases=[]
def case(name,text,names,check):
    p=H/(name+'.v');p.write_text(text,encoding='utf-8');g=parse(p,names,lib);check(g);cases.append(dict(name=name,passed=True,source_sha=hashlib.sha256(p.read_bytes()).hexdigest()))
def eq(a,b):assert a==b,(a,b)
case('long_alias_chain','module m(a,y);input a;output y;'+''.join(f'wire n{i};' for i in range(41))+'assign n0=a;'+''.join(f'assign n{i}=n{i-1};' for i in range(1,41))+'INVX0 u(.IN(n40),.QN(y));endmodule',['u'],lambda g:(eq(g['PI'].tolist(),[True]),eq(g['PO'].tolist(),[True])))
case('bitwise_concat','module m(a,z);input a;output [1:0] z;wire [1:0] b;wire [1:0] c;INVX0 u0(.IN(a),.QN(b[0]));INVX0 u1(.IN(a),.QN(b[1]));assign c={b[0],b[1]};INVX0 v0(.IN(c[0]),.QN(z[0]));INVX0 v1(.IN(c[1]),.QN(z[1]));endmodule',['u0','u1','v0','v1'],lambda g:eq(g['edge_index'].T.tolist(),[[0,3],[1,2]]))
case('reversed_range','module m(a,z);input [1:0] a;output z;wire [0:1] b;assign b=a;INVX0 u(.IN(b[0]),.QN(z));endmodule',['u'],lambda g:eq(g['PI'].tolist(),[True]))
case('part_select','module m(a,z);input [3:0] a;output z;wire [1:0] b;assign b=a[3:2];INVX0 u(.IN(b[0]),.QN(z));endmodule',['u'],lambda g:eq(g['PI'].tolist(),[True]))
case('constant_not_PI','module m(z);output z;wire c;assign c=1\'h1;INVX0 u(.IN(1\'b1),.QN(z));endmodule',['u'],lambda g:eq(g['PI'].tolist(),[False]))
case('replication','module m(a,z);input a;output z;wire [1:0] b;assign b={2{a}};AND2X2 u(.IN1(b[1]),.IN2(b[0]),.Q(z));endmodule',['u'],lambda g:eq(g['PI'].tolist(),[True]))
case('independent_Q_QN','module m(a,clk,z);input a,clk;output z;wire q,qn;SDFFX1 ff(.D(a),.CLK(clk),.Q(q),.QN(qn),.SI(a),.SE(a));INVX0 u(.IN(q),.QN(z));INVX0 v(.IN(qn),.QN(t));endmodule',['ff','u','v'],lambda g:eq(g['edge_index'].T.tolist(),[[0,1],[0,2]]))
case('continuous_operator_preserved','module m(a,z);input a;output z;wire b;assign b=1\'h1&a;INVX0 u(.IN(b),.QN(z));endmodule',['u'],lambda g:(eq(g['edge_index'].T.tolist(),[[1,0]]),eq(g['PI'].tolist(),[False,True]),eq(len(g['virtual_nodes']),1)))
case('continuous_mux_preserved','module m(a,s,z);input a,s;output z;wire b;assign b=s?1\'h0:a;INVX0 u(.IN(b),.QN(z));endmodule',['u'],lambda g:(eq(g['edge_index'].T.tolist(),[[1,0]]),eq(g['types'],['INVX0','V2_ASSIGN_MUX'])))
for name,st in [('width_reject','wire [1:0] b;assign b=a;'),('expression_reject','wire b;assign b=a+a;')]:
    p=H/(name+'.v');p.write_text('module m(a,z);input a;output z;'+st+'INVX0 u(.IN(a),.QN(z));endmodule',encoding='utf-8')
    try:parse(p,['u'],lib)
    except ValueError:cases.append(dict(name=name,passed=True));continue
    raise AssertionError('Expected rejection '+name)
rng=np.random.default_rng(42)
for k in range(30):
    n=12;e=np.array(sorted({tuple(v) for v in rng.integers(0,n,(18,2))}),dtype=np.int64).T
    adj=adjacency(e,n);expected=[]
    for i in range(n):
        one={int(v) for u,v in e.T if u==i};two={int(v) for u,v in e.T if u in one};two.discard(i);expected.append(np.log1p(len(two)))
    assert np.allclose(exact2(adj),expected)
cases.append(dict(name='30_random_exact2_reference_graphs',passed=True))
(H/'unit_results.json').write_text(json.dumps(dict(contract=CONTRACT,cases=cases,new_sat_queries=0,new_training_runs=0),ensure_ascii=False,indent=2),encoding='utf-8');print('PASS',len(cases),'cases including 30 random reference graphs')
