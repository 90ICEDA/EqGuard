"""Evaluate the ranking single-factor run: detection metrics + function discrimination (read-only)."""
from pathlib import Path
import collections, csv, json, sys
import numpy as np
import torch
from sklearn.metrics import roc_auc_score

R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
PRE = R / '_p0pilot/cec_pretrain_ready_20261105'
OLD = R / '_p0pilot/cec_mechanism_seed42_20261105'
sys.path.insert(0, str(PRE))
import engine as E  # noqa: E402

T = E.T


def detection():
    E.set_inputs()
    rows = []
    for arm in ['Z', 'R', 'P']:
        base = O / 'runs/main/seed42' / arm
        best = torch.load(base / 'finetune/best.pt', map_location='cuda', weights_only=True)
        model = E.EncoderModel().cuda(); model.load_state_dict(best); model.eval()
        pv = np.load(base / 'finetune/selected_val_scores.npy')
        va = T.arrays('trans', 'val')
        thr = float(np.nextafter(np.quantile(pv[va['trusted'] & (va['y'] == 0)], .95), np.inf))
        pt = E.predict(model, 'trans', 'test')
        np.save(base / 'finetune/test_scores.npy', pt)
        sel = E.read(base / 'finetune/COMPLETE.json')['best']
        for split, p in (('val', pv), ('test', pt)):
            summary, _ = T.metrics(p, 'trans', split, thr)
            t = summary['trusted']
            rows.append(dict(arm=arm, split=split, operation='historical_fpr5', threshold=thr,
                             selected_update=sel['epoch'], ap=t['ap'], auc=t['auc'], r1=t['r1'], r5=t['r5'],
                             recall=t.get('recall', ''), views=t.get('views', ''), control_fpr=t.get('control_fpr', '')))
        del model, best
        torch.cuda.empty_cache()
    with (O / 'detection_metrics.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows


def mechanism():
    E.set_inputs()
    plan = E.read(OLD / 'PREPARED.json')
    cert = E.read(OLD / 'validation_negative_certificates.json')
    pairs = E.read(E.J / 'final_pairs.json')
    cones = {c['cone_id']: c for c in E.read(E.J / 'final_cones.json')}
    ids = plan['val_cones']; ix = {c: i for i, c in enumerate(ids)}
    data = T.load('trans', 'val', 'A')
    source_of = {p[k]: p['source_object'] for p in pairs if p['split'] == 'val' for k in ['left_cone', 'right_cone']}
    ss = [source_of[c] for c in ids]; cnt = collections.Counter(ss)
    wgt = np.array([1 / len(cnt) / cnt[s] for s in ss])

    def per_source(x):
        recs = []
        for s in sorted({c['source'] for c in cert}):
            same, diff = [], []
            for c in cert:
                if c['source'] != s:
                    continue
                a, ar, b, br = [x[ix[cid]].astype(float) for cid in c['cones']]
                rms = lambda u, v: float(np.sqrt(np.mean((u - v) ** 2)))
                same += [rms(a, ar), rms(b, br)]
                diff += [rms(a, b), rms(ar, br)]
            recs.append(dict(source=s, auc=float(roc_auc_score([1] * len(same) + [0] * len(diff), -np.r_[same, diff])),
                             same_rms=float(np.mean(same)), different_rms=float(np.mean(diff)), blocks=len(same) // 2))
        return recs

    def spectral(x):
        center = x - wgt @ x
        ev = np.maximum(np.linalg.eigvalsh(center.T @ (wgt[:, None] * center)), 0)
        prob = ev / ev.sum() if ev.sum() > 0 else ev
        return float(np.exp(-np.sum(prob[prob > 0] * np.log(prob[prob > 0])))) if ev.sum() > 0 else 0.0

    def project(u, h):
        return np.maximum(u @ h['0.weight'].T + h['0.bias'], 0) @ h['2.weight'].T + h['2.bias']

    rows, per_source_rows = [], []
    for arm in ['Z', 'R', 'P']:
        pre = torch.load(O / f'runs/main/seed42/{arm}/pretrain/resume.pt', map_location='cpu', weights_only=False)
        head = {k: v.detach().cpu().numpy() for k, v in pre['projection'].items()}
        for stage in ['pre', 'best']:
            state = pre['model'] if stage == 'pre' else torch.load(O / f'runs/main/seed42/{arm}/finetune/best.pt', map_location='cpu', weights_only=True)
            model = E.EncoderModel().cuda(); model.load_state_dict(state); model.eval()
            chunks = []
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                h = model.encode(data['x'], data['edge'])
                for start in range(0, len(ids), 64):
                    ci = ids[start:start + 64]
                    lens = torch.tensor([len(cones[c]['graph_rows']) for c in ci], device='cuda')
                    flat = torch.tensor([i for c in ci for i in cones[c]['graph_rows']], device='cuda')
                    seg = torch.repeat_interleave(torch.arange(len(ci), device='cuda'), lens)
                    sums = torch.zeros(len(ci), 64, device='cuda').index_add(0, seg, h[flat].float())
                    roots = torch.tensor([cones[c]['root_row'] for c in ci], device='cuda')
                    chunks.append(torch.cat([h[roots], (sums / lens[:, None]).to(h.dtype)], 1).float().cpu().numpy())
            u = np.concatenate(chunks)
            np.save(O / f'{arm}_{stage}_val_concat128.npy', u)
            for sp, x in (('root64', u[:, :64]), ('concat128', u), ('projection32', project(u, head))):
                recs = per_source(x)
                rows.append(dict(arm=arm, stage=stage, space=sp,
                                 same_vs_different_auc=float(np.mean([r['auc'] for r in recs])),
                                 same_rms=float(np.mean([r['same_rms'] for r in recs])),
                                 different_rms=float(np.mean([r['different_rms'] for r in recs])),
                                 effective_rank=spectral(x)))
                for r in recs:
                    per_source_rows.append(dict(arm=arm, stage=stage, space=sp, **r))
            del model, h, u
            torch.cuda.empty_cache()
    with (O / 'mechanism_comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with (O / 'per_source_discrimination.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(per_source_rows[0])); w.writeheader(); w.writerows(per_source_rows)
    return rows


if __name__ == '__main__':
    det = detection()
    mech = mechanism()
    E.write(O / 'ANALYSIS_RANK.json', dict(detection=det, mechanism=mech, eval_only=True, new_training=0))
    print('done')
