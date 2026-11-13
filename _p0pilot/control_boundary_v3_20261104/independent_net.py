import re,collections
from phase2.ys import netlist_feats as NF
def norm(s):return s.strip().lstrip('\\')
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

def raw_network(path,lib):
 """Independent scalar-cell/pin network with bitwise wire aliases and output-driver seeds."""
 text=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)','',path.read_text(encoding='utf-8'),flags=re.S);stmts=[s.strip() for s in text.split(';') if s.strip()];ranges={};outputs=[];assign=[];cells={}
 def parts(s):
  aa=[];start=0;depth=0
  for i,ch in enumerate(s):
   depth+=int(ch in '{(')-int(ch in '})')
   if ch==',' and depth==0:aa.append(s[start:i].strip());start=i+1
  aa.append(s[start:].strip());assert depth==0;return aa
 def bits(s):
  s=s.strip()
  if s.startswith('\\'):
   assert not re.search(r'\s',norm(s));return [norm(s)]
  if s.startswith('{') and s.endswith('}'):
   body=s[1:-1];rep=re.fullmatch(r'\s*(\d+)\s*\{(.*)\}\s*',body,re.S)
   return bits('{'+rep[2]+'}')*int(rep[1]) if rep else [q for p in parts(body) for q in bits(p)]
  lit=re.fullmatch(r"(\d+)'([bBoOdDhH])([\da-fA-FxXzZ_]+)",s)
  if lit:
   w=int(lit[1]);ds=lit[3].replace('_','').lower();b=lit[2].lower()
   if b!='b':
    if any(q in ds for q in 'xz'):
     assert len(set(ds))==1;ds=ds[0]*w
    else:ds=bin(int(ds,{'o':8,'d':10,'h':16}[b]))[2:]
   return ['#'+v for v in ds.zfill(w)[-w:]]
  if s in ['0','1']:return ['#'+s]
  m=re.fullmatch(r'([\w$./]+)\[\s*(\d+)\s*:\s*(\d+)\s*\]',s)
  if m:
   hi,lo=int(m[2]),int(m[3]);return [f'{m[1]}[{i}]' for i in range(hi,lo+(1 if lo>=hi else -1),1 if lo>=hi else -1)]
  assert re.fullmatch(r'[\w$./]+(?:\[\d+\])?',s),('unsupported alias expression',path,s)
  return ranges.get(s,[s])
 for st in stmts:
  m=re.match(r'^(input|output|inout|wire|reg)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*(.*)$',st,re.S)
  if m:
   kind,high,low,body=m.groups()
   for n in parts(body):
    n=norm(n)
    if high is not None:
     hi,lo=int(high),int(low);ranges[n]=[f'{n}[{i}]' for i in range(hi,lo+(1 if lo>=hi else -1),1 if lo>=hi else -1)]
    if kind in ['output','inout']:outputs.append(n)
   continue
  if st.startswith('assign '):
   m=re.fullmatch(r'assign\s+(.+?)\s*=\s*(.+)',st,re.S);assert m;assign.append((m[1],m[2]));continue
  if re.match(r'^(module|endmodule)\b',st):continue
  m=re.fullmatch(r'(\w+)\s+(\\\S+|[^\s(]+)\s*\((.*)\)',st,re.S);assert m,st[:100];typ,name,body=m.groups();assert typ in lib;con=[]
  for s in parts(body):
   mm=re.fullmatch(r'\.\s*(\w+)\s*\((.*)\)',s,re.S);assert mm
   if not mm[2].strip():continue
   nets=bits(mm[2]);assert len(nets)==1;assert mm[1] in lib[typ]['inputs']+lib[typ]['outputs'];con.append((mm[1],nets[0]))
  assert norm(name) not in cells;cells[norm(name)]=(typ,con)
 par={}
 def find(x):
  while x in par and par[x]!=x:par[x]=par.get(par[x],par[x]);x=par[x]
  return x
 expressions=[]
 for a,b in assign:
  aa=bits(a)
  try:bb=bits(b)
  except AssertionError:
   assert len(aa)==1;expressions.append((aa[0],b));continue
  assert len(aa)==len(bb),(a,b)
  for x,y in zip(aa,bb):
   xx,yy=find(x),find(y)
   if xx!=yy:par[max(xx,yy)]=min(xx,yy)

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
 po={find(n) for o in outputs for n in bits(o)};drivers=collections.defaultdict(set);cons=collections.defaultdict(set);pins={}
 for name,(typ,cc) in cells.items():
  pins[name]=(typ,[(p,find(n)) for p,n in cc])
  for p,n in cc:
   (drivers if p in lib[typ]['outputs'] else cons)[find(n)].add(name)
 succ={n:set() for n in cells};pred={n:set() for n in cells};pocells=set()
 for n,owners in drivers.items():
  if n in po:pocells.update(owners)
  for u in owners:
   for v in cons[n]:succ[u].add(v);pred[v].add(u)
 reachable=set(pocells);queue=collections.deque(pocells)
 while queue:
  v=queue.popleft()
  for u in pred[v]:
   if u not in reachable:reachable.add(u);queue.append(u)
 return dict(cells=cells,pins=pins,succ=succ,pred=pred,reachable=reachable,po=po,pocells=pocells,drivers=drivers,cons=cons,find=find,assigns=len(assign),virtual_names=virtual_names)
