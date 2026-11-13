import re, collections
from pathlib import Path

f = Path(r'generate_trans/folds/hosts_bt31/trans/s38584t100__injalpha_d1_s42__ys_abc.v')
cell = re.compile(r'^\s*([A-Za-z][\w]*)\s+(\\?\S+)\s*\(')
skip = {'module', 'wire', 'reg', 'input', 'output', 'inout', 'assign', 'endmodule'}
types = collections.Counter(); ops = collections.Counter(); n_assign = 0
for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
    m = cell.match(line)
    if m and m.group(1) not in skip:
        types[m.group(1)] += 1
        continue
    s = line.strip()
    if s.startswith('assign'):
        n_assign += 1
        for op, name in (('&', 'AND'), ('|', 'OR'), ('^', 'XOR'), ('~', 'INV'), ('?', 'MUX')):
            if op in s:
                ops[name] += 1
print('cell types', len(types))
print(types.most_common(20))
print('assign lines', n_assign)
print('assign operator counts', dict(ops))
