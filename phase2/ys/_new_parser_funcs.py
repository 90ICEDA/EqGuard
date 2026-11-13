def getprimlist(linelist):
    """取每个 netlist 的 PI/PO 名 ✓（兼容老网表与 yosys 产物 ✓）。

    原版按"空格切 3 次"解析 `input`/`output` ✗ —— 只认 `input <w> <name>, ...` 的老格式 ✗；
    yosys 写出的是 `input sys_clk;` / `output [7:0] rec_dataH;` ✗ → 切不动 ✗
    （2026-10-17 实测：v3 的 x 里 4 个结构位中有 2 位几乎恒 0 ✗）。
    """
    priminlistlist = []
    primoutlistlist = []

    linelistflat = flatten(linelist)

    for lines in linelistflat:
        priminlist = ["1'b1"]
        primoutlist = []
        for l in lines:
            s = l.strip()
            m = re.match(r'^(input|output|inout)\b\s*(?:\[([^\]]*)\])?\s*([^;]+);', s)
            if not m:
                continue
            kind, rng, body = m.group(1), m.group(2), m.group(3)
            names = []
            for part in body.split(','):
                part = part.strip()
                if not part:
                    continue
                mm = re.match(r'^([A-Za-z_$\\][\w$\\]*)', part)
                if mm:
                    names.append(mm.group(1))
            if rng:
                nums = re.findall(r'\d+', rng)
                if len(nums) == 2:
                    hi, lo = int(nums[0]), int(nums[1])
                    names = [f"{n}[{i}]" for n in names
                             for i in range(min(hi, lo), max(hi, lo) + 1)]
            if kind == 'input':
                priminlist.extend(names)
            else:
                primoutlist.extend(names)
        priminlistlist.append(priminlist)
        primoutlistlist.append(primoutlist)

    return priminlistlist, primoutlistlist


def fixassigns(linelist):
    """把 `assign lhs = rhs;` 折成别名映射 ✓（两遍：先收集 → 传递闭包 → 再整行替换 ✓）。

    原版写死 `split(' ', 1)` 三次 ✗ —— 只认 `assign <w> <name> = <expr>` ✗；
    yosys 的 `assign \\U14.A1 = \\U106.A1 ;` 会直接 ValueError ✗（或被跳过 ✗），
    于是 `\\U127.Y` 这类**端口展平网**永远接不上 ✗（实测 v3 的 log1p(#in) 均值 0.14 vs 老 fold 1.32 ✗）。
    """
    ret = []
    for split in linelist:
        subret = []
        for lines in split:
            amap = {}
            rest = []
            for l in lines:
                m = re.match(r'^\s*assign\s+(.+?)\s*=\s*(.+?)\s*;\s*$', l)
                if m and not m.group(1).strip().startswith('{'):
                    amap[m.group(2).strip()] = m.group(1).strip()
                else:
                    rest.append(l)
            for _ in range(4):                    # 传递闭包：A=B; B=C → A=C
                amap = {k: amap.get(v, v) for k, v in amap.items()}
            out = []
            for l in rest:
                for key, val in amap.items():
                    if key in l:
                        l = re.sub(r'(?<![\w.])' + re.escape(key) + r'(?![\w.])', val, l)
                out.append(l)
            subret.append(out)
        ret.append(subret)
    return ret


def _split_ports(body: str):
    """按**顶层**逗号切端口（括号/花括号内的逗号不算 ✓）。"""
    out, buf, depth = [], [], 0
    for ch in body:
        if ch in '({[':
            depth += 1
        elif ch in ')}]':
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            out.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append(''.join(buf))
    return [s for s in (p.strip() for p in out) if s]


def getlineinfo(line):
    """解析一行实例化语句 ✓（兼容老网表与 yosys 产物 ✓）。

    原版正则只允许 `[\\/a-zA-Z-0-9_\\[\\]]` ✗ → **连接名里的 `.` 与 `$` 被截断** ✗
    （`\\U127.Y` → `\\U127` ✗ → 连错线 ✗），且不允许 `$_AND_` 这类内部单元 ✗。
    """
    line = re.sub(' +', ' ', line.replace('\n', '').lstrip())
    m = re.match(r'([^\s]+)\s+([^\s]+)\s*\((.*)\)\s*;', line)
    if not m:
        raise ValueError(f'bad instance line: {line[:100]}')
    gatetype, instancename, body = m.group(1), m.group(2), m.group(3)
    label = instancename
    portnames, connectionnames = [], []
    for part in _split_ports(body):
        z = part.replace(' ', '')
        zz = re.match(r'\.([^\s(]+)\(\s*(.*?)\s*\)$', z)
        if not zz:
            portnames.append(f'_{len(portnames)}')     # 位置连接（原语）：占位名
            connectionnames.append(z)
            continue
        portnames.append(zz.group(1))
        connectionnames.append(zz.group(2))
    return (gatetype, gatetype, instancename, label, portnames, connectionnames)
