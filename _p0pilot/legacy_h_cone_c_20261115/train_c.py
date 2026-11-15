"""Seed42 C: recipe-normalized positive D-cone loss, fixed old H."""
import json, sys
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import pandas as pd

OUT = Path(__file__).resolve().parent
RUN = OUT.parent / 'legacy_h_cone_20261115'
sys.path.insert(0, str(RUN))
import run

SEED = 42
DEST = OUT / f'seed{SEED}' / 'H'; DEST.mkdir(parents=True, exist_ok=True)
mod, manifest = run.configure(SEED, cone=True)
old = run.predecessor(SEED)
T = mod.T
cones = mod.CONES

# Map each cone to recipe; compute member counts and a capped sqrt balance weight.
raw = pd.read_csv(mod.CONE.OUT / 'CONE_CACHE_V2.csv', low_memory=False)
raw = raw[(raw.split == 'train') & (raw.kind == 'D') & (raw.label.astype(int) >= 0) & (raw.n_phys.astype(int) >= 2)]
raw['recipe'] = raw.view.str.extract(r'__(ys_[a-z]+)$')[0]
recipes = raw.recipe.tolist()
assert len(recipes) == len(cones['rows'])
labels = np.array([lab for _, lab, _ in cones['rows']], dtype=np.float32)
members = np.array([len(mem) for _, _, mem in cones['rows']], dtype=np.float64)
pos = {r: float(members[(labels == 1) & (np.array(recipes) == r)].sum()) for r in set(recipes)}
neg = {r: float(members[(labels == 0) & (np.array(recipes) == r)].sum()) for r in set(recipes)}
w = {}
for r in pos:
    ratio = min(1.0, neg.get(r, 0.0) / max(pos[r], 1.0))
    w[r] = max(0.25, float(np.sqrt(ratio)))
cone_w = np.array([w.get(r, 0.25) if lab == 1 else 1.0 for r, lab in zip(recipes, labels)], dtype=np.float32)
cone_w = torch.as_tensor(cone_w, device='cuda')
print('WEIGHTS', {k: round(v, 4) for k, v in sorted(w.items())}, flush=True)

def cone_loss(logits):
    score = mod.CONE.cone_score(mod.CONE.margin_of(logits), cones)
    bce = F.binary_cross_entropy_with_logits(score, cones['lab'], pos_weight=torch.tensor(10.0, device=score.device), reduction='none')
    return (bce * cone_w).sum() / cone_w.sum()

model = mod.Model().cuda()
model.load_state_dict(torch.load(old / f'init_s{SEED}.pt', map_location='cuda', weights_only=True))
assert sum(p.numel() for p in model.parameters()) == 46620
opt = torch.optim.Adam(model.parameters(), lr=.0002, weight_decay=.001)
domains = {}; slots = {}
for dm in ('orig', 'trans'):
    d = T.load(dm, 'train', 'A')
    d['base_indices'] = torch.tensor(np.flatnonzero(np.load(old / f'{dm}_base_mask.npy')), device='cuda')
    domains[dm] = d
    slots[dm] = np.load(old / f'{dm}_H_slots.npy')
best = dict(score=-1., epoch=-1); history = []
T.seed(SEED)
for epoch in range(200):
    T.seed(SEED + epoch); model.train(); opt.zero_grad(set_to_none=True); losses = []
    for dm, d in domains.items():
        ids = torch.cat((d['base_indices'], torch.tensor(slots[dm][epoch], device='cuda')))
        with torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(d['x'], d['edge'])
        loss = T.domain_loss(logits, d['y'], ids)
        if dm == 'trans':
            loss = loss + cone_loss(logits)
        assert torch.isfinite(loss)
        loss.backward(); losses.append(float(loss.detach()))
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.); assert torch.isfinite(norm); opt.step()
    rec = dict(update=epoch + 1, orig_loss=losses[0], trans_loss=losses[1], grad_norm=float(norm))
    if (epoch + 1) % 5 == 0:
        p = mod.predict(model, 'trans', 'val'); score = T.metrics(p, 'trans', 'val', .5)[0]['trusted']['ap']; rec['val_ap'] = score
        if score > best['score']:
            best = dict(score=score, epoch=epoch + 1); torch.save(model.state_dict(), DEST / 'best.pt'); np.save(DEST / 'selected_val_scores.npy', p)
        torch.save(dict(model=model.state_dict(), optimizer=opt.state_dict(), completed=epoch + 1, best=best), DEST / 'resume.pt')
        print(SEED, epoch + 1, 'valAP', round(score, 5), flush=True)
    history.append(rec); (DEST / 'history.json').write_text(json.dumps(history), encoding='utf-8')
print('DONE', best, flush=True)
