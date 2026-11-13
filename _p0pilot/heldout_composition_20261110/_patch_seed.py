from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\heldout_composition_20261110\train_hoco.py')
s = p.read_text(encoding='utf-8')
s = s.replace("    tag, arm = sys.argv[1], sys.argv[2]",
              "    tag, arm = sys.argv[1], sys.argv[2]\n    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42")
s = s.replace("T.seed(42)\n    model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt'",
              "T.seed(seed)\n    model = Model().cuda(); model.load_state_dict(torch.load(R / f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt'")
s = s.replace("        T.seed(42 + step); model.train();", "        T.seed(seed + step); model.train();")
s = s.replace("outdir = OUT / f'run_{tag}_{arm}'", "outdir = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')")
s = s.replace("rng_cuda=torch.cuda.get_rng_state_all(), tag=tag, arm=arm), outdir / f'{point}_resume.pt')",
              "rng_cuda=torch.cuda.get_rng_state_all(), tag=tag, arm=arm, seed=seed, best_step=best['step']), outdir / f'{point}_resume.pt')")
p.write_text(s, encoding='utf-8')
print('patched')
