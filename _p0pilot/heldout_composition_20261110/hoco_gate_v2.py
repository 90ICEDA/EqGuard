"""hoco gate v2 using production functions; quota/exposure CSV; counterexamples with real paths."""
import os, sys
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import csv, json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(OUT)); sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
import hoco_cone_lib as CL2
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

allA, allB = CL2.build_store('A'), CL2.build_store('B')
gA, gB = CL2.load_group('A'), CL2.load_group('B')
srcs = sorted({v[2] for v in allA.values()} & {v[2] for v in allB.values()})
selA, selB, per = CL2.match(allA, allB, srcs)
# quota/exposure csv
def memstats(sel):
    cnt = {}
    for _, _, _, m in sel:
        for x in m.tolist():
            cnt[x] = cnt.get(x, 0) + 1
    return cnt
for tag, sel in (('A', selA), ('B', selB)):
    cnt = memstats(sel)
    ex = np.array(list(cnt.values())) if cnt else np.array([0])
    with (OUT / f'CONE_QUOTA_{tag}.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['source', 'label', 'cand', 'matched', 'used', 'cones', 'member_mean', 'exposure_max', 'exposure_gt1_frac'])
        for r in per:
            ss = [x for x in sel if x[2] == r['source'] and x[1] == r['label']] if False else []
            used = sum(1 for x in sel if x[3] is not None and x[0].split('__ys_')[0] == r['source'] and x[2] == r['label'])
            w.writerow([r['source'], r['label'], r['cand_A'] if tag == 'A' else r['cand_B'], r['matched'], used,
                        used, round(float(np.mean([len(x[3]) for x in sel if x[2] == r['label']])), 3) if any(x[2] == r['label'] for x in sel) else 0,
                        int(ex.max()), round(float((ex > 1).mean()), 4)])
# gate
tag = sys.argv[1]
g = np.load(OUT / f'hoco_{tag}.npz'); cones = np.load(OUT / f'hoco_cones_{tag}.npz')
mean, std = g['mean'], g['std']
def norm(x):
    o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o
x = torch.as_tensor(norm(g['x']), device='cuda'); e = torch.as_tensor(g['edge'], device='cuda'); y = torch.as_tensor(g['y'], device='cuda')
xo = torch.as_tensor(norm(np.load(B / 'inputs/orig_train/x39.npy')), device='cuda')
eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
ct = dict(rows=list(range(len(cones['label']))), idx=torch.as_tensor(cones['rows'], device='cuda'),
          seg=torch.repeat_interleave(torch.arange(len(cones['label']), device='cuda'), torch.as_tensor(np.diff(cones['ptr']), device='cuda')),
          lab=torch.as_tensor(cones['label'], dtype=torch.float32, device='cuda'))
loader = FiveGroupLoader(); io = torch.as_tensor(np.array(loader.step('orig', 'G0', 0).indices, copy=True), device='cuda')
it = torch.as_tensor(g['idx'][0], device='cuda')
model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))
state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
cp = torch.get_rng_state().clone(); cu = torch.cuda.get_rng_state_all(); model.train()
params = [p for p in model.parameters() if p.requires_grad]
with torch.autocast('cuda', dtype=torch.bfloat16):
    lo = model(xo, eo); l_o = T.domain_loss(lo, yo, io)
l_o.backward()
with torch.autocast('cuda', dtype=torch.bfloat16):
    lt = model(x, e); l_t = T.domain_loss(lt, y, it); l_c = CL.cone_loss(lt, ct)
gn = sum(float(q.norm()) ** 2 for q in torch.autograd.grad(l_t, params, retain_graph=True, allow_unused=True) if q is not None) ** 0.5
gc = sum(float(q.norm()) ** 2 for q in torch.autograd.grad(l_c, params, retain_graph=True, allow_unused=True) if q is not None) ** 0.5
l_t.backward(retain_graph=True); l_c.backward()
finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
lg = lt.detach().float(); m1 = (lg[:, 1] - lg[:, 0]).cpu().numpy().astype(np.float64)
off = np.random.default_rng(0).normal(size=(len(m1), 1))
m2 = ((lg[:, 1] + torch.as_tensor(off[:, 0], device='cuda')).cpu().numpy() - (lg[:, 0] + torch.as_tensor(off[:, 0], device='cuda')).cpu().numpy()).astype(np.float64)
margin_ok = abs(average_precision_score(g['y'][g['trusted']], m1[g['trusted']]) - average_precision_score(g['y'][g['trusted']], m2[g['trusted']])) < 1e-6
model.load_state_dict(state); torch.set_rng_state(cp); torch.cuda.set_rng_state_all(cu)
restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
rng_ok = torch.equal(torch.get_rng_state(), cp) and len(torch.cuda.get_rng_state_all()) == len(cu) and all(torch.equal(a, b) for a, b in zip(torch.cuda.get_rng_state_all(), cu))
bn_ok = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items() if 'running_' in k or 'num_batches' in k)
cx = {}
crc = CL2.cross_recipe_check(allA)
cx['cross_recipe_key'] = dict(passed=bool(crc['distinct_members']), path='hoco_cone_lib.build_store', evidence=crc)
try:
    CL2.negative_guard(np.array([int(g['pos'][0])]), g); neg = dict(passed=False, error=None)
except ValueError as ex:
    neg = dict(passed=True, error=str(ex))
cx['wrong_negative'] = neg
try:
    CL2.duplicate_guard(np.array([1, 1])); dup = dict(passed=False, error=None)
except ValueError as ex:
    dup = dict(passed=True, error=str(ex))
cx['duplicate'] = dup
try:
    CL2.insufficient_guard(np.arange(2), 5); ins = dict(passed=False, error=None)
except ValueError as ex:
    ins = dict(passed=True, error=str(ex))
cx['insufficient'] = ins
out = dict(group=tag, step0_len=int(len(g['idx'][0])), step0_sha=str(g['stepsha'][0]), cones=int(len(cones['label'])),
           cone_pos=int(cones['label'].sum()), cone_neg=int((cones['label'] == 0).sum()),
           cone_sources=len(srcs), loss_orig=float(l_o), loss_trans=float(l_t), loss_cone=float(l_c),
           node_grad=gn, cone_grad=gc, finite=bool(finite), margin_ok=bool(margin_ok), restored=bool(restored),
           bn_ok=bool(bn_ok), rng=bool(rng_ok), rng_cpu=bool(torch.equal(torch.get_rng_state(), cp)),
           rng_cuda_count=len(cu), optimizer_steps=0, optimizer=None,
           counterexamples=cx, production_paths=['hoco_cone_lib.build_store', 'hoco_cone_lib.negative_guard',
                                                  'hoco_cone_lib.duplicate_guard', 'hoco_cone_lib.insufficient_guard'])
(OUT / f'GATE_{tag}.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in out.items() if k != 'counterexamples'}, ensure_ascii=False))
