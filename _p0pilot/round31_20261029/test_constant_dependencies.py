"""Exhaustively compare full/pruned generated fixture logic without SAT."""
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'round27_20261027'))
import k4_fast_support as F

def evaluate(code,env):
    values={}
    for bit,expr in re.findall(r'assign b(\d+)=(.*);',code):
        expr=re.sub(r"1'b([01])",r'\1',expr)
        expr=re.sub(r'env\[(\d+)\]',lambda m:str((env>>int(m[1]))&1),expr)
        expr=re.sub(r'\bb(\d+)\b',lambda m:str(values[int(m[1])]),expr)
        if '?' in expr:
            cond,rest=expr.split('?');yes,no=rest.split(':')
            expr=f'({yes} if {cond} else {no})'
        values[int(bit)]=eval(expr,{'__builtins__':{}},{})&1
    return values

lines=['wire b2,b3,b4,b5,b6,b7,b8;', 'assign b2=env[0];','assign b7=env[1];',
       "assign b3=b2&1'b0;", "assign b4=b7|1'b1;",
       "assign b5=b2?1'b0:1'b1;", 'assign b6=b2^b7;', 'assign b8=~b6;']
checks=0
for target in (3,4,5,6,8):
    chunk=[dict(target_bit=target,cut_bits=[2,7])]
    code=F.pruned_model(F.compile_logic(lines),2,chunk,lambda b:f'b{b}')
    for env in range(4):
        assert evaluate(code,env)[target]==evaluate('\n'.join(lines),env)[target]
        checks+=1
print(f'PASS: {checks} exhaustive full/pruned output comparisons; no solver invoked')
