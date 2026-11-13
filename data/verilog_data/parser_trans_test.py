import re
import scipy
import numpy as np
import os
import json
from scipy.sparse import csr_matrix, lil_matrix
import argparse


def flatten(l):
    return [item for sublist in l for item in sublist]

def getverilogs(path = './'):
    TRAIN = path + 'trans/train'
    VAL = path + 'trans/val'
    TEST = path + 'trans/test'

    trainids = os.listdir(TRAIN)
    valids = os.listdir(VAL)
    testids = os.listdir(TEST)

    trainverilogs = [os.path.join(TRAIN, v) for v in trainids]
    valverilogs = [os.path.join(VAL, v) for v in valids]
    testverilogs = [os.path.join(TEST, v) for v in testids]

    return [trainverilogs, valverilogs, testverilogs]

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


            inp, out = modules[instancename]
            if inp is None:
                continue
            for q in range(len(portnames)):
                if portnames[q] in inp:
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
    directed_edges = []  # 新增：用于记录逻辑流向 (驱动门 -> 被驱动门)
    
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
            instancename = x[0] # 门类型，如 OAI21X1_RS
            
            if 'trojan' in x[3].lower():
                class_map[str(i)] = 1
            else:
                class_map[str(i)] = 0

            # --- ### DEBUG: 检查门类型是否存在于库中 ---
            if instancename not in modules:
                total_skipped_no_module += 1
                # 如果前几个门就找不到，打印出来看看名字差异
                if total_skipped_no_module < 5:
                    print(f"DEBUG: 库中缺少门类型 '{instancename}' (网表中的第一个词)")
                membership[i] = netlist_idx
                i += 1
                continue

            inp_ports, out_ports = modules[instancename]
            
            if out_ports is None:
                total_skipped_no_output += 1
                membership[i] = netlist_idx
                i += 1
                continue

            portnames = x[4]        # 物理引脚名，如 ['A0', 'A1', 'B0', 'Y']
            connectionnames = x[5]  # 连接信号名，如 ['n1', 'n2', 'sig_out']

            # 遍历当前门的所有端口
            for q in range(len(portnames)):
                # --- ### DEBUG: 检查引脚判定逻辑 ---
                pin = portnames[q]
                # 检查这个引脚是否被识别为“输出”
                is_output = any(pin in op for op in out_ports)
                
                if is_output:
                    conn_name = connectionnames[q]
                    try:
                        neighbors = lookup[conn_name]
                        for num in neighbors:
                            target_node = num + offset
                            adj[i, target_node] = 1
                            adj[target_node, i] = 1

                            directed_edges.append((i, target_node))
                            
                            num_neighbs[i] += 1
                            num_neighbs[target_node] += 1
                            total_edges_found += 1

                            if i in train_idx_set and target_node in train_idx_set:
                                adj_train[i, target_node] = 1
                                adj_train[target_node, i] = 1
                    except KeyError:
                        # 这种情况通常是信号连到了顶层输出(PO)，在lookup里找不到(lookup只存输入)
                        pass
                # --- ### DEBUG: 辅助判定引脚名是否匹配 ---
                elif q == 0 and i == offset: # 每个文件只打印第一个实例的第一个引脚
                    print(f"DEBUG: 实例 {x[2]} 的引脚 {pin} 未被识别为输出。库定义输出为: {out_ports}")
            
            membership[i] = netlist_idx
            i += 1
        netlist_idx += 1
        
    # --- ### DEBUG: 打印最终汇总报告 ---
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

def save_output(trainindices, valindices, testindices, adj, adj_train, class_map, feats):
    import json
    from scipy.sparse import save_npz
    from tempfile import TemporaryFile

    outfile = TemporaryFile()

    role = dict()

    role['tr'] = trainindices
    role['va'] = valindices
    role['te'] = testindices

    adj_full = adj.tocsr()
    adj_train = adj_train.tocsr()

    save_npz('./data/for_train/adj_full_trans.npz', adj_full)
    save_npz('./data/not_for_train/adj_train_trans.npz', adj_train)

    with open('./data/for_train/class_map_trans.json', 'w') as fp:
        json.dump(class_map, fp)

    with open('./data/for_train/role_trans.json', 'w') as fp:
        json.dump(role, fp)

    np.save('./data/for_train/feats_trans.npy', feats, allow_pickle=False)

    

def main():



    veriloglistlist = getverilogs()


    lines = []
    for v in veriloglistlist:
        lines.append(readlogs(v))

    trainlen = len(lines[0])
    vallen = len(lines[1])
    testlen = len(lines[2])

    priminlistlist, primoutlistlist = getprimlist(lines)
    lines = fixassigns(lines) #takes time

    moduleinfo = getmoduleinfo()
    modules = parse_modules(moduleinfo)
    gate_full_to_simplified = load_gate_full_to_simplified_mapping('./gate_full_to_simplified_mapping.json')
    gatelookup = load_gatelookup('./gatelookup_recommended.json')
    print(type(gate_full_to_simplified), len(gate_full_to_simplified))


    for num2, split in enumerate(lines):
        for num, l in enumerate(split):
            clean_1(l) #!double check this works
            last = getindices('wire', l)[-1]

            l = l[last+1:-1]
            lines[num2][num] = l



    gates, nodeslistlist, infolistlist, indexlistlist, indices = parse_lines(lines)
    numnodes = np.sum([(len(i)) for i in nodeslistlist])

    print(len(priminlistlist))

    #tested till here

    # for n, v in zip(nodeslistlist, flatten(veriloglistlist)):
    #     print(len(n), v)

    lookuplist = generate_lookup(infolistlist, modules)
    adj, adj_train, class_map, membership, num_neighbs, directed_edges = connect(numnodes, infolistlist, lookuplist, modules, indices[0])
    print(gatelookup)


    feats, connected_to_prim_inp, connected_to_prim_out = generate_features(numnodes,gatelookup,gate_full_to_simplified,
                                                modules,infolistlist,priminlistlist,primoutlistlist,membership,num_neighbs)

    import networkx as nx
    import matplotlib.pyplot as plt

    try:
        G = nx.from_scipy_sparse_array(adj)
    except AttributeError:
        G = nx.from_scipy_sparse_matrix(adj.tocsr())

    print("正在构建有向图...")
    DiG = nx.DiGraph()
    DiG.add_nodes_from(range(numnodes))
    DiG.add_edges_from(directed_edges)

    distances = np.ones((numnodes, 2)) * -1

    for i in connected_to_prim_inp:
        distances[i, 0] = 0
    for i in connected_to_prim_out:
        distances[i, 1] = 0


    distances = calculate_distances(G, connected_to_prim_out, 1, distances, 1)
    distances = calculate_distances(G, connected_to_prim_inp, 1, distances, 0)

    # 新增：双向 2-hop 子图特征计算
    print("正在计算驱动(Fan-in)与被驱动(Fan-out) 2-hop 子图大小...")
    fan_in_sizes = np.zeros((numnodes, 1))
    fan_out_sizes = np.zeros((numnodes, 1))

    for i in range(numnodes):
        if i % 2000 == 0:
            print(f"进度: {i}/{numnodes}", end='\r')
        
        # 1. 计算驱动侧 (上游)：在有向图中反向看 2 步
        # 使用 bfs_tree 获取深度为 2 的节点集，减去自身(1)
        upstream = nx.bfs_tree(DiG, i, reverse=True, depth_limit=2)
        fan_in_sizes[i, 0] = np.log1p(len(upstream) - 1)

        # 2. 计算被驱动侧 (下游)：在有向图中正向看 2 步
        downstream = nx.bfs_tree(DiG, i, reverse=False, depth_limit=2)
        fan_out_sizes[i, 0] = np.log1p(len(downstream) - 1)


    
    print(f"\n特征提取完成。最终特征维度: {feats.shape[1]}")

    # --- 寻找最后一个不可达节点所属文件 ---
    
    # 1. 组合所有处理过的文件路径（按顺序：train -> val -> test）
    all_v_files = flatten(veriloglistlist)
    
    # 2. 找到最后一个不可达节点的全局索引
    # 我们检查距离矩阵，只要 PI 或 PO 任何一个方向不可达（即值为 -1）
    unreachable_indices = np.where((distances[:, 0] == -1) | (distances[:, 1] == -1))[0]
    
    if len(unreachable_indices) > 0:
        last_unreachable_idx = unreachable_indices[-1] # 拿到最后一个 -1 的索引
        
        # 3. 遍历每个文件对应的节点集合，定位该索引
        current_idx = 0
        target_file = "Unknown"
        
        # nodeslistlist 存储了每个文件的节点字典，顺序与 all_v_files 一致
        for file_path, nodes_dict in zip(all_v_files, nodeslistlist):
            num_nodes_in_file = len(nodes_dict)
            start_range = current_idx
            end_range = current_idx + num_nodes_in_file - 1
            
            if start_range <= last_unreachable_idx <= end_range:
                target_file = file_path
                print(f"\n[诊断结果]")
                print(f"最后一个不可达节点的全局索引: {last_unreachable_idx}")
                print(f"该节点所属文件路径: {target_file}")
                print(f"该文件在该电路中的节点范围: {start_range} 到 {end_range}")
                break
            
            current_idx += num_nodes_in_file
    else:
        print("\n[诊断结果] 恭喜！图中不存在不可达节点。")

    unreachable_pi = np.sum(distances[:, 0] == -1)
    unreachable_po = np.sum(distances[:, 1] == -1)
    
    print(f"5. 无法到达 PI 的节点比例: {unreachable_pi}/{numnodes} ({unreachable_pi/numnodes:.2%})")
    print(f"6. 无法到达 PO 的节点比例: {unreachable_po}/{numnodes} ({unreachable_po/numnodes:.2%})")

    # 检查是否有节点是完全孤立的（度数为0）
    isolated_nodes = np.sum(num_neighbs == 0)
    print(f"7. 完全孤立（度数为0）的节点数: {isolated_nodes}")
    in_out_ratio = (fan_in_sizes - fan_out_sizes)/10
    # distances[:,0] = distances[:,0] / 10
    # distances[:,1] = distances[:,1] / 10
    # 修改：将两个方向的特征拼接到矩阵最后两列
    # 顺序：... + distances (2列) + fan_in_size (1列) + fan_out_size (1列)
    feats = np.concatenate((feats, distances, fan_in_sizes, fan_out_sizes), axis = 1)
    # , fan_in_sizes, fan_out_sizes, in_out_ratio

    np.savetxt("./data/not_for_train/distances.txt", distances, fmt='%1.1f')

    print(f"节点总数: {numnodes}")
    print(f"直接连接到 PI 的节点数: {np.sum(feats[:, -6])}") 
    print(f"直接连接到 PO 的节点数: {np.sum(feats[:, -5])}")
    print(f"邻接矩阵边总数: {adj.nnz}")


    nx.write_gexf(G, "./data/not_for_train/test.gexf")
    
    

    save_output(indices[0], indices[1], indices[2], adj, adj_train, class_map, feats)

if __name__ == '__main__':
    main()
