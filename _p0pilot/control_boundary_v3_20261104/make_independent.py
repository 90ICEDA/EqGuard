"""Extend the frozen independent pin parser with explicit continuous-expression nodes."""
from pathlib import Path
import sys,inspect
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O.parent/'control_labelaudit_20261104'))
from audit import raw_network
src=inspect.getsource(raw_network)
escape_line="if s.startswith('\\\\'):return [norm(s)]"
assert escape_line in src
src=src.replace(escape_line,"if s.startswith('\\\\'):\n   assert not re.search(r'\\s',norm(s));return [norm(s)]")
old="for a,b in assign:\n  aa,bb=bits(a),bits(b);assert len(aa)==len(bb),(a,b)"
new="""expressions=[]
 for a,b in assign:
  aa=bits(a)
  try:bb=bits(b)
  except AssertionError:
   assert len(aa)==1;expressions.append((aa[0],b));continue
  assert len(aa)==len(bb),(a,b)"""
assert old in src;src=src.replace(old,new)
anchor=" po={find(n) for o in outputs for n in bits(o)};drivers="
insert="""
 lib={k:{p:list(v) for p,v in d.items()} for k,d in lib.items()}
 virtual_names=[]
 def emit(ast,output=None):
  op=ast[0]
  if op=='leaf':
   vv=bits(ast[1]);assert len(vv)==1;return find(vv[0])
  vals=[emit(t) for t in ast[1:]]
  typ,pins={'&':('V2_ASSIGN_AND',['A','B']),'|':('V2_ASSIGN_OR',['A','B']),'^':('V2_ASSIGN_XOR',['A','B']),'~':('V2_ASSIGN_NOT',['A']),'?':('V2_ASSIGN_MUX',['S','A','B'])}[op]
  num=len(virtual_names);name=f'__v2_assign_{num:06d}';net=output if output is not None else f'@v2_net_{num:06d}'
  assert name not in cells;cells[name]=(typ,list(zip(pins,vals))+[('Y',net)]);virtual_names.append(name);lib[typ]={'inputs':pins,'outputs':['Y']};return net
 for lhs,rhs in expressions:emit(parse_expression(rhs),output=find(lhs))
"""
assert anchor in src;src=src.replace(anchor,insert+anchor)
src=src.replace("assigns=len(assign))","assigns=len(assign),virtual_names=virtual_names)")
header='''import re,collections
from phase2.ys import netlist_feats as NF
def norm(s):return s.strip().lstrip('\\\\')
def parse_expression(text):
 toks=NF.tokenize(text);assert toks is not None,text
 pos=0
 def unary():
  nonlocal pos
  kind,t=toks[pos];pos+=1
  if t=='~':return ('~',unary())
  if t=='(':
   a=conditional();assert toks[pos][1]==')';pos+=1;return a
  assert kind in ['num','id','esc'],(kind,t,text);return ('leaf',t)
 def binary(level):
  nonlocal pos
  if level==3:return unary()
  op=['|','^','&'][level];a=binary(level+1)
  while pos<len(toks) and toks[pos][1]==op:
   pos+=1;a=(op,a,binary(level+1))
  return a
 def conditional():
  nonlocal pos
  a=binary(0)
  if pos<len(toks) and toks[pos][1]=='?':
   pos+=1;b=conditional();assert toks[pos][1]==':';pos+=1;a=('?',a,b,conditional())
  return a
 a=conditional();assert pos==len(toks),(text,pos,toks);return a
'''
(O/'independent_net.py').write_text(header+'\n'+src,encoding='utf-8')
