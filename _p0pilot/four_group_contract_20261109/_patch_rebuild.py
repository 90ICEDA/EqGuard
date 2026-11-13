from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\four_group_contract_20261109\rebuild_gate.py')
s = p.read_text(encoding='utf-8')
s = s.replace("rr = np.random.default_rng(abs(hash(s)) % (2 ** 31))",
              "rr = np.random.default_rng(int(hashlib.sha256(s.encode()).hexdigest()[:8], 16))")
s = s.replace("    np.savez_compressed(OUT / 'cones_A.npz', rows=np.array([m for _, (_, m, _) in selA], dtype=object) if False else np.array([x for _, (_, m, _) in selA for x in m], np.int64),",
              "    ptrA = np.array([0] + list(np.cumsum([len(m) for _, (_, m, _) in selA])), np.int64)\n"
              "    ptrB = np.array([0] + list(np.cumsum([len(m) for _, (_, m, _) in selB])), np.int64)\n"
              "    np.savez_compressed(OUT / 'cones_A.npz', ptr=ptrA, rows=np.array([x for _, (_, m, _) in selA for x in m], np.int64),")
s = s.replace("    np.savez_compressed(OUT / 'cones_B.npz', rows=np.array([x for _, (_, m, _) in selB for x in m], np.int64),",
              "    np.savez_compressed(OUT / 'cones_B.npz', ptr=ptrB, rows=np.array([x for _, (_, m, _) in selB for x in m], np.int64),")
s = s.replace("torch.as_tensor([len(m) for _, (_, m, _) in selA], device='cuda')",
              "torch.as_tensor(np.diff(ptrA), device='cuda')")
p.write_text(s, encoding='utf-8')
print('patched')
