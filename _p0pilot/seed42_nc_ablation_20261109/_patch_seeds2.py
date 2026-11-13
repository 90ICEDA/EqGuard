from pathlib import Path

p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\seed42_nc_ablation_20261109\train_pair.py')
s = p.read_text(encoding='utf-8')
s = s.replace('        T.seed(42 + step)', '        T.seed(seed + step)')
s = s.replace("            q = loader.step(dm, 'G0', step)",
              "            q = loader.step(dm, 'G0', step, seed=seed)")
s = s.replace("            ids = torch.as_tensor(np.array(q.indices, copy=True), dtype=torch.long, device='cuda')",
              "            idx_np = np.array(q.indices, copy=True)\n"
              "            idx_sha = hashlib.sha256(idx_np.tobytes()).hexdigest()\n"
              "            ids = torch.as_tensor(idx_np, dtype=torch.long, device='cuda')")
s = s.replace("            history.append(dict(step=step + 1, orig=ls['orig'], trans=ls['trans'], val_ap=score))",
              "            history.append(dict(step=step + 1, orig=ls['orig'], trans=ls['trans'], val_ap=score, idx_sha=idx_sha))")
s = s.replace("    return dict(arm=arm, best_step=best['step'], best_score=best['score'],",
              "    return dict(arm=arm, seed=seed, init_sha=init_sha, best_step=best['step'], best_score=best['score'],")
p.write_text(s, encoding='utf-8')
print('patched')
