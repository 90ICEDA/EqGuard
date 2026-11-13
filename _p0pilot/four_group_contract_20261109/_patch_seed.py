from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\four_group_contract_20261109\train_four.py')
s = p.read_text(encoding='utf-8')
s = s.replace("    tag = sys.argv[1]; arm = sys.argv[2]", "    tag = sys.argv[1]; arm = sys.argv[2]; seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42")
s = s.replace("model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))",
              "model.load_state_dict(torch.load(R / f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt', map_location='cuda', weights_only=True))")
s = s.replace("    T.seed(42); model = Model().cuda();", "    T.seed(seed); model = Model().cuda();")
s = s.replace("        T.seed(42 + step); model.train();", "        T.seed(seed + step); model.train();")
s = s.replace("    outdir = OUT / f'run_{tag}_{arm}'; outdir.mkdir(exist_ok=True)",
              "    outdir = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}'); outdir.mkdir(exist_ok=True)")
s = s.replace("rng_cuda=torch.cuda.get_rng_state_all(), tag=tag, arm=arm)",
              "rng_cuda=torch.cuda.get_rng_state_all(), tag=tag, arm=arm, seed=seed)")
p.write_text(s, encoding='utf-8')
print('patched')
