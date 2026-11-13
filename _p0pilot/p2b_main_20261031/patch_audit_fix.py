from pathlib import Path

p = Path(r'_p0pilot/p2b_main_20261031/train_ab.py')
s = p.read_text(encoding='utf-8')

# ARMS selector
s = s.replace("SEEDS = tuple(int(x) for x in os.environ.get('P2B_SEEDS', '42,1,2').split(','))",
              "SEEDS = tuple(int(x) for x in os.environ.get('P2B_SEEDS', '42,1,2').split(','))\nARMS = tuple(x.strip() for x in os.environ.get('P2B_ARMS', 'A,B').split(','))")

# per-architecture common init
s = s.replace("    common = H / f'common_init_s{s}.pt'", "    common = H / f'common_init_{arm}_s{s}.pt'")

# config wording
s = s.replace("               common_parameter_init='equal-shaped params copied per seed')",
              "               common_parameter_init='same seed + deterministic construction order; equal-shaped tensors shared only within the same architecture family (cross-architecture tensors are NOT shared)')")

# arms loop
s = s.replace("        for arm in ('A', 'B'):\n            train_arm(arm, s)",
              "        for arm in ARMS:\n            train_arm(arm, s)")
p.write_text(s, encoding='utf-8')
print('ARMS:', 'ARMS = tuple' in s, 'loop:', 'for arm in ARMS' in s)
print('init per arch:', "common_init_{arm}_s{s}.pt" in s)
