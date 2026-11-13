from pathlib import Path

p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\seed42_nc_ablation_20261109\train_pair.py')
s = p.read_text(encoding='utf-8')
s = s.replace("def run(arm, loader, cones):\n    T.seed(42)",
              "def run(arm, loader, cones, seed=42):\n    T.seed(seed)")
s = s.replace("model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))",
              "model.load_state_dict(torch.load(V / f'init_s{seed}.pt', map_location='cuda', weights_only=True))")
s = s.replace("torch.save(best['state'], OUT / f'{arm}_best.pt'); torch.save(last, OUT / f'{arm}_last.pt')",
              "torch.save(best['state'], OUT / f'{arm}_s{seed}_best.pt'); torch.save(last, OUT / f'{arm}_s{seed}_last.pt')")
s = s.replace("np.savez(OUT / f'{arm}_scores.npz',",
              "np.savez(OUT / f'{arm}_s{seed}_scores.npz',")
old = "    for arm in ('N', 'NC'):\n        t = time.perf_counter()\n        out[arm] = run(arm, loader, cones)"
new = ("    seeds = [int(x) for x in sys.argv[1:]] or [42]\n"
       "    for seed in seeds:\n"
       "        for arm in ('N', 'NC'):\n"
       "            t = time.perf_counter()\n"
       "            out[f'{arm}_s{seed}'] = run(arm, loader, cones, seed)")
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
print('patched', old in s)
