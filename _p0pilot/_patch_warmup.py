from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\lcone_warmup_train.py')
s = p.read_text(encoding='utf-8')
s = s.replace('arm = sys.argv[1]; seed = int(sys.argv[2]); lam = float(sys.argv[3])',
              'arm = sys.argv[1]; seed = int(sys.argv[2]); lam = float(sys.argv[3]); warmup = int(sys.argv[4]) if len(sys.argv) > 4 else 0')
s = s.replace("run_{arm}_s{seed}_lam{lam}", "run_{arm}_s{seed}_lam{lam}_w{warmup}")
s = s.replace("        loss = l_t + lam * l_c", "        loss = (l_t + lam * l_c) if step >= warmup else l_t")
s = s.replace("dict(arm=arm, seed=seed, lambda_=lam, pos_weight=10.0, best_step=best['step'], best_score=best['score'], logs=logs)",
              "dict(arm=arm, seed=seed, lambda_=lam, pos_weight=10.0, warmup=warmup, best_step=best['step'], best_score=best['score'], logs=logs)")
p.write_text(s, encoding='utf-8')
print('patched warmup')
