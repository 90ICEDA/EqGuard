import re

def strip(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)', '', text, flags=re.S)

def parts(s):
    aa, start, depth = [], 0, 0
    for i, ch in enumerate(s):
        depth += int(ch in '{(') - int(ch in '})')
        if ch == ',' and depth == 0:
            aa.append(s[start:i].strip()); start = i + 1
    aa.append(s[start:].strip())
    return aa

def declared_ports(text):
    pi, po = set(), set()
    for st in [x.strip() for x in strip(text).split(';') if x.strip()]:
        m = re.match(r'^(input|inout|output)\b(.*)$', st, re.S)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2).strip()
        rng = re.match(r'^\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*(.*)$', rest, re.S)
        print('DBG', repr(st), kind, repr(rest), rng.groups() if rng else None)
        if rng:
            hi, lo, body = int(rng.group(1)), int(rng.group(2)), rng.group(3)
            step = 1 if hi >= lo else -1
            names = [f'{n}[{i}]' for n in parts(body) for i in range(hi, lo + step, step)]
        else:
            names = parts(rest)
        print('  names', names)
        tgt = pi if kind in ('input', 'inout') else po
        for n in names:
            n = n.strip().lstrip('\\')
            if n:
                tgt.add(n)
    return pi, po

print(declared_ports('input [3:0] a; output o;'))
