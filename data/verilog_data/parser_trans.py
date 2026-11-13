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
    x = re.match('module ([a-zA-Z0-9]+) \([\s,a-zA-Z0-9]+\); \s+(input [a-zA-Z0-9,\s]+;)? \s+(output [a-zA-Z0-9,\s]+;)?', line)
    if x == None:
        return [line.split(" ")[1], None, None]
    name = x.group(1)
    inputs = x.group(2)
    outputs = x.group(3)
    if inputs != None:
        z = re.match('input ((\w+,? ?)+)', inputs)
        inputs = z.group(1).split(", ")
    if outputs != None:
        y = re.match('output ((\w+,? ?)+)', outputs)
        outputs = y.group(1).split(", ")

    return (name, inputs, outputs)

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
    
    class_map = dict()
    membership = dict()
    num_neighbs = np.zeros(shape)

    i = 0
    netlist_idx = 0
    train_idx_set = set(train_indices)

    for info, lookup in zip(infolist, lookuplist):
        offset = i
        for x in info:
            instancename = x[0]
            if 'trojan' in x[3].lower():
                class_map[str(i)] = 1
            else:
                class_map[str(i)] = 0


            if instancename not in modules:
                membership[i] = netlist_idx
                i += 1
                continue

            inp_ports, out_ports = modules[instancename]
            
            if out_ports is None:
                membership[i] = netlist_idx
                i += 1
                continue

            portnames = x[4]
            connectionnames = x[5]

            # 遍历当前门的所有端口
            for q in range(len(portnames)):
                # 如果该端口是输出端口
                if any(portnames[q] in op for op in out_ports):
                    conn_name = connectionnames[q]
                    try:
                        # 查找所有连接到这个信号的输入端（邻居）
                        neighbors = lookup[conn_name]
                        for num in neighbors:
                            target_node = num + offset
                            # 建立无向图边连接 (GIN 通常处理无向图)
                            adj[i, target_node] = 1
                            adj[target_node, i] = 1
                            

                            num_neighbs[i] += 1
                            num_neighbs[target_node] += 1


                            if i in train_idx_set and target_node in train_idx_set:
                                adj_train[i, target_node] = 1
                                adj_train[target_node, i] = 1
                    except KeyError:
                        pass
            
            membership[i] = netlist_idx
            i += 1
        netlist_idx += 1
        
    print(f"Total nodes processed: {i}")
    return adj, adj_train, class_map, membership, num_neighbs


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
    adj, adj_train, class_map, membership, num_neighbs = connect(numnodes, infolistlist, lookuplist, modules, indices[0])
    print(gatelookup)


    feats, connected_to_prim_inp, connected_to_prim_out = generate_features(numnodes,gatelookup,gate_full_to_simplified,
                                                modules,infolistlist,priminlistlist,primoutlistlist,membership,num_neighbs)

    import networkx as nx
    import matplotlib.pyplot as plt

    try:
        G = nx.from_scipy_sparse_array(adj)
    except AttributeError:
        G = nx.from_scipy_sparse_matrix(adj.tocsr())

    distances = np.ones((numnodes, 2)) * -1

    for i in connected_to_prim_inp:
        distances[i, 0] = 0
    for i in connected_to_prim_out:
        distances[i, 1] = 0

    distances = calculate_distances(G, connected_to_prim_out, 1, distances, 1)
    distances = calculate_distances(G, connected_to_prim_inp, 1, distances, 0)

    distances[:,0] = distances[:,0] / 10
    distances[:,1] = distances[:,1] / 10

    np.savetxt("./data/not_for_train/distances.txt", distances, fmt='%1.1f')

    feats = np.concatenate((feats, distances), axis = 1)

    nx.write_gexf(G, "./data/not_for_train/test.gexf")

    

    save_output(indices[0], indices[1], indices[2], adj, adj_train, class_map, feats)

if __name__ == '__main__':
    main()
