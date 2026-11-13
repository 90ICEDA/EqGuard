"""Stratify pair diagnostics by role (injection/control) x recipe pair (read-only)."""
from pathlib import Path
import collections
import csv
import json
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
J = R / '_p0pilot/cec_joint_expand_20261105'
PRE = R / '_p0pilot/cec_pretrain_ready_20261105'
sys.path.insert(0, str(PRE))


def role(source):
    if 'a4trojan' in source:
        return 'a4trojan'
    return 'injection' if '__inj' in source else 'control'


def main():
    pairs = json.loads((J / 'final_pairs.json').read_text(encoding='utf-8'))
    cones = {c['cone_id']: c for c in json.loads((J / 'final_cones.json').read_text(encoding='utf-8'))}

    def recipe_of(pid):
        p = byid[pid]
        a, b = cones[p['left_cone']]['view'].split('__')[-1], cones[p['right_cone']]['view'].split('__')[-1]
        return '|'.join(sorted([a, b]))

    byid = {p['pair_id']: p for p in pairs}

    # ---- train blocks: join schedule -> pair_a -> recipe ----
    schedule = json.loads((PRE / 'schedule.json').read_text(encoding='utf-8'))
    sched = {(r['update'], r['block_id']): r for r in schedule if r['mode'] == 'main' and r['seed'] == 42}
    blocks = pd.read_csv(R / '_p0pilot/cec_dropout_seed42_20261105/functional_train_blocks.csv')
    rows = []
    for _, r in blocks.iterrows():
        s = sched.get((int(r['update']), r['block_id']))
        if s is None:
            continue
        rows.append(dict(arm=r['arm'], source=r['source'], role=role(r['source']), recipe=recipe_of(s['pair_a']),
                         real=r['real_rms'], perm=r['permuted_rms'], neg=r['negative_rms']))
    tr = pd.DataFrame(rows)
    tr['m_perm'] = tr['perm'] - tr['real']
    tr['m_neg'] = tr['neg'] - tr['real']
    trg = tr.groupby(['arm', 'role', 'recipe']).agg(blocks=('real', 'size'), real=('real', 'mean'),
                                                    m_perm=('m_perm', 'mean'), m_neg=('m_neg', 'mean')).reset_index()
    trg.round(4).to_csv(O / 'train_role_recipe_margins.csv', index=False, encoding='utf-8-sig')

    # ---- val certificates: group by role x recipe ----
    certs = json.loads((O / 'validation_negative_certificates.json').read_text(encoding='utf-8'))
    for c in certs:
        c['role'] = role(c['source'])
        c['recipe'] = recipe_of(c['pair_a'])

    # distances come from the saved pooled embeddings: recompute with a cheap linear probe-free pass
    # (reuse cached concat128 saved in cec_rank / analyze_rank dirs is not available for MSE arms here)
    import torch
    sys.path.insert(0, str(PRE))
    import engine as E
    T = E.T
    E.set_inputs()
    data = T.load('trans', 'val', 'A')
    need = sorted({cid for c in certs for cid in c['cones']})
    out_rows = []
    for family, base_dir in (('mse', PRE), ('rank', R / '_p0pilot/cec_rank_seed42_20261105')):
        for arm in ('Z', 'R', 'P'):
            base = base_dir / 'runs/main/seed42' / arm
            for stage in ('pre', 'best'):
                state = torch.load(base / ('pretrain/resume.pt' if stage == 'pre' else 'finetune/best.pt'),
                                   map_location='cpu', weights_only=False if stage == 'pre' else True)
                state = state['model'] if stage == 'pre' else state
                model = E.EncoderModel().cuda(); model.load_state_dict(state); model.eval()
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    h = model.encode(data['x'], data['edge'])
                    lens = torch.tensor([len(cones[c]['graph_rows']) for c in need], device='cuda')
                    flat = torch.tensor([i for c in need for i in cones[c]['graph_rows']], device='cuda')
                    seg = torch.repeat_interleave(torch.arange(len(need), device='cuda'), lens)
                    sums = torch.zeros(len(need), 64, device='cuda').index_add(0, seg, h[flat].float())
                    roots = torch.tensor([cones[c]['root_row'] for c in need], device='cuda')
                    u = torch.cat([h[roots], (sums / lens[:, None]).to(h.dtype)], 1).float().cpu().numpy()[:, :64]
                del model, h
                torch.cuda.empty_cache()
                ix = {c: i for i, c in enumerate(need)}
                groups = collections.defaultdict(lambda: dict(same=[], diff=[], blocks=0))
                for c in certs:
                    key = (c['role'], c['recipe'])
                    a, ar, b, br = [u[ix[cid]].astype(float) for cid in c['cones']]
                    rms = lambda p, q: float(np.sqrt(np.mean((p - q) ** 2)))
                    groups[key]['same'] += [rms(a, ar), rms(b, br)]
                    groups[key]['diff'] += [rms(a, b), rms(ar, br)]
                    groups[key]['blocks'] += 1
                for (ro, rec), d in groups.items():
                    out_rows.append(dict(family=family, arm=arm, stage=stage, role=ro, recipe=rec, blocks=d['blocks'],
                                         auc=float(roc_auc_score([1] * len(d['same']) + [0] * len(d['diff']), -np.r_[d['same'], d['diff']])),
                                         same_rms=float(np.mean(d['same'])), different_rms=float(np.mean(d['diff']))))
                print(family, arm, stage, 'done', flush=True)
    pd.DataFrame(out_rows).round(4).to_csv(O / 'val_role_recipe_auc.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    main()
