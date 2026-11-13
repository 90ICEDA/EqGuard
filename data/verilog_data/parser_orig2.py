import re
import scipy
import numpy as np
import os
import json
from scipy.sparse import csr_matrix, lil_matrix, save_npz
import argparse
import networkx as nx

# --- 配置输出路径 ---
OUT_DIR = "./data/for_train"
NOT_FOR_TRAIN_DIR = "./data/not_for_train"

def ensure_dirs():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(NOT_FOR_TRAIN_DIR, exist_ok=True)

def flatten(l):
    return [item for sublist in l for item in sublist]

def getverilogs(path = './'):
    TRAIN = path + 'orig/train'
    VAL = path + 'orig/val'
    TEST = path + 'orig/test'
    for d in [TRAIN, VAL, TEST]:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
    
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

def getmoduleinfo(path = './'):
    moduleinfo = []
    lib_path = os.path.join(path, 'verilog_lib.v')
    if not os.path.exists(lib_path):
        raise FileNotFoundError(f"找不到库文件: {lib_path}")
        
    with open(lib_path) as f:
        temp = ''
        copy = False
        for line in f:
            m = re.match(r"\s*\n", line)
            if m: continue
            if 'module' == line.split(None, 1)[0]:
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
        priminlist = ["1'b1"]
        primoutlist = []
        for l in lines:
            if 'input' in l or 'output' in l:
                parts = re.split(r'\s+', l.strip())
                if parts[0] in ['input', 'output']:
                    temp = ",".join(parts[1:]).replace(';', '').split(',')
                    for prim in temp:
                        prim = prim.strip()
                        if not prim: continue
                        if 'input' in l: priminlist.append(prim)
                        else: primoutlist.append(prim)
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
                    match = re.search(r'assign\s+(\w+)\s*=\s*(\w+)', l)
                    if match:
                        blacklist[match.group(2)] = match.group(1)
                else:
                    for key in blacklist.keys():
                        if key in l:
                            l = l.replace(key, blacklist[key])
                    subsubret.append(l)
            subret.append(subsubret)
        ret.append(subret)
    return ret

def getinfo(line):
    x = re.match(r'module ([a-zA-Z0-9_]+) \((.*?)\);', line)
    if x:
        name = x.group(1)
        inputs = re.findall(r'input (.*?);', line)
        outputs = re.findall(r'output (.*?);', line)
        return (name, inputs, outputs)
    return [line.split(" ")[1], None, None]


def normalize_gate_type(gatetype):
    s = gatetype
    s = ''.join([i for i in s if not i.isdigit()])
    s = s.split('BWP')[0]
    s = re.sub(r'X\d+\b', 'X', s)
    s = re.sub(r'_(RS|S\d*|N)$', '', s)
    if s == "MXX":
        s = "MUXX"
    if s == "NBUFFX":
        s = "BUFX"
    return s

def build_library_gatelookup(modules):
    library_gate_types = sorted({normalize_gate_type(name) for name in modules.keys()})
    if 'UNK' not in library_gate_types:
        library_gate_types.append('UNK')
    return {g: i for i, g in enumerate(library_gate_types)}

def getlineinfo(line):
    line = line.replace("\n", "").lstrip()
    line = re.sub(' +', ' ', line)
    x = re.match(r"([a-zA-Z0-9_]+)\s+(\w+)\s*(\([^\)]+\))", line)
    if not x: return None
    gatetype, instancename, port_blob = x.group(1), x.group(2), x.group(3)
    
    label = instancename
    gatetypetrunc = normalize_gate_type(gatetype)

    portnames = []
    connectionnames = []
    connections = re.findall(r'\.(\w+)\((.*?)\)', port_blob)
    for p, c in connections:
        portnames.append(p)
        connectionnames.append(c)
    
    return (gatetype, gatetypetrunc, instancename, label, portnames, connectionnames)

def parse_modules(module_list):
    modules = dict()
    for i in module_list:
        name, inp, out = getinfo(i)
        modules[name] = inp, out
    return modules

def clean_1(lines):
    for l in range(len(lines)):
        if 'SDFFX1' in lines[l] and '.QN()' in lines[l]:
            lines[l] = re.sub(',\s*.QN\(\)', '', lines[l])
            lines[l] = lines[l].replace('SDFFX1 ', 'SDFFX12 ')
        if '//' in lines[l]:
            lines[l] = re.sub(r'//.*', '', lines[l])
        lines[l] = lines[l].strip()

def parse_lines(lines):
    nodeslistlist = []
    infolistlist = []
    trainindices, valindices, testindices = [], [], []

    i = 0
    for split, nets in enumerate(lines):
        for net in nets:
            nodes = dict()
            info = []
            for l in net:
                if not l or l.startswith('module') or l.startswith('endmodule') or l.startswith('wire'):
                    continue
                x = getlineinfo(l)
                if not x: continue
                nodes[x[2]] = i
                info.append(x)
                if split == 0: trainindices.append(i)
                elif split == 1: valindices.append(i)
                elif split == 2: testindices.append(i)
                i += 1
            infolistlist.append(info)
            nodeslistlist.append(nodes)
    return nodeslistlist, infolistlist, (trainindices, valindices, testindices)

def generate_lookup(infolist, modules):
    lookuplist = []
    for info in infolist:
        lookup = dict()
        for i, x in enumerate(info):
            inst_type = x[0]
            port_conns = zip(x[4], x[5])
            if inst_type not in modules: continue
            inp_ports, _ = modules[inst_type]
            if not inp_ports: continue
            for p, c in port_conns:
                if any(p in ip for ip in inp_ports):
                    lookup.setdefault(c, []).append(i)
        lookuplist.append(lookup)
    return lookuplist

def connect(shape, infolist, lookuplist, modules, train_indices):
    adj = lil_matrix((shape, shape), dtype=bool)
    adj_train = lil_matrix((shape, shape), dtype=bool)
    class_map = dict()
    membership = dict()
    num_neighbs = np.zeros(shape)

    i = 0
    net_idx = 0
    train_idx_set = set(train_indices)

    for info, lookup in zip(infolist, lookuplist):
        offset = i
        for x in info:
            inst_type, inst_name = x[0], x[2]
            
            # --- 二分类标签逻辑修改 ---
            # 0: Normal (普通节点和等价变换节点)
            # 1: Trojan (仅包含木马字符串的节点)
            if 'trojan' in x[3].lower():
                class_map[i] = 1
            else:
                class_map[i] = 0

            membership[i] = net_idx
            
            if inst_type in modules:
                _, out_ports = modules[inst_type]
                if out_ports:
                    for p, c in zip(x[4], x[5]):
                        if any(p in op for op in out_ports):
                            if c in lookup:
                                for target_local_idx in lookup[c]:
                                    target_global_idx = target_local_idx + offset
                                    adj[i, target_global_idx] = True
                                    adj[target_global_idx, i] = True 
                                    num_neighbs[i] += 1
                                    if i in train_idx_set and target_global_idx in train_idx_set:
                                        adj_train[i, target_global_idx] = True
                                        adj_train[target_global_idx, i] = True
            i += 1
        net_idx += 1
    return adj, adj_train, class_map, membership, num_neighbs

def generate_features(numnodes, gatelookup, modules, infolist, priminpslist, primoutslist, membership, num_neighbs):
    info_flat = flatten(infolist)
    feats = np.zeros((numnodes, len(gatelookup) + 4))
    unknown_gate_types = {}
    
    for i in range(numnodes):
        gate_type = info_flat[i][1]
        gate_idx = gatelookup.get(gate_type)
        if gate_idx is None:
            raw_gate_type = info_flat[i][0]
            renorm_gate_type = normalize_gate_type(raw_gate_type)
            gate_idx = gatelookup.get(renorm_gate_type, gatelookup['UNK'])
            if gate_idx == gatelookup['UNK']:
                unknown_gate_types[raw_gate_type] = unknown_gate_types.get(raw_gate_type, 0) + 1
        feats[i][gate_idx] = 1
        
        inst_type = info_flat[i][0]
        if inst_type in modules:
            inps, outs = modules[inst_type]
            feats[i][-4] = len(inps)/10 if inps else 0
            feats[i][-3] = num_neighbs[i]/20
        
        conns = info_flat[i][5]
        curr_net_idx = membership[i]
        if any(c in priminpslist[curr_net_idx] for c in conns):
            feats[i][-2] = 1
        if any(c in primoutslist[curr_net_idx] for c in conns):
            feats[i][-1] = 1

    if unknown_gate_types:
        print('[WARN] Unknown normalized gate types mapped to UNK:')
        for gate_name, count in sorted(unknown_gate_types.items()):
            print(f'  {gate_name} -> {normalize_gate_type(gate_name)} (count={count})')
    return feats

def save_all_data(train_idx, val_idx, test_idx, adj, adj_train, class_map, feats, gatelookup):
    save_npz(os.path.join(OUT_DIR, 'adj_full_orig.npz'), adj.tocsr())
    save_npz(os.path.join(NOT_FOR_TRAIN_DIR, 'adj_train_orig.npz'), adj_train.tocsr())
    
    with open(os.path.join(OUT_DIR, 'class_map_orig.json'), 'w') as f:
        json.dump(class_map, f)
    
    role = {'tr': train_idx, 'va': val_idx, 'te': test_idx}
    with open(os.path.join(OUT_DIR, 'role_orig.json'), 'w') as f:
        json.dump(role, f)
        
    with open(os.path.join(OUT_DIR, 'gatelookup_orig.json'), 'w') as f:
        json.dump(gatelookup, f, indent=2, sort_keys=True)

    np.save(os.path.join(OUT_DIR, 'feats_orig.npy'), feats)
    print(f"[SUCCESS] 数据预处理完成，标签已设为二分类 (0:Normal, 1:Trojan)")
    print(f"[INFO] 文件已存入: {OUT_DIR}")

def main():
    ensure_dirs()
    veriloglistlist = getverilogs()
    lines = [readlogs(v) for v in veriloglistlist]
    priminlistlist, primoutlistlist = getprimlist(lines)
    lines = fixassigns(lines)
    modules = parse_modules(getmoduleinfo())

    for split_idx in range(len(lines)):
        for net_idx in range(len(lines[split_idx])):
            clean_1(lines[split_idx][net_idx])
    
    nodeslistlist, infolistlist, indices = parse_lines(lines)
    numnodes = sum(len(n) for n in nodeslistlist)
    gatelookup = build_library_gatelookup(modules)

    lookuplist = generate_lookup(infolistlist, modules)
    adj, adj_train, class_map, membership, num_neighbs = connect(numnodes, infolistlist, lookuplist, modules, indices[0])

    feats = generate_features(numnodes, gatelookup, modules, infolistlist, priminlistlist, primoutlistlist, membership, num_neighbs)
    print(f"DEBUG: 库文件固定的简化门类型数为: {len(gatelookup)}")
    print(f"DEBUG: 特征矩阵的特征维度 (in_channels) 为: {feats.shape[1]}")
    save_all_data(indices[0], indices[1], indices[2], adj, adj_train, class_map, feats, gatelookup)

if __name__ == '__main__':
    main()