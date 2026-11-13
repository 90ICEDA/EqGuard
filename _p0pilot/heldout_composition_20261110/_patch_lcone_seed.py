from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\heldout_composition_20261110\train_lcone.py')
s = p.read_text(encoding='utf-8')
s = s.replace("    arm = sys.argv[1]", "    arm = sys.argv[1]\n    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42")
s = s.replace("T.seed(42)\n    model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt'",
              "T.seed(seed)\n    model = Model().cuda(); model.load_state_dict(torch.load(R / f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt'")
s = s.replace("        T.seed(42 + step); model.train();", "        T.seed(seed + step); model.train();")
s = s.replace("outdir = OUT / f'lcone_{arm}'", "outdir = OUT / (f'lcone_{arm}' if seed == 42 else f'lcone_{arm}_s{seed}')")
s = s.replace("arm=arm, best_step=best['step'])", "arm=arm, seed=seed, best_step=best['step'])")
p.write_text(s, encoding='utf-8')
print('patched')
