"""Descriptive audit of SAT features on the Round 18/21 small-netlist set.

No SAT query, training, threshold tuning, or model fitting. Labels are used
only for this posthoc descriptive comparison, not for any model selection.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
OUT = T / 'sat_round21' / 'feature_diff'
R18 = T / 'sat_small_round18'
R19 = T / 'sat_diagnosis_round19'


def build_features():
    rec = json.loads((R18 / 'records.json').read_text(encoding='utf-8'))
    b = np.load(R18 / 'base_inputs.npz')
    real = np.load(R18 / 'real.npy')
    cand = np.load(R19 / 'candidate_boundary_repr.npz')
    g = torch.load(ROOT / 'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt',
                   map_location='cpu', weights_only=False, mmap=True)
    ids = b['global_ids']
    y = g.y[torch.tensor(ids)].numpy().astype(int)
    n = len(y)
    family = np.empty(n, object)
    view = np.empty(n, object)
    driver = np.empty(n, object)
    role = np.empty(n, object)
    k = np.zeros(n, int)
    for r in rec:
        i = int(r['local_node'])
        family[i] = r['family']
        view[i] = r['view']
        driver[i] = r['driver_type']
        role[i] = r['target_role']
        k[i] = r['k']
    state = cand['canonical_state_onehot'].astype(np.float32)
    valid = cand['pattern_valid']
    per_input = cand['per_input_original'].astype(np.float32)
    input_valid = cand['input_valid']
    counts = np.stack([(state[:, :, j] * valid).sum(1) for j in range(5)], axis=1)
    npat = valid.sum(1)
    denom = np.maximum(npat, 1)
    f = {}
    for j, name in enumerate(['infeasible', 'forced_zero', 'forced_one',
                              'feasible_undecided', 'solver_unknown']):
        f[f'n_{name}'] = counts[:, j]
        f[f'frac_{name}'] = counts[:, j] / denom
    n_forced = counts[:, 1] + counts[:, 2]
    f['n_patterns'] = npat
    f['n_forced'] = n_forced
    f['frac_forced'] = n_forced / denom
    f['frac_ones_on_forced'] = np.divide(counts[:, 2], n_forced,
                                         out=np.zeros(n), where=n_forced > 0)
    f['n_distinct_states'] = np.array([
        len(set(state[i, valid[i]].argmax(1))) if valid[i].any() else 0 for i in range(n)])
    def entropy(c):
        c = c[c > 0]
        if c.sum() == 0:
            return 0.0
        p = c / c.sum()
        return float(-(p * np.log(p)).sum())
    f['state_entropy'] = np.array([entropy(counts[i]) for i in range(n)])
    for q, name in enumerate(['pair_coverage', 'change_fraction', 'influence_valid']):
        vals = per_input[:, :, q]
        f[f'input_{name}_mean'] = np.divide((vals * input_valid).sum(1),
                                            np.maximum(input_valid.sum(1), 1))
        f[f'input_{name}_max'] = (vals * input_valid).max(1)
        f[f'n_inputs_{name}_positive'] = ((vals > 0) & input_valid).sum(1)
    f['n_inputs'] = input_valid.sum(1)
    X = pd.DataFrame(f)
    names = json.loads((T / 'sat_pair_round15/target18_manifest.json').read_text())['columns']
    for j, name in enumerate(names):
        X[name] = real[:, j]
    meta = pd.DataFrame(dict(
        y=y, family=family, view=view, driver=driver, role=role, k=k,
        inj=np.array(['__inj' in v for v in view]),
        covered=cand['covered'].astype(bool),
        local_node=np.arange(n), global_id=ids))
    return X, meta



def safe_auc(y, a):
    if len(np.unique(a)) < 2 or len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, a))


def safe_ap(y, a):
    if len(np.unique(y)) < 2:
        return None
    return float(average_precision_score(y, a))


def cliffs_delta(pos, neg):
    pos = np.asarray(pos, dtype=float)
    neg = np.asarray(neg, dtype=float)
    if len(pos) == 0 or len(neg) == 0:
        return None
    gt = sum(float((pos > v).sum()) for v in neg)
    lt = sum(float((pos < v).sum()) for v in neg)
    return (gt - lt) / (len(pos) * len(neg))


def smd(pos, neg):
    pos = np.asarray(pos, dtype=float)
    neg = np.asarray(neg, dtype=float)
    if len(pos) < 2 or len(neg) < 2:
        return None
    sp = np.sqrt(((len(pos) - 1) * pos.var(ddof=1) +
                  (len(neg) - 1) * neg.var(ddof=1)) /
                 max(len(pos) + len(neg) - 2, 1))
    if sp <= 1e-12:
        return 0.0 if abs(pos.mean() - neg.mean()) <= 1e-12 else None
    return float((pos.mean() - neg.mean()) / sp)


def summarize(X, meta, scope='covered'):
    base = meta.covered.values if scope == 'covered' else np.ones(len(meta), bool)
    rows = []
    for c in X.columns:
        a = X[c].values.astype(float)
        pos = a[base & (meta.y.values == 1)]
        neg = a[base & (meta.y.values == 0)]
        if len(pos) == 0 or len(neg) == 0:
            continue
        yy = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
        aa = np.r_[pos, neg]
        rows.append(dict(feature=c, n_pos=len(pos), n_neg=len(neg),
                         pos_mean=float(pos.mean()), neg_mean=float(neg.mean()),
                         pos_median=float(np.median(pos)), neg_median=float(np.median(neg)),
                         pos_nonzero=float((pos != 0).mean()),
                         neg_nonzero=float((neg != 0).mean()),
                         mean_diff=float(pos.mean() - neg.mean()),
                         smd=smd(pos, neg), cliffs_delta=cliffs_delta(pos, neg),
                         auc=safe_auc(yy, aa), ap=safe_ap(yy, aa),
                         pos_max=float(pos.max()), neg_max=float(neg.max()),
                         pos_min=float(pos.min()), neg_min=float(neg.min())))
    d = pd.DataFrame(rows)
    fam_stats = []
    for f in sorted(meta.family.unique()):
        m = base & (meta.family.values == f).astype(bool) & meta.inj.values
        for c in X.columns:
            a = X[c].values.astype(float)
            p = a[m & (meta.y.values == 1)]
            n = a[m & (meta.y.values == 0)]
            if len(p) and len(n):
                fam_stats.append(dict(family=f, feature=c, n_pos=len(p), n_neg=len(n),
                                      pos_mean=float(p.mean()), neg_mean=float(n.mean()),
                                      mean_diff=float(p.mean() - n.mean()),
                                      auc=safe_auc(np.r_[np.ones(len(p)), np.zeros(len(n))], np.r_[p, n])))
    fam = pd.DataFrame(fam_stats)
    gate_stats = []
    for gate in sorted(meta.driver.unique()):
        m = base & (meta.driver.values == gate) & (meta.role.values == 'comb_output')
        for c in X.columns:
            a = X[c].values.astype(float)
            p = a[m & (meta.y.values == 1)]
            n = a[m & (meta.y.values == 0)]
            if len(p) >= 2 and len(n) >= 10:
                gate_stats.append(dict(driver=gate, feature=c, n_pos=len(p), n_neg=len(n),
                                       pos_mean=float(p.mean()), neg_mean=float(n.mean()),
                                       mean_diff=float(p.mean() - n.mean()),
                                       auc=safe_auc(np.r_[np.ones(len(p)), np.zeros(len(n))], np.r_[p, n])))
    gate = pd.DataFrame(gate_stats)
    d['family_positive_fraction'] = [
        float((fam[fam.feature == c].mean_diff > 0).sum() / max((fam.feature == c).sum(), 1))
        for c in d.feature]
    d['gate_positive_fraction'] = [
        float((gate[gate.feature == c].mean_diff > 0).sum() / max((gate.feature == c).sum(), 1))
        for c in d.feature]
    return d.sort_values('auc', ascending=False), fam, gate


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    X, meta = build_features()
    counts = []
    for f in sorted(meta.family.unique()):
        for v in sorted(meta.view[meta.family == f].unique()):
            m = (meta.family == f) & (meta.view == v)
            counts.append(dict(family=f, view=v, inj=bool(meta.inj[m].iloc[0]),
                               nodes=int(m.sum()), positives=int(meta.y[m].sum()),
                               negatives=int((meta.y[m] == 0).sum()),
                               covered=int(meta.covered[m].sum()),
                               uncovered=int((~meta.covered[m]).sum()),
                               comb_output=int((meta.role[m] == 'comb_output').sum()),
                               dff_data_D=int((meta.role[m] == 'DFF_data_D').sum())))
    pd.DataFrame(counts).to_csv(OUT / 'class_counts.csv', index=False, encoding='utf-8-sig')

    overall, fam, gate = summarize(X, meta, scope='covered')
    inj = (meta.covered & meta.inj).values
    comb = (meta.covered & (meta.role == 'comb_output')).values

    def summarize_mask(mask):
        rows = []
        for c in X.columns:
            a = X[c].values.astype(float)
            pos = a[mask & (meta.y.values == 1)]
            neg = a[mask & (meta.y.values == 0)]
            if len(pos) == 0 or len(neg) == 0:
                continue
            yy = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
            aa = np.r_[pos, neg]
            rows.append(dict(feature=c, n_pos=len(pos), n_neg=len(neg),
                             pos_mean=float(pos.mean()), neg_mean=float(neg.mean()),
                             pos_median=float(np.median(pos)), neg_median=float(np.median(neg)),
                             pos_nonzero=float((pos != 0).mean()),
                             neg_nonzero=float((neg != 0).mean()),
                             mean_diff=float(pos.mean() - neg.mean()),
                             smd=smd(pos, neg), cliffs_delta=cliffs_delta(pos, neg),
                             auc=safe_auc(yy, aa), ap=safe_ap(yy, aa),
                             pos_max=float(pos.max()), neg_max=float(neg.max())))
        return pd.DataFrame(rows).sort_values('auc', ascending=False)

    within_inj = summarize_mask(inj)
    within_comb = summarize_mask(comb)
    overall.to_csv(OUT / 'feature_overall.csv', index=False, encoding='utf-8-sig')
    within_inj.to_csv(OUT / 'feature_within_inj.csv', index=False, encoding='utf-8-sig')
    within_comb.to_csv(OUT / 'feature_within_comb_output.csv', index=False, encoding='utf-8-sig')
    fam.to_csv(OUT / 'feature_by_family.csv', index=False, encoding='utf-8-sig')
    gate.to_csv(OUT / 'feature_by_gate.csv', index=False, encoding='utf-8-sig')

    strata = []
    for (f, d, k, r), m in meta[meta.covered].groupby(['family', 'driver', 'k', 'role']):
        pos = int(meta.loc[m.index, 'y'].sum())
        neg = int((meta.loc[m.index, 'y'] == 0).sum())
        if pos:
            strata.append(dict(family=f, driver=d, k=int(k), role=r,
                               nodes=int(len(m)), positives=pos, negatives=neg,
                               positive_fraction=float(pos / len(m))))
    pd.DataFrame(strata).sort_values(['family', 'driver', 'k']).to_csv(
        OUT / 'strata_counts.csv', index=False, encoding='utf-8-sig')

    def top(df, n=12):
        z = df.copy()
        z['score'] = pd.to_numeric(z['auc'], errors='coerce').fillna(0.5)
        z['consistency'] = z.get('family_positive_fraction', 0) * z.get('gate_positive_fraction', 0)
        return z.sort_values(['score', 'consistency'], ascending=False).head(n).to_dict(orient='records')

    summary = dict(
        status='descriptive_posthoc_no_training',
        data=dict(nodes=int(len(meta)), positives=int(meta.y.sum()),
                  negatives=int((meta.y == 0).sum()), covered=int(meta.covered.sum()),
                  covered_positives=int((meta.covered & (meta.y == 1)).sum()),
                  covered_negatives=int((meta.covered & (meta.y == 0)).sum()),
                  positives_by_family=meta[meta.y == 1].family.value_counts().to_dict(),
                  positives_by_view=meta[meta.y == 1].view.value_counts().to_dict(),
                  positives_by_driver=meta[meta.y == 1].driver.value_counts().to_dict(),
                  positives_by_role=meta[meta.y == 1].role.value_counts().to_dict(),
                  positives_by_k=meta[meta.y == 1].k.value_counts().to_dict()),
        comparisons=dict(
            overall_covered='positive vs all covered negatives',
            within_inj='positive vs negative nodes in the same inj views',
            within_comb_output='positive vs negative comb_output nodes',
            by_family='positive vs same-family inj-view negatives',
            by_gate='positive vs same-driver comb_output negatives (>=2 pos, >=10 neg)',
            strata='family x driver x k x role counts; all positives are comb_output'),
        top_overall=top(overall),
        top_within_inj=top(within_inj),
        top_within_comb_output=top(within_comb),
        notes=['No model training or SAT query in this audit.',
               'All positives are covered comb_output gates; comparisons within inj/comb/gate are essential.',
               'Single-feature AUC/AP are descriptive; gate/family confounding is reported, not adjusted away.',
               'The 144 unexpanded-target nodes are excluded from covered comparisons.'])
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(data=summary['data'], top_within_inj=summary['top_within_inj'][:8],
                          top_within_comb=summary['top_within_comb_output'][:8]),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

