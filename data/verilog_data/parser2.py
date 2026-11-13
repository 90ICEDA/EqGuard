import re
import scipy
import numpy as np
import networkx as nx
import os
import pathlib
import json
import pandas as pd
from scipy.sparse import csr_matrix, lil_matrix, save_npz
import argparse


def flatten(l):
    return [item for sublist in l for item in sublist]

def getverilogs(path='./', sub_folder='orig'):
    folder = os.path.join(path, sub_folder)
    if not os.path.exists(folder):
        return []
    # 获取目录下所有 .v 文件并排序
    v_files = sorted([os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.v')])
    return v_files

def myreadlines(f, newline):
  buf = ""
  while True:
    while newline in buf:
        pos = buf.index(newline)
        yield buf[:pos]
        buf = buf[pos + len(newline):]
    chunk = f.read(4096)
    if not chunk:
        yield buf
        break
    buf += chunk

def readlogs(verilog_list):
    ret = []
    for i in verilog_list:
        temp = []
        with open(i) as f:
            for l in myreadlines(f, ';'):
                temp.append(l)
        ret.append(temp)
    return ret

def seekword(word, lines):
    line = next(line for line in lines if word in line)
    return line

def getindices(word, lines):
    indices = []
    for i, j in enumerate(lines):
        if word in j:
            indices.append(i)
    return indices

def getmoduleinfo(path = './'):
    moduleinfo = []
    with open(path + 'verilog_lib.v') as f:
        temp = ''
        copy = False
        for line in f:
            m = re.match(r"\s*\n", line)
            if m:
                continue
            if 'module' == line.split(None, 1)[0]: #gets first word
                temp += line
                copy = True
            elif 'endmodule' == line.split(None, 1)[0]:
                temp = temp.replace('\n', '')
                moduleinfo.append(temp)
                temp = ''
                copy = False
            elif copy:
                temp+= line
    return moduleinfo


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
            m = re.match(r'^(input|output|inout)\b\s*(?:\[([^\]]*)\])?\s*(.+?)\s*;?\s*$', s)
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

_TOK = re.compile(r'[\\\w.\[\]$]+')


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
                m = re.match(r'^\s*assign\s+(.+?)\s*=\s*(.+?)\s*;?\s*$', l)
                if not m:
                    rest.append(l)
                    continue
                lhs, rhs = m.group(1).strip(), m.group(2).strip()
                if lhs.startswith('{'):                 # 左值拼接（罕见）→ 保留原行 ✓
                    rest.append(l)
                elif rhs.startswith('{') and rhs.endswith('}'):
                    # **拼接右值**：`assign out = { a, b, c };` ✓
                    # 早先被整体当"别名"丢掉 ✗ → out 与 a/b/c 之间少 8 条边 ✗（dev4: 109/325 视图各 1 处 ✗）
                    # 现在把每个元素都记成别名 → `out` ✓（节点层面等价于"这些 bit 都驱动 out" ✓）
                    for el in rhs[1:-1].split(','):
                        el = el.strip()
                        if el and not el.startswith("'"):
                            amap[el] = lhs
                else:
                    amap[rhs] = lhs
            for _ in range(4):                    # 传递闭包：A=B; B=C → A=C
                amap = {k: amap.get(v, v) for k, v in amap.items()}
            out = rest
            if amap:
                # 用「整 token 查表」代替「N 个别名的正则交替」✓：
                # 交替版本对每个位置都要试 N 个分支 ✗（N≈几百 → 每行 ~1e5 次比较 ✗）。
                a2 = {k: v for k, v in amap.items() if _TOK.fullmatch(k)}
                if a2:
                    out = [_TOK.sub(lambda m, mp=a2: mp.get(m.group(0), m.group(0)), l)
                           for l in rest]
            subret.append(out)
        ret.append(subret)
    return ret

def getinfo(line):
    # 1. 提取模块名：支持字母、数字和下划线
    # 使用 re.search 比 re.match 更稳健
    name_match = re.search(r'module\s+([a-zA-Z0-9_]+)', line)
    if not name_match:
        return ["Unknown", None, None]
    
    name = name_match.group(1)

    # 2. 提取所有 input 块内容
    # 匹配从 'input' 开始到 ';' 结束的所有字符
    input_matches = re.findall(r'input\s+([^;]+);', line)
    all_inputs = []
    for match in input_matches:
        # 处理可能的位宽 [7:0]
        clean_match = re.sub(r'\[.*?\]', '', match)
        # 按逗号分割，并清理每个引脚名的空格
        pins = [p.strip() for p in clean_match.split(',') if p.strip()]
        all_inputs.extend(pins)

    # 3. 提取所有 output 块内容
    output_matches = re.findall(r'output\s+([^;]+);', line)
    all_outputs = []
    for match in output_matches:
        clean_match = re.sub(r'\[.*?\]', '', match)
        pins = [p.strip() for p in clean_match.split(',') if p.strip()]
        all_outputs.extend(pins)

    # 如果没搜到引脚，返回 None 保持与原逻辑兼容
    res_in = all_inputs if all_inputs else None
    res_out = all_outputs if all_outputs else None

    return (name, res_in, res_out)

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

    性能：**不要**用 `\\((.*)\\)\\s*\\)?\\s*;?$` ✗ —— 长行上回溯是 O(n²) ✗
    （实测 3.5M 实例的 TRANS 域跑 28 min 仍未完 ✗）。这里用 `find/rfind` 做线性切分 ✓。
    """
    s = re.sub(' +', ' ', line.replace('\n', '').lstrip()).rstrip()
    i = s.find('(')
    if i <= 0:
        raise ValueError(f'bad instance line: {s[:100]}')
    head = s[:i].split()
    if len(head) < 2:
        raise ValueError(f'bad instance line: {s[:100]}')
    gatetype, instancename = head[0], head[1]
    j = s.rfind(')')
    body = s[i + 1:j] if j > i else s[i + 1:]
    body = body.rstrip()
    while body.count(')') > body.count('('):     # 只削掉多余的右括号（`(...) ) ` 这种 ✓）
        body = body[:-1].rstrip()
    label = instancename
    portnames, connectionnames = [], []
    for part in _split_ports(body):
        z = part.replace(' ', '')
        k = z.find('(')
        if z.startswith('.') and k > 0:
            portnames.append(z[1:k])
            connectionnames.append(z[k + 1:-1] if z.endswith(')') else z[k + 1:])
        else:
            portnames.append(f'_{len(portnames)}')     # 位置连接（原语）：占位名
            connectionnames.append(z)
    return (gatetype, gatetype, instancename, label, portnames, connectionnames)
def parse_modules(module_list):
    modules = dict()
    for i in module_list:
        name, inp, out = getinfo(i)
        modules[name] = inp, out
    return modules

def clean_1(lines):
    for l in range(0,len(lines)):
        if 'SDFFX1' in lines[l] and '.QN()' in lines[l]:
            lines[l] = re.sub(',\s*.QN\(\)', '',lines[l])
            lines[l] = lines[l].replace('SDFFX1 ', 'SDFFX12 ')
        if '//' in lines[l]:
            lines[l] = re.sub('\n*//[^\n]*\n', '', lines[l])
        lines[l].replace('\n', '')

def load_gate_full_to_simplified_mapping(path='./gate_full_to_simplified_mapping.json'):
    with open(path, 'r') as f:
        raw_data = json.load(f)

    if isinstance(raw_data, list):
        mapping = {item['full_gate_name']: item['simplified_gate_type'] for item in raw_data}
        return mapping
    
    if isinstance(raw_data, dict):
        if 'gate_full_to_simplified_mapping' in raw_data:
            return raw_data['gate_full_to_simplified_mapping']
        return raw_data
        
    raise TypeError(f"Invalid JSON format in {path}. Expected a list of mappings or a dictionary.")

    return raw

def load_gatelookup(path='./gatelookup_recommended.json'):
    with open(path, 'r') as f:
        raw = json.load(f)

    if isinstance(raw, dict) and 'gatelookup' in raw:
        raw = raw['gatelookup']

    if not isinstance(raw, dict):
        raise TypeError(f"Invalid gatelookup format in {path}")

    return {k: int(v) for k, v in raw.items()}

def parse_lines(lines):
    gates = set() #universal set

    nodeslistlist = list() #universal
    infolistlist = []  #universal
    indexlistlist = [] #universal

    trainindices = [] 
    valindices = []
    testindices = []

    i = 0
    for split, nets in enumerate(lines):
        nodeslist = [] #universal
        infolist = []  #universal
        index = None #per file
        indexlist = [] #universal
        for net in nets:
            nodes = dict()
            info = []
            for l in net:
                if l == '' or '//' in l or l == '\n':
                    continue
                x = getlineinfo(l)
                nodes[x[2]] = i
                gates.add(x[1])
                info.append(x)
                if split == 0:
                    trainindices.append(i)
                if split == 1:
                    valindices.append(i)
                if split == 2:
                    testindices.append(i)
                i = i + 1
            infolist.append(info)
            index = {v: k for k, v in nodes.items()}
            indexlist.append(index)
            nodeslist.append(nodes)
        nodeslistlist.append(nodeslist)
        infolistlist.append(infolist)
        indexlistlist.append(indexlist)

    nodeslistlist = flatten(nodeslistlist)
    infolistlist = flatten(infolistlist)
    indexlistlist = flatten(indexlistlist) 

    return gates, nodeslistlist, infolistlist, indexlistlist, (trainindices, valindices, testindices)

def generate_lookup(infolist, modules):
    lookuplist = []
    for info in infolist:
        lookup = dict()
        for i, x in enumerate(info):
            instancename = x[0]
            portnames = x[4]
            connectionnames = x[5]




            inp_ports = set(modules[instancename][0]) if modules[instancename][0] else set()
            for q in range(len(portnames)):
                if portnames[q] in inp_ports:
                    connection = connectionnames[q]
                    if connection in lookup:
                        lookup[connection].append(i)
                    else:
                        lookup[connection] = [i]
        lookuplist.append(lookup)

    return lookuplist

# provenance 覆盖：A4 系注入门名（U0T1/U0P0/...）不含 'trojan'，按注入记录补标签
PROV_LABELS = {}  # view_stem -> set(instance names)


def connect(shape, infolist, lookuplist, modules, train_indices):
    shape = int(shape)                       # ✓ 兜底：任何上游给 float 都不崩（scipy 只收 int ✗）
    adj = lil_matrix((shape, shape), dtype=int) 
    adj_train = lil_matrix((shape, shape), dtype=int)
    directed_edges = []  
    
    class_map = dict()
    membership = dict()
    num_neighbs = np.zeros(shape)

    i = 0
    netlist_idx = 0
    train_idx_set = set(train_indices)

    # --- ### DEBUG: 初始化统计变量 ---
    total_skipped_no_module = 0
    total_skipped_no_output = 0
    total_edges_found = 0
    # -------------------------------

    for info, lookup in zip(infolist, lookuplist):
        offset = i
        for x in info:
            instancename = x[0] 
            
            if 'trojan' in x[3].lower():
                class_map[str(i)] = 1
            else:
                class_map[str(i)] = 0

            if instancename not in modules:
                total_skipped_no_module += 1
                if total_skipped_no_module < 5:
                    print(f"DEBUG: 库中缺少门类型 '{instancename}' (网表中的第一个词)")
                membership[i] = netlist_idx
                i += 1
                continue

            inp_ports, out_ports = modules[instancename]
            
            # --- 核心修改点 1: 确保输出列表是集合，方便精确匹配 ---
            out_ports_set = set(out_ports) if out_ports else set()
            if not out_ports_set:
                total_skipped_no_output += 1

            portnames = x[4]        
            connectionnames = x[5]  

            for q in range(len(portnames)):
                pin = portnames[q]
                
                # --- 核心修改点 2: 将 any(...in...) 改为精确匹配 ---
                # 这样 pin 为 "Q" 时就不会误匹配到库里的 "QN"
                is_output = pin in out_ports_set
                
                if is_output:
                    conn_name = connectionnames[q]
                    # 使用 if conn_name in lookup 代替 try/except，逻辑更清晰
                    if conn_name in lookup:
                        neighbors = lookup[conn_name]
                        for num in neighbors:
                            target_node = num + offset
                            # 建立边
                            adj[i, target_node] = 1
                            adj[target_node, i] = 1
                            directed_edges.append((i, target_node))
                            
                            num_neighbs[i] += 1
                            num_neighbs[target_node] += 1
                            total_edges_found += 1

                            if i in train_idx_set and target_node in train_idx_set:
                                adj_train[i, target_node] = 1
                                adj_train[target_node, i] = 1
                
                # 保留您的 DEBUG 辅助判定
                elif q == 0 and i == offset: 
                    print(f"DEBUG: 实例 {x[2]} 的引脚 {pin} 未被识别为输出。库定义输出为: {out_ports}")
            
            membership[i] = netlist_idx
            i += 1
        netlist_idx += 1
        
    print(f"\n--- 调试报告 ---")
    print(f"处理节点总数: {i}")
    print(f"因库中无定义而跳过的门: {total_skipped_no_module}")
    print(f"因库中无输出端口定义的门: {total_skipped_no_output}")
    print(f"成功建立的边(连接)总数: {total_edges_found}")
    print(f"----------------\n")
    
    return adj, adj_train, class_map, membership, num_neighbs, directed_edges


def generate_features(numnodes, gatelookup, gate_full_to_simplified, modules, infolist, priminpslist, primoutslist, membership, num_neighbs): #! need to fix as priminps is now list of lists!!!
    connected_to_prim_out = set()
    connected_to_prim_inp = set()

    featsleft = np.zeros((numnodes, len(gatelookup)))
    featsright = np.zeros((numnodes, 4))
    info = [item for sublist in infolist for item in sublist]
    print(featsleft.shape[0])
    for i in range(featsleft.shape[0]):
        print(i, end='\r')
        priminps = priminpslist[membership[i]]
        primouts = primoutslist[membership[i]]


        full_gate_type = info[i][0]
        simplified_gate_type = gate_full_to_simplified.get(full_gate_type)

        if simplified_gate_type is None:
            raise KeyError(f"Gate type '{full_gate_type}' not found in gate_full_to_simplified_mapping.json")

        if simplified_gate_type not in gatelookup:
            raise KeyError(f"Simplified gate type '{simplified_gate_type}' not found in gatelookup_recommended.json")

        featsleft[i][gatelookup[simplified_gate_type]] = 1

        ins = modules[info[i][0]][0]
        outs = modules[info[i][0]][1]
        featsright[i][0] = np.log1p(len(ins)) if ins else 0
        featsright[i][1] = np.log1p(num_neighbs[i])
        connections = info[i][5]
        for conn in connections:
            if conn in priminps:
                connected_to_prim_inp.add(i)
                featsright[i][2] = 1
            if conn in primouts:
                connected_to_prim_out.add(i)
                featsright[i][3] = 1

    feats = np.concatenate((featsleft, featsright), axis = 1)

    os.makedirs("./data/not_for_train", exist_ok=True)   # ✓ 新 fold 目录下没有该目录 → 自动建 ✓（否则 savetxt 崩 ✗）
    np.savetxt("./data/not_for_train/featsleft.txt", featsleft, fmt='%1.1f')
    np.savetxt("./data/not_for_train/featsright.txt", featsright, fmt='%1.1f')

    return feats, connected_to_prim_inp, connected_to_prim_out


def get_neighbs(graph, nodes):
    ret = []
    for i in nodes:
        ret += list(graph.neighbors(i))

    return ret

def calculate_distances(graph, current, label, output, pos):
    neighbs = set()

    for n in get_neighbs(graph, current):
        if output[n, pos] == -1:
            neighbs.add(n)
            output[n, pos] = label
    
    current = list(neighbs)
    if len(current) > 0:
        output = calculate_distances(graph, current, label + 1, output, pos)
    
    return output

def save_domain_output(indices, adj, adj_train, class_map, feats, prefixes, file_ids, suffix):
    path = './data/for_train/'
    os.makedirs(path, exist_ok=True)
    metadata = {
        'prefixes': prefixes,
        'file_ids': file_ids
    }
    with open(f'{path}metadata_{suffix}.json', 'w') as f:
        json.dump(metadata, f)
    save_npz(f'{path}adj_full_{suffix}.npz', adj.tocsr())
    with open(f'{path}class_map_{suffix}.json', 'w') as f: json.dump(class_map, f)
    with open(f'{path}role_{suffix}.json', 'w') as f:
        json.dump({'tr': indices[0], 'va': indices[1], 'te': indices[2]}, f)
    np.save(f'{path}feats_{suffix}.npy', feats)

def get_circuit_prefix(filename):
    """从文件名提取基础名，例如 s38584t100.v -> s38584"""
    name = os.path.basename(filename).replace(".v", "")
    # 或者匹配 '_tr', '_equiv' 之前的内容
    match = re.search(r'^(.+?)(?=t\d|_tr|tr\d|equiv)', name)
    
    if match:
        prefix = match.group(1).rstrip('_') # 去掉末尾可能残留的下划线
        return prefix
    
    # 如果没匹配到规律，按原样返回（例如只叫 rs232.v 的情况）
    return name

def get_names_only(verilog_list):
    """
    轻量级解析：只获取所有网表中的实例名顺序
    """
    all_names_global = {}
    current_idx = 0
    
    # 这里的读取逻辑必须和你 trans 脚本里的 readlogs/parse_lines 顺序完全一致
    for v_file in verilog_list:
        with open(v_file, 'r') as f:
            # 简单的正则提取实例名：GateType InstanceName (
            content = f.read()
            # 匹配 Verilog 实例名的标准模式
            # 注意：这里的正则要和你 getlineinfo 里的逻辑对应
            instances = re.findall(r'\b\w+\s+(\\?\w+)\s*\(', content)
            
            for name in instances:
                # 去除转义斜杠
                clean_name = name.lstrip('\\')
                all_names_global[clean_name] = current_idx
                current_idx += 1
    return all_names_global

    # --- 2. 封装核心处理流程 ---
def _csr_from_edges(edges, n, reverse=False):
    """有向边表 → scipy CSR 邻接（`reverse=True` 返回**前驱**图）✓。"""
    from scipy.sparse import csr_matrix
    e = np.asarray(edges, dtype=np.int64)
    if e.size == 0:
        return csr_matrix((n, n), dtype=np.int32)
    r, c = (e[:, 1], e[:, 0]) if reverse else (e[:, 0], e[:, 1])
    return csr_matrix((np.ones(len(r), dtype=np.int32), (r, c)), shape=(n, n))


def _bfs_levels(csr, sources):
    """CSR 上的 BFS 层数；不可达 = −1 ✓（比 networkx 逐点 BFS 快很多 ✓）。"""
    n = csr.shape[0]
    lv = np.full(n, -1, dtype=np.int32)
    src = np.asarray(sorted({int(s) for s in sources if 0 <= int(s) < n}), dtype=np.int64)
    if src.size == 0:
        return lv
    lv[src] = 0
    frontier = src
    depth = 1
    indptr, indices = csr.indptr, csr.indices
    while frontier.size:
        parts = [indices[indptr[u]:indptr[u + 1]] for u in frontier]
        parts = [p for p in parts if p.size]
        if not parts:
            break
        nxt = np.unique(np.concatenate(parts))
        nxt = nxt[lv[nxt] < 0]
        if nxt.size == 0:
            break
        lv[nxt] = depth
        frontier = nxt
        depth += 1
    return lv


def _two_hop_log(csr):
    """log1p(2 跳内可达的**不同**节点数，不含自身) ✓。

    早先用 `nx.bfs_tree(depth_limit=2)` 逐点建树 ✗（3.5M 次 Python 调用 → 重建极慢 ✗）；
    这里直接在 CSR 上取"邻接的邻接"再 `np.unique` ✓（时钟这种大扇出点也就几十 k 元素 ✓）。
    """
    n = csr.shape[0]
    out = np.zeros(n, dtype=np.float64)
    indptr, indices = csr.indptr, csr.indices
    for i in range(n):
        a = indices[indptr[i]:indptr[i + 1]]
        if a.size == 0:
            continue
        parts = [indices[indptr[u]:indptr[u + 1]] for u in a]
        parts = [p for p in parts if p.size]
        if not parts:
            continue
        u2 = np.unique(np.concatenate(parts))
        cnt = u2.size - (1 if np.any(u2 == i) else 0)
        out[i] = np.log1p(max(cnt, 0))
    return out.reshape(-1, 1)


def _scc_labels(edges, n):
    """强连通分量标号（C 实现 ✓）；返回 (labels[N], sizes[n_comp]) ✓。"""
    from scipy.sparse.csgraph import connected_components
    g = _csr_from_edges(edges, n)
    n_comp, labels = connected_components(g, directed=True, connection="strong")
    sizes = np.bincount(labels, minlength=n_comp)
    return labels, sizes


def topo_features(numnodes, directed_edges, prim_inp_nodes, prim_out_nodes, seq_nodes=None):
    """方案 A 的 6 维（`cycle_mode=contract`）✓：

      f33/f34  dist_to_PI/PO **有向**，且在 **DFF 处层级重置**（每条流水线级各自从 0 计 ✓）
      f35/f36  log1p(2-hop 扇入/扇出)，同样在 DFF 处重置 ✓
      f37/f38  in_cycle（该门是否处在**组合环**里）/ log1p(SCC 大小) ✓

    与 f29–f32 的分工：
      f29/f30 = 有向距离（全图，**不**重置）→ "全局深度"
      f31/f32 = 有向 2-hop（全图）
      f33–f36 = 同上但在 DFF 处重置 → "本流水线级内的深度/局部扇入扇出" ✓ 与之必然不同 ✓
    """
    n = int(numnodes)
    seq = set(int(x) for x in (seq_nodes or ()))

    # 前向：剪掉"进入 DFF"的边（DFF 的 D 侧不把距离带过寄存器）
    fwd_edges = [(u, v) for (u, v) in directed_edges if v not in seq]
    # 反向：剪掉"从 DFF 出发"的边（给 dist_to_PO 用同一套层级语义）
    rev_edges = [(u, v) for (u, v) in directed_edges if u not in seq]

    fwd_succ = _csr_from_edges(fwd_edges, n)
    fwd_pred = _csr_from_edges(fwd_edges, n, reverse=True)
    rev_succ = _csr_from_edges(rev_edges, n)
    rev_pred = _csr_from_edges(rev_edges, n, reverse=True)

    src_pi = set(int(x) for x in prim_inp_nodes) | seq
    src_po = set(int(x) for x in prim_out_nodes) | seq
    # 说明：本批网表里**每个 DFF 的 CK 都接 PI** ✗ → DFF 本身已是"距离 0" ✓
    # → 用 `PI∪DFF` 当源时 f33 与 f29 会 100% 相同 ✗（实测 rs232 2604 点全等 ✗）。
    # 因此这里改成「**到最近寄存器输出**」/「**到最近寄存器输入**」的距离 ✓
    #   = 流水线级**内部**的组合深度 ✓（与全局距离 f29/f30 必然不同 ✓）
    seq_arr = np.asarray(sorted(seq), dtype=np.int64)
    if seq_arr.size:
        parts = [fwd_succ.indices[fwd_succ.indptr[u]:fwd_succ.indptr[u + 1]] for u in seq_arr]
        parts = [p for p in parts if p.size]
        src_pi = set(np.unique(np.concatenate(parts)).tolist()) if parts else set()
        parts = [rev_pred.indices[rev_pred.indptr[u]:rev_pred.indptr[u + 1]] for u in seq_arr]
        parts = [p for p in parts if p.size]
        src_po = set(np.unique(np.concatenate(parts)).tolist()) if parts else set()
    d_pi = _bfs_levels(fwd_succ, src_pi).astype(np.float64)
    d_po = _bfs_levels(rev_pred, src_po).astype(np.float64)
    if seq_arr.size:
        # 寄存器自身就是"级边界" ✓ → 距离记 0 ✓（而不是 −1 ✗）
        d_pi[seq_arr] = 0.0
        d_po[seq_arr] = 0.0
    fi = _two_hop_log(fwd_pred)
    fo = _two_hop_log(rev_succ)

    # 组合环：在"剪掉 DFF 出边"的图上求 SCC（避免把时序环误判为组合环 ✓）
    labels, sizes = _scc_labels(rev_edges, n)
    self_loop = {u for (u, v) in rev_edges if u == v}
    in_cycle = np.array([1.0 if (sizes[c] > 1 or i in self_loop) else 0.0
                         for i, c in enumerate(labels)], dtype=np.float64)
    scc_size = np.log1p(sizes[labels]).astype(np.float64)
    extra = np.stack([in_cycle, scc_size], axis=1)

    return np.stack([d_pi, d_po], axis=1), fi, fo, extra

def process_domain(verilog_splits, modules, gate_mapping, gatelookup, suffix="orig",
                   cycle_mode="none"):
    print(f"\n>>> 正在处理 {suffix.upper()} 域特征提取...")
    
    # A. 读取日志
    lines = []
    for v in verilog_splits:
        lines.append(readlogs(v))
    
    priminlistlist, primoutlistlist = getprimlist(lines)
    lines = fixassigns(lines)

    for split in lines:
        for l in split:
            clean_1(l)
            wire_idx = getindices('wire', l)
            if wire_idx:
                last = wire_idx[-1]
                l[:] = l[last+1:-1]

    # B. 解析网表并生成索引
    gates, nodeslistlist, infolistlist, indexlistlist, indices = parse_lines(lines)
    numnodes = int(np.sum([len(i) for i in nodeslistlist]))   # ✓ 必须 int（scipy 拒绝 numpy.float64 ✗）

    node_prefixes = []
    node_file_ids = [] # 新增：记录具体文件名
    flatten_files = flatten(verilog_splits) # 确保这里的顺序和 parse_lines 一致
    for file_path, file_nodes in zip(flatten_files, nodeslistlist):
        prefix = get_circuit_prefix(file_path)
        file_id = os.path.basename(file_path).replace(".v", "") # 具体文件名
        
        node_prefixes.extend([prefix] * len(file_nodes))
        node_file_ids.extend([file_id] * len(file_nodes)) # 记录具体文件
    # 建立名字到全局索引的映射 (对齐的关键)
    name_to_idx_global = {}
    curr_offset = 0
    for file_nodes in nodeslistlist:
        for name in file_nodes:
            # 统一去除斜杠，防止匹配失败
            clean_name = name.lstrip('\\')
            name_to_idx_global[clean_name] = curr_offset
            curr_offset += 1

    # C. 基础特征
    lookuplist = generate_lookup(infolistlist, modules)
    adj, adj_train, class_map, membership, num_neighbs, directed_edges = connect(
        numnodes, infolistlist, lookuplist, modules, indices[0]
    )
    # D0. provenance 标签覆盖（只对 orig 侧有意义；trans 侧名字已变，覆盖不到即跳过）
    if PROV_LABELS:
        _idx = 0
        _fix = 0
        for _fp, _info in zip(flatten_files, infolistlist):
            _stem = os.path.basename(_fp).replace('.v', '')
            _extra = PROV_LABELS.get(_stem)
            for _x in _info:
                if _extra and _x[3] in _extra and class_map.get(str(_idx)) != 1:
                    class_map[str(_idx)] = 1
                    _fix += 1
                _idx += 1
        if _fix:
            print(f'    [prov-label] {suffix}: 按注入记录补正正标签 {_fix} 个')

    feats, connected_to_prim_inp, connected_to_prim_out = generate_features(
        numnodes, gatelookup, gate_mapping, modules, infolistlist, 
        priminlistlist, primoutlistlist, membership, num_neighbs
    )

    # D. 拓扑特征（方案 A：**全部有向** ✓；旧实现用的是无向图 ✗ → "到 PI 的距离"会沿逆向边乱走 ✗）
    succ = _csr_from_edges(directed_edges, numnodes)
    pred = _csr_from_edges(directed_edges, numnodes, reverse=True)
    distances = np.stack([_bfs_levels(succ, connected_to_prim_inp),
                          _bfs_levels(pred, connected_to_prim_out)], axis=1).astype(np.float64)
    fan_in_sizes = _two_hop_log(pred)
    fan_out_sizes = _two_hop_log(succ)
    feats = np.concatenate((feats, distances, fan_in_sizes, fan_out_sizes), axis=1)   # 33 维基线

    # D2. 环感知 6 维（仅 contract）→ 39 维
    #     f33/f34 = 有向距离，但**在 DFF 处层级重置**（每条流水线级从 0 计）
    #     f35/f36 = 同样重置后的 2-hop
    #     f37/f38 = in_cycle / log1p(scc_size)
    if cycle_mode == "contract":
        flat_info = [item for sublist in infolistlist for item in sublist]
        seq_nodes = {i for i, x in enumerate(flat_info)
                     if str(gate_mapping.get(x[0], x[0])).upper().startswith(("DFF", "SDFF"))}
        dist_dag, fi_dag, fo_dag, cycle_extra = topo_features(
            numnodes, directed_edges, connected_to_prim_inp, connected_to_prim_out,
            seq_nodes=seq_nodes)
        feats = np.concatenate((feats, dist_dag, fi_dag, fo_dag, cycle_extra), axis=1)
        n_cycle = int(cycle_extra[:, 0].sum())
        print(f"[INFO] cycle_mode=contract：时序边界 {len(seq_nodes)} 个；组合环内节点 {n_cycle} 个；"
              f"特征维度 {feats.shape[1]}（前 33 维与 none 完全一致 ✓）")

    # E. 保存中间结果
    save_domain_output(indices, adj, adj_train, class_map, feats, node_prefixes, node_file_ids, suffix)
    
    return name_to_idx_global, flatten(verilog_splits), class_map, nodeslistlist, flatten(infolistlist)

def verify_alignment_indices(alignment_list, nodeslist_o, files_o, nodeslist_t, files_t):
    """
    alignment_list: alignment.json 里的 [[o, t], ...]
    nodeslist_o: process_domain(..., 'orig') 返回的 nodeslistlist
    files_o: process_domain(..., 'orig') 返回的 flatten(verilog_splits)
    """
    
    def get_info(target_idx, node_dicts, file_paths):
        """根据全局索引找文件名和实例名"""
        current_offset = 0
        for i, d in enumerate(node_dicts):
            num_nodes = len(d)
            if current_offset <= target_idx < current_offset + num_nodes:
                # 找到该节点所在的文件名
                fname = os.path.basename(file_paths[i])
                # 反转字典 {name: global_idx} -> {global_idx: name}
                idx_to_name = {v: k for k, v in d.items()}
                instance_name = idx_to_name.get(target_idx, "Unknown")
                return fname, instance_name
            current_offset += num_nodes
        return "Unknown", "Unknown"

    results = []
    print(f"{'Index_O':<8} {'File_O':<20} {'Name_O':<15} | {'Index_T':<8} {'File_T':<20} {'Name_T':<15}")
    print("-" * 100)

    for o_idx, t_idx in alignment_list:
        f_o, n_o = get_info(o_idx, nodeslist_o, files_o)
        f_t, n_t = get_info(t_idx, nodeslist_t, files_t)
        
        # 判定是否跨文件（对齐错误的标志）
        # 假设原文件名 s38584t100.v 对应的变换文件包含 s38584t100 字样
        is_cross_file = f_o.replace(".v", "") not in f_t
        tag = "[WRONG!]" if is_cross_file else "[OK]"
        
        print(f"{o_idx:<8} {f_o:<20} {n_o:<15} | {t_idx:<8} {f_t:<20} {n_t:<15} {tag}")
        
        results.append({
            'Orig_Idx': o_idx, 'Orig_File': f_o, 'Orig_Name': n_o,
            'Trans_Idx': t_idx, 'Trans_File': f_t, 'Trans_Name': n_t,
            'Match_Status': "OK" if not is_cross_file else "CROSS_FILE_ERROR"
        })

    # 导出 CSV 方便慢慢看
    df = pd.DataFrame(results)
    df.to_csv("alignment_debug_report.csv", index=False)
    print("\n详细调试报告已保存至: alignment_debug_report.csv")

def generate_mapping_csv(alignment, nodes_o, info_o, files_o, nodes_t, info_t, files_t):
    import collections
    print(">>> 正在生成详细映射统计表 (mapping.csv)...")
    
    # 建立索引到文件名的快速映射
    def get_index_to_file_map(node_dicts, file_paths):
        idx_to_file = {}
        idx_to_name = {}
        curr = 0
        for i, d in enumerate(node_dicts):
            fname = os.path.basename(file_paths[i])
            for name, g_idx in d.items():
                idx_to_file[g_idx] = fname
                idx_to_name[g_idx] = name
        return idx_to_file, idx_to_name

    file_map_o, name_map_o = get_index_to_file_map(nodes_o, files_o)
    file_map_t, name_map_t = get_index_to_file_map(nodes_t, files_t)

    # 聚合对齐关系 (o_idx -> [t_idx1, t_idx2...])
    align_map = collections.defaultdict(list)
    for o_idx, t_idx in alignment:
        align_map[o_idx].append(t_idx)

    rows = []
    # 遍历所有 Orig 节点
    for o_idx in range(len(info_o)):
        mapped_t_idxs = align_map.get(o_idx, [])
        
        # 映射门详情统计
        t_ids = "/".join([str(tid) for tid in mapped_t_idxs])
        t_names = "/".join([name_map_t.get(tid, "Unknown") for tid in mapped_t_idxs])
        
        # 检查映射门是否属于同一个文件
        t_files = list(set([file_map_t.get(tid, "Unknown") for tid in mapped_t_idxs]))
        if len(t_files) > 1:
            t_file_str = "ERROR: Multi-Files (" + ",".join(t_files) + ")"
        elif len(t_files) == 1:
            t_file_str = t_files[0]
        else:
            t_file_str = "N/A"

        rows.append({
            'id号': o_idx,
            '所属网表文件名称': file_map_o.get(o_idx, "Unknown"),
            '门名称': name_map_o.get(o_idx, "Unknown"),
            '门类型': info_o[o_idx][0],
            '映射比例': f"1:{len(mapped_t_idxs)}",
            '映射门id': t_ids,
            '映射门所属网表文件名称': t_file_str,
            '映射门名称': t_names
        })

    # 输出到 CSV
    out_dir = './data/not_for_train'
    os.makedirs(out_dir, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, 'mapping.csv'), index=False, encoding='utf-8-sig')
    print(f"[完成] 映射详情已保存至 {out_dir}/mapping.csv")

def generate_mapping_csv_v2(alignment, nodes_o, info_o, files_o, nodes_t, info_t, files_t):
    import collections
    print(">>> 正在生成详细映射统计表 (按变体拆分)...")
    
    def get_maps(node_dicts, file_paths):
        idx_to_file = {}
        idx_to_name = {}
        for i, d in enumerate(node_dicts):
            fname = os.path.basename(file_paths[i])
            for name, g_idx in d.items():
                idx_to_file[g_idx] = fname
                idx_to_name[g_idx] = name
        return idx_to_file, idx_to_name

    file_map_o, name_map_o = get_maps(nodes_o, files_o)
    file_map_t, name_map_t = get_maps(nodes_t, files_t)

    # 核心：将对齐按 (o_idx, trans_file) 分组
    # key: o_idx, value: { trans_file_name: [t_idx1, t_idx2...] }
    master_map = collections.defaultdict(lambda: collections.defaultdict(list))
    for o_idx, t_idx in alignment:
        t_file = file_map_t[t_idx]
        master_map[o_idx][t_file].append(t_idx)

    rows = []
    # 遍历所有原始门
    for o_idx in range(len(info_o)):
        o_fname = file_map_o[o_idx]
        
        # 找到这个 Orig 对应的所有 Trans 文件
        # 逻辑：只要 trans 文件名以 orig 文件名（无后缀）开头
        o_base = o_fname.replace(".v", "")
        relevant_t_files = [os.path.basename(f) for f in files_t if os.path.basename(f).startswith(o_base)]
        
        for t_file in relevant_t_files:
            mapped_ts = master_map[o_idx].get(t_file, [])
            
            rows.append({
                'orig_id': o_idx,
                'orig_file': o_fname,
                'gate_name': name_map_o[o_idx],
                'gate_type': info_o[o_idx][0],
                'target_trans_file': t_file,
                'mapping_ratio': f"1:{len(mapped_ts)}",
                'trans_ids': "/".join(map(str, mapped_ts)),
                'trans_names': "/".join([name_map_t[tid] for tid in mapped_ts])
            })

    out_path = './data/not_for_train/mapping.csv'
    pd.DataFrame(rows).to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"[完成] 映射表已保存至 {out_path}")

def build_alignment_from_mappings(*, mapping_dir, trans_name_to_idx, orig_name_to_idx,
                                  nodeslistlist_orig, nodeslistlist_trans,
                                  class_map_orig, class_map_trans,
                                  require_label_match=False):
    """
    用生成器输出的 mappings/<view>.json（node_alignment: src 门 -> [dst 门]）建立 raw provenance。

    分任务1 要求：**raw provenance 建立时不能看 Trojan label**，label 只用于独立的 label transport。
    因此默认 label-free（require_label_match=False）；置 True 可复现旧的「label 相同才写入」行为。

    返回 (final_alignment, conflicts, stats)
    """
    final_alignment = []
    conflicts = []
    seen_pairs = set()
    explicit = identity = 0

    # 注意：nodeslistlist_*[i] 里的索引是**全局节点索引**（parse_lines 跨文件连续编号，已验证），
    # 因此这里直接用即可，不需要再加文件偏移。

    for t_fname_v, t_f_idx in trans_name_to_idx.items():
        map_path = os.path.join(mapping_dir, f"{t_fname_v}.json")
        if not os.path.exists(map_path):
            continue
        with open(map_path, 'r') as f:
            map_data = json.load(f)
        src_v = map_data.get("src_verilog", "").replace(".v", "")
        node_align = map_data.get("node_alignment", {}) or {}
        if src_v not in orig_name_to_idx:
            print(f"  [Skip] 映射文件 {t_fname_v}.json 指向的原始网表 {src_v} 未在 orig 文件夹找到")
            continue

        o_f_idx = orig_name_to_idx[src_v]
        curr_orig_nodes = nodeslistlist_orig[o_f_idx]
        curr_trans_nodes = nodeslistlist_trans[t_f_idx]
        covered_o = set()

        # A. 生成器给出的显式血缘映射（label-blind）
        for o_name, t_names in node_align.items():
            o_clean = o_name.lstrip('\\')
            if o_clean not in curr_orig_nodes:
                continue
            o_idx = curr_orig_nodes[o_clean]
            o_label = class_map_orig.get(str(o_idx))
            for t_name in (t_names or []):
                t_clean = str(t_name).lstrip('\\')
                if t_clean not in curr_trans_nodes:
                    continue
                t_idx = curr_trans_nodes[t_clean]
                t_label = class_map_trans.get(str(t_idx))
                if require_label_match and o_label != t_label:
                    continue
                if (o_idx, t_idx) in seen_pairs:
                    continue
                seen_pairs.add((o_idx, t_idx))
                final_alignment.append([o_idx, t_idx])
                covered_o.add(o_idx)
                explicit += 1
                if o_label != t_label:
                    conflicts.append({'o_idx': o_idx, 't_idx': t_idx,
                                      'o_label': o_label, 't_label': t_label,
                                      'file': f"{t_fname_v}.v"})

        # B. 身份映射（网表中名字未变动的门）
        for name, o_idx in curr_orig_nodes.items():
            if o_idx in covered_o or name not in curr_trans_nodes:
                continue
            t_idx = curr_trans_nodes[name]
            o_label = class_map_orig.get(str(o_idx))
            t_label = class_map_trans.get(str(t_idx))
            if require_label_match and o_label != t_label:
                continue
            if (o_idx, t_idx) in seen_pairs:
                continue
            seen_pairs.add((o_idx, t_idx))
            final_alignment.append([o_idx, t_idx])
            identity += 1
            if o_label != t_label:
                conflicts.append({'o_idx': o_idx, 't_idx': t_idx,
                                  'o_label': o_label, 't_label': t_label,
                                  'file': f"{t_fname_v}.v"})

    n_orig = sum(len(d) for d in nodeslistlist_orig)
    n_trans = sum(len(d) for d in nodeslistlist_trans)
    stats = {
        'pairs': len(final_alignment),
        'explicit_pairs': explicit,
        'identity_pairs': identity,
        'orig_nodes': n_orig,
        'trans_nodes': n_trans,
        'orig_covered': len({o for o, _ in final_alignment}),
        'trans_covered': len({t for _, t in final_alignment}),
        'label_conflicts': len(conflicts),
        'require_label_match': bool(require_label_match),
        'label_source': "instance-name contains 'trojan'",
    }
    return final_alignment, conflicts, stats


def build_label_transport(alignment, class_map_orig, class_map_trans):
    """
    独立的 label transport 步骤：把 Orig 标签沿 provenance 传播到 Trans 节点
    （1:N 映射时所有子节点继承同一标签）。返回 (transported, report)。
    """
    transported = {}
    for o_idx, t_idx in alignment:
        transported[str(t_idx)] = int(class_map_orig.get(str(o_idx), 0))
    agree = disagree = 0
    examples = []
    for t_str, lab in transported.items():
        name_lab = int(class_map_trans.get(t_str, 0))
        if name_lab == lab:
            agree += 1
        else:
            disagree += 1
            if len(examples) < 10:
                examples.append({'t_idx': int(t_str), 'transported': lab,
                                 'name_derived': name_lab})
    report = {
        'transported_nodes': len(transported),
        'agree_with_name_derived': agree,
        'disagree_with_name_derived': disagree,
        'disagree_examples': examples,
        'trojan_transported': sum(1 for v in transported.values() if v == 1),
        'trojan_name_derived': sum(1 for v in class_map_trans.values() if int(v) == 1),
    }
    return transported, report


def write_provenance_reports(out_dir, stats, conflicts, transport_report, transported_labels):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'provenance_stats.json'), 'w') as f:
        json.dump({'stats': stats, 'n_conflicts': len(conflicts),
                   'conflicts_sample': conflicts[:200]}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, 'label_transport.json'), 'w') as f:
        json.dump({'report': transport_report,
                   'trans_labels_from_orig': transported_labels}, f, indent=2)
    with open(os.path.join(out_dir, 'class_map_trans_transported.json'), 'w') as f:
        json.dump(transported_labels, f)
    print(f"[OK] provenance_stats.json / label_transport.json / "
          f"class_map_trans_transported.json -> {out_dir}")


def main():
    ap = argparse.ArgumentParser(
        description="parser2：生成 orig/trans 图数据 + label-free raw provenance + 独立 label transport")
    ap.add_argument("--require-label-match", action="store_true",
                    help="复现旧行为：alignment 只保留 label（名字派生）相同的对（默认关闭=label-free）")
    ap.add_argument("--prov-root", default="",
                    help="逗号分隔的 hosts 根（含 */provenance.json）；用于按注入记录补正正标签")
    ap.add_argument("--out-root", default="./data/for_train",
                    help="输出目录（*_orig/_trans 数据与 alignment 都写这里）")
    ap.add_argument("--views-list", default=None,
                    help="只处理清单里的 trans 视图（每行一个视图名/文件名，# 为注释）")
    ap.add_argument("--alignment-name", default="alignment.json", help="provenance 输出文件名")
    ap.add_argument("--no-backup", action="store_true", help="不备份已存在的 alignment 文件")
    ap.add_argument("--skip-debug", action="store_true",
                    help="跳过 alignment_debug_report.csv / mapping.csv（大批量视图时建议开启）")
    ap.add_argument("--cycle-mode", choices=["none", "contract"], default="none",
                    help="组合环处理：none=旧行为(33 维)；contract=SCC 收缩后算拓扑特征并回填(35 维，含 in_cycle/scc_size)")
    args = ap.parse_args()

    if getattr(args, 'prov_root', ''):
        _roots = [r.strip() for r in args.prov_root.split(',') if r.strip()]
        for _r in _roots:
            for _f in sorted(pathlib.Path(_r).glob('*/provenance.json')):
                for _rec in json.loads(_f.read_text(encoding='utf-8')):
                    if _rec.get('kind') == 'trojan' and _rec.get('new_gates'):
                        PROV_LABELS.setdefault(_rec['view'], set()).update(_rec['new_gates'])
        print(f'[prov-label] 载入 {len(PROV_LABELS)} 个 trojan 视图的注入门名（来自 {len(_roots)} 个 root）')

    moduleinfo = getmoduleinfo()
    modules = parse_modules(moduleinfo)
    gate_mapping = load_gate_full_to_simplified_mapping('./gate_full_to_simplified_mapping.json')
    gatelookup = load_gatelookup('./gatelookup_recommended.json')

    # 1. 加载文件夹
    orig_files = getverilogs(path='./', sub_folder='orig')
    trans_files = getverilogs(path='./', sub_folder='trans')
    if args.views_list:
        wanted = set()
        with open(args.views_list, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith('#'):
                    wanted.add(s)
                    wanted.add(s[:-2] if s.endswith('.v') else s)
        def _stem(p):
            b = os.path.basename(p)
            return b[:-2] if b.endswith('.v') else b
        trans_files = [f for f in trans_files if _stem(f) in wanted]
        print(f"[INFO] --views-list 过滤后 trans 视图数: {len(trans_files)}")
    if not trans_files:
        print("[ERROR] trans 视图为空，退出")
        return

    _, _, class_map_orig, nodeslistlist_orig, infolist_orig = process_domain(
        [orig_files, [], []], modules, gate_mapping, gatelookup, "orig",
        cycle_mode=args.cycle_mode)
    _, _, class_map_trans, nodeslistlist_trans, infolist_trans = process_domain(
        [trans_files, [], []], modules, gate_mapping, gatelookup, "trans",
        cycle_mode=args.cycle_mode)

    orig_name_to_idx = {os.path.basename(f).replace(".v", ""): i for i, f in enumerate(orig_files)}
    trans_name_to_idx = {os.path.basename(f).replace(".v", ""): i for i, f in enumerate(trans_files)}

    # 2. raw provenance（默认 label-free；label 只在下一步做 transport）
    print("\n>>> 建立 raw provenance（label-blind；从 mappings/*.json 的血缘 + 未变门身份）...")
    alignment, conflicts, stats = build_alignment_from_mappings(
        mapping_dir="./mappings",
        trans_name_to_idx=trans_name_to_idx,
        orig_name_to_idx=orig_name_to_idx,
        nodeslistlist_orig=nodeslistlist_orig,
        nodeslistlist_trans=nodeslistlist_trans,
        class_map_orig=class_map_orig,
        class_map_trans=class_map_trans,
        require_label_match=args.require_label_match)
    print(f"[完成] raw provenance: {stats['pairs']} 对"
          f"（显式血缘 {stats['explicit_pairs']} + 身份 {stats['identity_pairs']}）"
          f"｜orig 覆盖 {stats['orig_covered']}/{stats['orig_nodes']}"
          f"｜trans 覆盖 {stats['trans_covered']}/{stats['trans_nodes']}"
          f"｜label 冲突（仅统计，未过滤）{stats['label_conflicts']}")

    # 3. label transport（独立步骤：Orig 标签沿 provenance 传播到 Trans）
    transported, transport_report = build_label_transport(alignment, class_map_orig, class_map_trans)
    print(f"[完成] label transport: {transport_report['transported_nodes']} 个 trans 节点"
          f"｜trojan={transport_report['trojan_transported']}"
          f"（名字派生 trojan={transport_report['trojan_name_derived']}）"
          f"｜与名字派生不一致 {transport_report['disagree_with_name_derived']}")

    # 4. 保存 provenance / transport / 统计
    out_dir = args.out_root
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, args.alignment_name)
    if os.path.exists(target) and not args.no_backup:
        bak = os.path.join(out_dir, 'alignment_labelgated_backup.json')
        if not os.path.exists(bak):
            import shutil
            shutil.copyfile(target, bak)
            print(f"[OK] 旧 alignment 已备份 -> {bak}")
    with open(target, 'w') as f:
        json.dump(alignment, f)
    print(f"[OK] raw provenance 已写入 {target}")
    write_provenance_reports(out_dir, stats, conflicts, transport_report, transported)

    if not args.skip_debug:
        try:
            verify_alignment_indices(alignment, nodeslistlist_orig, orig_files,
                                     nodeslistlist_trans, trans_files)
            generate_mapping_csv_v2(alignment, nodeslistlist_orig, infolist_orig, orig_files,
                                    nodeslistlist_trans, infolist_trans, trans_files)
        except Exception as exc:      # 调试报告不影响主产物
            print(f"[WARN] 调试报告生成失败（不影响 alignment/数据集）：{type(exc).__name__}: {exc}")
    else:
        print("[INFO] --skip-debug：跳过 alignment_debug_report.csv / mapping.csv")

if __name__ == '__main__':
    main()
