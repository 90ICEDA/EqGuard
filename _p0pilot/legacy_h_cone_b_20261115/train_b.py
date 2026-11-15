"""Seed42 single-factor B: H+D plus fixed nand/aig H-slot replacement schedule."""
import json, sys, hashlib
from pathlib import Path
import numpy as np
import torch

OUT = Path(__file__).resolve().parent
RUN = OUT.parent / 'legacy_h_cone_20261115'
sys.path.insert(0, str(RUN))
import run

SEED = 42
DEST = OUT / f'seed{SEED}' / 'H'
DEST.mkdir(parents=True, exist_ok=True)
mod, manifest = run.configure(SEED, cone=True)
old = run.predecessor(SEED)
T = mod.T
model = mod.Model().cuda()
init = old / f'init_s{SEED}.pt'
model.load_state_dict(torch.load(init, map_location='cuda', weights_only=True))
assert sum(p.numel() for p in model.parameters()) == 46620
opt = torch.optim.Adam(model.parameters(), lr=.0002, weight_decay=.001)
sch = np.load(OUT.parent / 'legacy_h_cone_20261115/replacement_preflight/SCHEDULE.npz')['pair']
assert sch.shape == (200, 54, 2)

domains = {}
slots = {}
for dm in ('orig', 'trans'):
    d = T.load(dm, 'train', 'A')
    base = np.flatnonzero(np.load(old / f'{dm}_base_mask.npy'))
    d['base_indices'] = torch.tensor(base, device='cuda')
    domains[dm] = d
    slots[dm] = np.load(old / f'{dm}_H_slots.npy').copy()

# Verify the fixed replacement donors are trusted physical negatives.
a = T.arrays('trans', 'train')
donors = np.unique(sch[:, :, 1])
assert len(donors) == 541
assert (a['y'][donors] == 0).all()
assert a['trusted'][donors].all()
assert a['physical'][donors].all()
# Replace only the first 54 trans slots per step; all else fixed.
for ep in range(200):
    slots['trans'][ep, :54] = sch[ep, :, 1]

best = dict(score=-1., epoch=-1)
history = []
T.seed(SEED)
for epoch in range(200):
    T.seed(SEED + epoch)
    model.train()
    opt.zero_grad(set_to_none=True)
    losses = []
    for dm, d in domains.items():
        ids = torch.cat((d['base_indices'], torch.tensor(slots[dm][epoch], device='cuda')))
        with torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(d['x'], d['edge'])
        loss = T.domain_loss(logits, d['y'], ids)
        if dm == 'trans':
            loss = loss + mod.CONE.cone_loss(logits, mod.CONES)
        assert torch.isfinite(loss)
        loss.backward()
        losses.append(float(loss.detach()))
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
    assert torch.isfinite(norm)
    opt.step()
    rec = dict(update=epoch + 1, orig_loss=losses[0], trans_loss=losses[1], grad_norm=float(norm))
    if (epoch + 1) % 5 == 0:
        p = mod.predict(model, 'trans', 'val')
        score = T.metrics(p, 'trans', 'val', .5)[0]['trusted']['ap']
        rec['val_ap'] = score
        if score > best['score']:
            best = dict(score=score, epoch=epoch + 1)
            torch.save(model.state_dict(), DEST / 'best.pt')
            np.save(DEST / 'selected_val_scores.npy', p)
        torch.save(dict(model=model.state_dict(), optimizer=opt.state_dict(), completed=epoch + 1, best=best), DEST / 'resume.pt')
        print(SEED, epoch + 1, 'valAP', round(score, 5), flush=True)
    history.append(rec)
    (DEST / 'history.json').write_text(json.dumps(history), encoding='utf-8')
print('DONE', best, flush=True)
