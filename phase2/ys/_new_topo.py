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
