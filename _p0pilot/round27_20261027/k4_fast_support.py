"""Pure model formatting from one previously validated native logic expansion."""
import re

def compact_display(script):
    lines=[]
    for line in script.splitlines():
        if line.startswith('sat ') and '-dump_json' not in line:
            match=re.search(r'-prove target\[(\d+)\]',line)
            if match is None:raise ValueError('Unexpected native query')
            i=match[1];line+=f' -show pattern -show premise[{i}] -show target[{i}]'
        lines.append(line)
    return '\n'.join(lines)+'\n'

def compile_logic(lines):
    assignments=[];parents={}
    for line in lines[1:]:
        match=re.fullmatch(r'assign b(\d+)=(.*);',line)
        if match is None:raise ValueError('Unexpected native assignment syntax')
        bit=int(match[1]);assert bit not in parents
        # A Verilog literal such as 1'b0 contains a word-boundary before b0,
        # but it is a constant, not the native signal named b0.
        parents[bit]=tuple(map(int,re.findall(r"(?<![\w'])b(\d+)\b",match[2])))
        assignments.append((bit,line))
    return assignments,parents

def pruned_model(compiled,width,records,bitref):
    assignments,parents=compiled
    needed=set();stack=[b for r in records for b in [r['target_bit'],*r['cut_bits']] if isinstance(b,int)]
    while stack:
        bit=stack.pop()
        if bit in needed:continue
        if bit not in parents:raise ValueError(f'Undriven required bit {bit}')
        needed.add(bit);stack.extend(parents[bit])
    lines=['wire '+','.join(bitref(b) for b in sorted(needed))+';']+[line for bit,line in assignments if bit in needed]
    return model_from_logic(lines,width,records,bitref)

def model_from_logic(lines, width, records, bitref):
    n=len(records)
    code=[f'module check(input [{width-1}:0] env,input [3:0] pattern,',
          f'output [{n-1}:0] premise,output [{n-1}:0] target);']+lines
    for i,r in enumerate(records):
        k=len(r['cut_bits']);cut='{'+','.join(bitref(b) for b in reversed(r['cut_bits']))+'}'
        code += [f'assign premise[{i}]=({cut}==pattern[{k-1}:0]);',
                 f'assign target[{i}]={bitref(r["target_bit"])};']
    return '\n'.join(code+['endmodule'])+'\n'
