import re
import scipy
import numpy as np
import networkx as nx
import os
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
    priminlistlist = []
    primoutlistlist = []

    linelistflat = flatten(linelist)

    for lines in linelistflat:
        priminlist = []
        primoutlist = []
        priminlist.append("1'b1")
        for l in lines:
            if 'input' in l or 'output' in l:
                temp = l.split(' ', 1)[1]
                temp = temp.split(' ', 1)[1]
                temp = temp.split(' ', 1)[1]
                temp = temp.split(',')

                for prim in temp:
                    if re.match('\[\d*:\d*]', prim):
                        numbering, name = prim.split(' ')
                        stop, start = re.findall('\d+', prim)
                        for i in range(int(start), int(stop) + 1):
                            if 'input' in l:
                                priminlist.append(name+'['+str(i)+']')
                            else:
                                primoutlist.append(name+'['+str(i)+']')
                    else:
                        if 'input' in l:
                            priminlist.append(prim.strip())
                        else:
                            primoutlist.append(prim.strip())

        priminlistlist.append(priminlist)
        primoutlistlist.append(primoutlist)

    return priminlistlist, primoutlistlist

def fixassigns(linelist):
    ret = []
    for split in linelist:
        subret = []
        for lines in split:
            subsubret = []
            blacklist = dict()
            for l in lines:
                if 'assign' in l:
                    #temp = l.replace('\n', '')
                    temp = l.split(' ', 1)[1]
                    temp = temp.split(' ', 1)[1]
                    temp = temp.split(' ', 1)[1]
                    leftside, rightside = temp.split(' = ')
                    blacklist[rightside] = leftside
                else:
                    for key in blacklist.keys():
                        if key in l:
                            l = l.replace(key, blacklist[key])
                    subsubret.append(l)
            subret.append(subsubret)
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

def getlineinfo(line):
    line = line.replace("\n", "").lstrip()
    line = re.sub(' +', ' ', line)
    #print(line)
    #x = re.match('(([a-zA-Z0-9]+)) \\\\(\w)+[^\s]+ (\([\/a-zA-Z0-9\s_\),.\(\\\\]+)', line)
    #x = re.match('(([a-zA-Z0-9]+)) \\\\(\w)+[^\s]+ (\([\/a-zA-Z0-9\s_\)\[\],.\(\\\\]+)', line)
    #x = re.match(r"(([a-zA-Z0-9]+)) \\(\w+)[^\s]+ (\([\/a-zA-Z0-9\s_\),.\(\\\\\[\]]+)", line)
    #x = re.match(r"(([a-zA-Z0-9]+)) \\?(\w+)[^\s]* (\([\/a-zA-Z0-9\s_\),.\(\\\\\[\]]+)", line)
    #print(line)
    x = re.match(r"(([a-zA-Z0-9_]+))\s*\\?(\w+)[^\s]*\s*(\([\/a-zA-Z0-9\s_\'),.\(\\\\\[\]]+)", line)
    #print(x)
    gatetype, instancename = x.group(0).split(' ')[0], x.group(0).split(' ')[1]
    label = x.group(3)

    ports = x.group(4)
    ports = ports.split(',')
    ports[0] = ports[0][1:]
    ports[-1] = ports[-1][:-2]
    portnames = []
    connectionnames = []
    
    for lin in ports:
        z = lin.replace(' ','')
        #print(z)
        #zz = re.match('.([A-Z0-9]+)\(\\\\([a-zA-Z-0-9_\/]+)', z)
        zz = re.match('\.([a-zA-Z0-9_]+)\(([\\\/a-zA-Z-0-9_\/\[\]]+)', z)
        portname = zz.group(1)
        zz
        portconnection = zz.group(2)
        portnames.append(portname)
        connectionnames.append(portconnection)
    
    return(gatetype, gatetype, instancename, label, portnames, connectionnames)

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

def connect(shape, infolist, lookuplist, modules, train_indices):
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
def process_domain(verilog_splits, modules, gate_mapping, gatelookup, suffix="orig"):
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
    numnodes = np.sum([len(i) for i in nodeslistlist])

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
    feats, connected_to_prim_inp, connected_to_prim_out = generate_features(
        numnodes, gatelookup, gate_mapping, modules, infolistlist, 
        priminlistlist, primoutlistlist, membership, num_neighbs
    )

    # D. 拓扑特征 (Distance & 2-hop)
    try:
        G = nx.from_scipy_sparse_array(adj)
    except:
        G = nx.from_scipy_sparse_matrix(adj.tocsr())
    DiG = nx.DiGraph()
    DiG.add_nodes_from(range(numnodes)) 
    DiG.add_edges_from(directed_edges)

    distances = np.ones((numnodes, 2)) * -1
    for i in connected_to_prim_inp: distances[i, 0] = 0
    for i in connected_to_prim_out: distances[i, 1] = 0
    distances = calculate_distances(G, list(connected_to_prim_out), 1, distances, 1)
    distances = calculate_distances(G, list(connected_to_prim_inp), 1, distances, 0)

    fan_in_sizes = np.zeros((numnodes, 1))
    fan_out_sizes = np.zeros((numnodes, 1)) 
    in_out_ratio = (fan_in_sizes - fan_out_sizes)/10
    for i in range(numnodes):
        fan_in_sizes[i, 0] = np.log1p(len(nx.bfs_tree(DiG, i, reverse=True, depth_limit=2)) - 1)
        fan_out_sizes[i, 0] = np.log1p(len(nx.bfs_tree(DiG, i, reverse=False, depth_limit=2)) - 1)

    feats = np.concatenate((feats, distances, fan_in_sizes, fan_out_sizes), axis=1)

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
                instance_name = idx_to_name[target_idx]
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

def main():
    moduleinfo = getmoduleinfo()
    modules = parse_modules(moduleinfo)
    gate_mapping = load_gate_full_to_simplified_mapping('./gate_full_to_simplified_mapping.json')
    gatelookup = load_gatelookup('./gatelookup_recommended.json')

    # 1. 加载文件夹
    orig_files = getverilogs(path='./', sub_folder='orig')
    trans_files = getverilogs(path='./', sub_folder='trans')

    _, _, class_map_orig, nodeslistlist_orig, infolist_orig = process_domain([orig_files, [], []], modules, gate_mapping, gatelookup, "orig")
    _, _, class_map_trans, nodeslistlist_trans, infolist_trans = process_domain([trans_files, [], []], modules, gate_mapping, gatelookup, "trans")

    # 2. 建立文件名到索引的映射 (归一化处理，去掉 .v)
    orig_name_to_idx = {os.path.basename(f).replace(".v", ""): i for i, f in enumerate(orig_files)}
    trans_name_to_idx = {os.path.basename(f).replace(".v", ""): i for i, f in enumerate(trans_files)}

    print("\n>>> 正在根据 Trans 网表名称匹配映射文件...")
    mapping_dir = "./mappings"
    final_alignment = []
    
    # 遍历所有 Trans 文件
    for t_fname_v, t_f_idx in trans_name_to_idx.items():
        # 匹配映射文件 (trans名称.json)
        map_path = os.path.join(mapping_dir, f"{t_fname_v}.json")
        if not os.path.exists(map_path):
            continue
            
        with open(map_path, 'r') as f:
            map_data = json.load(f)
            src_v = map_data.get("src_verilog", "").replace(".v", "")
            node_align = map_data.get("node_alignment", {})

        if src_v not in orig_name_to_idx:
            print(f"  [Skip] 映射文件 {t_fname_v}.json 指向的原始网表 {src_v} 未在 orig 文件夹找到")
            continue
            
        o_f_idx = orig_name_to_idx[src_v]
        curr_orig_nodes = nodeslistlist_orig[o_f_idx]
        curr_trans_nodes = nodeslistlist_trans[t_f_idx]
        covered_o_idxs_this_pair = set()

        # A. 显式映射
        for o_name, t_names in node_align.items():
            o_clean = o_name.lstrip('\\')
            if o_clean in curr_orig_nodes:
                o_idx = curr_orig_nodes[o_clean]
                o_label = class_map_orig[str(o_idx)]
                for t_name in t_names:
                    t_clean = t_name.lstrip('\\')
                    if t_clean in curr_trans_nodes:
                        t_idx = curr_trans_nodes[t_clean]
                        if o_label == class_map_trans[str(t_idx)]:
                            final_alignment.append([o_idx, t_idx])
                            covered_o_idxs_this_pair.add(o_idx)

        # B. 身份映射 (未变动的门)
        for name, o_idx in curr_orig_nodes.items():
            if o_idx not in covered_o_idxs_this_pair:
                if name in curr_trans_nodes:
                    t_idx = curr_trans_nodes[name]
                    if class_map_orig[str(o_idx)] == class_map_trans[str(t_idx)]:
                        final_alignment.append([o_idx, t_idx])

    # 3. 保存并验证
    save_path = './data/for_train/alignment.json'
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, 'w') as f: json.dump(final_alignment, f)
    
    print(f"[完成] 共生成 {len(final_alignment)} 个对齐节点。")

    verify_alignment_indices(final_alignment, nodeslistlist_orig, orig_files, 
                             nodeslistlist_trans, trans_files)
    
    # 调用升级后的统计函数
    generate_mapping_csv_v2(final_alignment, nodeslistlist_orig, infolist_orig, orig_files, 
                            nodeslistlist_trans, infolist_trans, trans_files)
if __name__ == '__main__':
    main()
