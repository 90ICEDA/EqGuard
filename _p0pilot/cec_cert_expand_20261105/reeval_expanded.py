"""Re-evaluate existing checkpoints on the expanded validation certificate set (read-only)."""
from pathlib import Path
import collections
import csv
import json
import sys

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
PRE = R / '_p0pilot/cec_pretrain_ready_20261105'
RANK = R / '_p0pilot/cec_rank_seed42_20261105'
sys.path.insert(0, str(PRE))
import engine as E  # noqa: E402

T = E.T


def load_model(family, arm, stage):
    if family == 'mse':
        base = PRE / 'runs/main/seed42' / arm
        if stage == 'pre':
            return torch.load(base / 'pretrain/resume.pt', map_location='cpu', weights_only=False)['model']
        return torch.load(base / 'finetune/best.pt', map_location='cpu', weights_only=True)
    base = RANK / 'runs/main/seed42' / arm
    if stage == 'pre':
        return torch.load(base / 'pretrain/resume.pt', map_location='cpu', weights_only=False)['model']
    return torch.load(base / 'finetune/best.pt', map_location='cpu', weights_only=True)


def head_of(family, arm):
    base = (PRE if family == 'mse' else RANK) / 'runs/main/seed42' / arm / 'pretrain/resume.pt'
    pre = torch.load(base, map_location='cpu', weights_only=False)
    return {k: v.detach().cpu().numpy() for k, v in pre['projection'].items()}


def project(u, h):
    return np.maximum(u @ h['0.weight'].T + h['0.bias'], 0) @ h['2.weight'].T + h['2.bias']


def main():
    certs = E.read(O / 'validation_negative_certificates.json')
    cones_all = {c['cone_id']: c for c in E.read(E.J / 'final_cones.json')}
    E.set_inputs()
    data = T.load('trans', 'val', 'A')
    need = sorted({cid for c in certs for cid in c['cones']})
    rows, per_source_rows = [], []
    for family in ('mse', 'rank'):
        for arm in ('Z', 'R', 'P'):
            hp = head_of(family, arm)
            for stage in ('pre', 'best'):
                state = load_model(family, arm, stage)
                model = E.EncoderModel().cuda(); model.load_state_dict(state); model.eval()
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    h = model.encode(data['x'], data['edge'])
                    lens = torch.tensor([len(cones_all[c]['graph_rows']) for c in need], device='cuda')
                    flat = torch.tensor([i for c in need for i in cones_all[c]['graph_rows']], device='cuda')
                    seg = torch.repeat_interleave(torch.arange(len(need), device='cuda'), lens)
                    sums = torch.zeros(len(need), 64, device='cuda').index_add(0, seg, h[flat].float())
                    roots = torch.tensor([cones_all[c]['root_row'] for c in need], device='cuda')
                    u = torch.cat([h[roots], (sums / lens[:, None]).to(h.dtype)], 1).float().cpu().numpy()
                del model, h
                torch.cuda.empty_cache()
                ix = {c: i for i, c in enumerate(need)}
                for space, x in (('root64', u[:, :64]), ('concat128', u), ('projection32', project(u, hp))):
                    all_same, all_diff = [], []
                    per = []
                    for s in sorted({c['source'] for c in certs}):
                        same, diff = [], []
                        for c in certs:
                            if c['source'] != s: continue
                            a, ar, b, br = [x[ix[cid]].astype(float) for cid in c['cones']]
                            rms = lambda p, q: float(np.sqrt(np.mean((p - q) ** 2)))
                            s1, s2 = rms(a, ar), rms(b, br)
                            d1, d2 = rms(a, b), rms(ar, br)
                            same += [s1, s2]; diff += [d1, d2]
                        if not same:
                            continue
                        auc = float(roc_auc_score([1] * len(same) + [0] * len(diff), -np.r_[same, diff]))
                        per.append(dict(source=s, blocks=len(same) // 2, auc=auc,
                                        same_rms=float(np.mean(same)), different_rms=float(np.mean(diff))))
                        all_same += same; all_diff += diff
                    block_auc = float(roc_auc_score([1] * len(all_same) + [0] * len(all_diff), -np.r_[all_same, all_diff]))
                    rows.append(dict(family=family, arm=arm, stage=stage, space=space,
                                     block_balanced_auc=block_auc,
                                     source_balanced_auc=float(np.mean([p['auc'] for p in per])),
                                     same_rms=float(np.mean(all_same)), different_rms=float(np.mean(all_diff)),
                                     blocks=len(all_same) // 2))
                    for p in per:
                        per_source_rows.append(dict(family=family, arm=arm, stage=stage, space=space, **p))
                print(family, arm, stage, 'done', flush=True)
    with (O / 'expanded_comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with (O / 'expanded_per_source.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(per_source_rows[0])); w.writeheader(); w.writerows(per_source_rows)
    E.write(O / 'REEVAL_DONE.json', dict(eval_only=True, rows=len(rows)))


if __name__ == '__main__':
    main()
