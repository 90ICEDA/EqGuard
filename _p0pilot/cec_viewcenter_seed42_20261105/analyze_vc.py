"""Evaluate the per-view centering run: detection + role x recipe function AUC (read-only)."""
from pathlib import Path
import collections, csv, json, sys
import numpy as np
import torch
from sklearn.metrics import roc_auc_score

R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
PRE = R / '_p0pilot/cec_pretrain_ready_20261105'
CERT = R / '_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json'
sys.path.insert(0, str(PRE))
import engine as E  # noqa: E402

T = E.T


def role(s):
    return 'a4trojan' if 'a4trojan' in s else ('injection' if '__inj' in s else 'control')


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
            t = T.metrics(p, 'trans', split, thr)[0]['trusted']
            rows.append(dict(arm=arm, split=split, threshold=thr, selected_update=sel['epoch'], ap=t['ap'],
                             auc=t['auc'], r1=t['r1'], r5=t['r5'], control_fpr=t.get('control_fpr', '')))
        del model, best
        torch.cuda.empty_cache()
    with (O / 'detection_metrics.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows


def mechanism():
    certs = E.read(CERT)
    cones = {c['cone_id']: c for c in E.read(E.J / 'final_cones.json')}
    pairs = E.read(E.J / 'final_pairs.json')
    byid = {p['pair_id']: p for p in pairs}

    def recipe_of(pid):
        p = byid[pid]
        return '|'.join(sorted([cones[p['left_cone']]['view'].split('__')[-1], cones[p['right_cone']]['view'].split('__')[-1]]))

    for c in certs:
        c['role'] = role(c['source']); c['recipe'] = recipe_of(c['pair_a'])
    E.set_inputs()
    data = T.load('trans', 'val', 'A')
    need = sorted({cid for c in certs for cid in c['cones']})
    rows = []
    for arm in ['Z', 'R', 'P']:
        pre = torch.load(O / f'runs/main/seed42/{arm}/pretrain/resume.pt', map_location='cpu', weights_only=False)
        head = {k: v.detach().cpu().numpy() for k, v in pre['projection'].items()}
        for stage in ['pre', 'best']:
            state = pre['model'] if stage == 'pre' else torch.load(O / f'runs/main/seed42/{arm}/finetune/best.pt', map_location='cpu', weights_only=True)
            model = E.EncoderModel().cuda(); model.load_state_dict(state); model.eval()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                h = model.encode(data['x'], data['edge'])
                lens = torch.tensor([len(cones[c]['graph_rows']) for c in need], device='cuda')
                flat = torch.tensor([i for c in need for i in cones[c]['graph_rows']], device='cuda')
                seg = torch.repeat_interleave(torch.arange(len(need), device='cuda'), lens)
                sums = torch.zeros(len(need), 64, device='cuda').index_add(0, seg, h[flat].float())
                roots = torch.tensor([cones[c]['root_row'] for c in need], device='cuda')
                u = torch.cat([h[roots], (sums / lens[:, None]).to(h.dtype)], 1).float().cpu().numpy()
            del model, h
            torch.cuda.empty_cache()
            ix = {c: i for i, c in enumerate(need)}
            def project(x):
                return np.maximum(x @ head['0.weight'].T + head['0.bias'], 0) @ head['2.weight'].T + head['2.bias']
            for space, x in (('root64', u[:, :64]), ('projection32', project(u))):
                groups = collections.defaultdict(lambda: dict(same=[], diff=[], blocks=0))
                for c in certs:
                    key = (c['role'], c['recipe'])
                    a, ar, b, br = [x[ix[cid]].astype(float) for cid in c['cones']]
                    rms = lambda p, q: float(np.sqrt(np.mean((p - q) ** 2)))
                    groups[key]['same'] += [rms(a, ar), rms(b, br)]
                    groups[key]['diff'] += [rms(a, b), rms(ar, br)]
                    groups[key]['blocks'] += 1
                for (ro, rec), d in groups.items():
                    rows.append(dict(arm=arm, stage=stage, space=space, role=ro, recipe=rec, blocks=d['blocks'],
                                     auc=float(roc_auc_score([1] * len(d['same']) + [0] * len(d['diff']), -np.r_[d['same'], d['diff']])),
                                     same_rms=float(np.mean(d['same'])), different_rms=float(np.mean(d['diff']))))
            print(arm, stage, 'done', flush=True)
    with (O / 'viewcenter_role_recipe.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows


if __name__ == '__main__':
    det = detection()
    mech = mechanism()
    E.write(O / 'ANALYSIS_VIEWCENTER.json', dict(detection=det, mechanism=mech, eval_only=True))
    print('done')
