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

