"""v6: corrected expansion stats, normal/A-B from saved predictions, four-group manifests."""
import csv, json, sys, hashlib
from pathlib import Path
import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
EX = R / '_p0pilot/expansion_boundary_20261109'
V5 = R / '_p0pilot/heldout_recipe_v5_20261109'
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0, str(V5)); sys.path.insert(0, str(R / '_p0pilot/control_signed_carrier_20261109_v3'))
import fold_io as F
import Signed_common as S

ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')
BASE = ('ys_abc', 'ys_id', 'ys_opt')
ADD = ('ys_aig', 'ys_nand')


def sha(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def contract(): return json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))


def main():
    OUT.mkdir(exist_ok=True)
    c = contract()
    # ---------- 1. corrected stats (test panel, diagnostic only) ----------
    vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
    y = np.load(B / 'inputs/trans_test/y.npy'); tr = np.load(B / 'inputs/trans_test/trusted.npy'); ph = np.load(B / 'inputs/trans_test/physical.npy')
    stats = {}
    for rec in ALL:
        stats[rec] = dict(views=0, physical=0, trusted=0, pos=0, full_members=0, trusted_members=0,
                          cones=0, depth_max=0, depth_known=0, depth_unknown=0, exposure={})
    # cones from cache + depth from builder
    for v, lay in vs.items():
        rec = v.split('__')[-1]
        a, b = lay['start'], lay['stop']
        d = stats[rec]; d['views'] += 1; d['physical'] += int(ph[a:b].sum())
        d['trusted'] += int((tr[a:b] & ph[a:b]).sum()); d['pos'] += int(((y[a:b] == 1) & tr[a:b] & ph[a:b]).sum())
    with (OLD / 'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != 'test' or r['kind'] != 'D':
                continue
            rec = r['view'].split('__')[-1]
            mem = [int(x) for x in r['phys_rows'].split('|') if x]
            tmem = [x for x in mem if bool(tr[x]) and bool(ph[x])]
            d = stats[rec]; d['cones'] += 1; d['full_members'] += len(mem); d['trusted_members'] += len(tmem)
            for x in set(mem):
                d['exposure'][x] = d['exposure'].get(x, 0) + 1
    for rec, d in stats.items():
        d['trusted_cov'] = d['trusted'] / max(1, d['physical'])
        d['pos_density'] = d['pos'] / max(1, d['physical'])
        d['avg_full_members'] = d['full_members'] / max(1, d['cones'])
        d['avg_trusted_members'] = d['trusted_members'] / max(1, d['cones'])
        ex = np.array(list(d['exposure'].values())) if d['exposure'] else np.array([0])
        d['member_exposure_mean'] = float(ex.mean()); d['member_exposure_max'] = int(ex.max())
        d['shared_member_frac'] = float((ex > 1).mean())
        del d['exposure']
    # ---------- 2. normal / A-B from saved predictions ----------
    normal = {}
    for rec in ('ys_abc', 'ys_aig', 'ys_nand'):
        for arm in ('N', 'NC'):
            for seed in (1, 2):
                for tag in ('best', 'last'):
                    p = EX / f'{rec}_{arm}_s{seed}_{tag}_alltest.npz'
                    if not p.exists():
                        continue
                    z = np.load(p)
                    mean, std = F.fold_stats(rec)
                    g = dict(rows=z['rows'], y=z['y'], trusted=z['trusted'], physical=z['physical'],
                             views={v['view']: v for v in c['shared_inputs']['trans_test']['views']})
                    # val thresholds from v5 preds
                    zv = np.load(V5 / rec / arm / f'seed{seed}' / f'{tag}_pred.npz')
                    dv = np.load(F.V4 / f'{rec}_val_map.npz')
                    yv, tv = np.asarray(dv['y']), np.asarray(dv['trusted'])
                    pv = tv & (yv == 1)
                    out = {}
                    for tgt in ('0.8', '0.9', '0.95'):
                        need = int(np.ceil(float(tgt) * pv.sum()))
                        thr = float(np.sort(zv['val'][pv])[::-1][need - 1])
                        ctl = [v for v in g['views'] if 'ctl' in v]
                        node_num = node_den = 0; alarm = []
                        for v in ctl:
                            a, b = np.searchsorted(g['rows'], [g['views'][v]['start'], g['views'][v]['stop']])
                            tt = g['trusted'][a:b] & g['physical'][a:b]; yy = g['y'][a:b]; ss = z['scores'][a:b]
                            if not tt.any(): continue
                            alarm.append(float(ss[tt].max() >= thr))
                            neg = tt & (yy == 0); node_num += int((ss[neg] >= thr).sum()); node_den += int(neg.sum())
                        out[tgt] = dict(threshold=thr, ctl_views=len(ctl), alarm=float(np.mean(alarm)) if alarm else None,
                                        node_fpr=float(node_num / max(1, node_den)))
                    normal[f'{rec}_{arm}_{seed}_{tag}'] = out
    # ---------- 3. four-group manifest ----------
    tr_vs = {v['view']: v for v in c['shared_inputs']['trans_train']['views']}
    def views_for(pool):
        return [v for v in tr_vs if v.split('__')[-1] in pool]
    A = views_for(BASE); Bv = views_for(BASE + ADD)
    # source support and per-source positive quota (min positives across groups per source)
    def src_pos(views):
        out = {}
        for v in views:
            lay = tr_vs[v]; a, b = lay['start'], lay['stop']
            s = v.split('__ys_')[0]
            out[s] = out.get(s, 0) + int(((y[a:b] if False else np.load(B / 'inputs/trans_train/y.npy')[a:b]) == 1).sum())
        return out
    ya = np.load(B / 'inputs/trans_train/y.npy'); ta = np.load(B / 'inputs/trans_train/trusted.npy'); pa = np.load(B / 'inputs/trans_train/physical.npy')
    def pos_by_src(views):
        out = {}
        for v in views:
            lay = tr_vs[v]; a, b = lay['start'], lay['stop']; s = v.split('__ys_')[0]
            out[s] = out.get(s, 0) + int(((ya[a:b] == 1) & ta[a:b] & pa[a:b]).sum())
        return out
    pa_src = pos_by_src(A); pb_src = pos_by_src(Bv)
    common_src = sorted(set(pa_src) & set(pb_src))
    quota = {s: min(pa_src[s], pb_src[s]) for s in common_src}
    man = dict(A_views=len(A), B_views=len(Bv), A_sources=len(pa_src), B_sources=len(pb_src),
               common_sources=len(common_src), quota_total=int(sum(quota.values())),
               unmatched_A=sorted(set(pa_src) - set(pb_src)), unmatched_B=sorted(set(pb_src) - set(pa_src)),
               quota=quota, base_recipes=list(BASE), add_recipes=list(ADD))
    (OUT / 'MANIFEST.json').write_text(json.dumps(dict(manifest=man, stats=stats, normal=normal), indent=2), encoding='utf-8')
    print(json.dumps({k: (v if not isinstance(v, dict) else len(v)) for k, v in man.items() if k != 'quota'}, ensure_ascii=False))
    print('stats', {k: (round(v['avg_full_members'], 2), round(v['avg_trusted_members'], 2), v['member_exposure_max']) for k, v in stats.items()})


if __name__ == '__main__':
    main()
