"""Directory-level no-keep counts (read-only): design dirs, pairs, cec/manifest, keep removal, GT paths."""
import csv, json
from pathlib import Path

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
BASE = R / 'generate_trans/yslib_test'
OUT = R / '_p0pilot/four_group_contract_20261109'
HOSTS = ('rs232t1000', 's15850t100', 's35932t200')
KINDS = ('injalpha', 'injdelta')
RECS = ('ys_abc', 'ys_aig', 'ys_nand')


def main():
    rep = {}
    dirs = [d for d in BASE.rglob('*') if d.is_dir()]
    rep['n_dirs'] = len(dirs)
    rep['sample_dirs'] = [d.name for d in dirs[:20]]
    # find files by token
    allf = [p for p in BASE.rglob('*') if p.is_file()]
    rep['n_files'] = len(allf)
    pairs = {}
    for h in HOSTS:
        for k in KINDS:
            for rec in RECS:
                tok = f'{h}__{k}'
                hits = [p for p in allf if tok in p.name and rec in p.name]
                pairs[f'{tok}__{rec}'] = dict(n=len(hits), names=[p.name for p in hits][:8],
                                              dirs=sorted({p.parent.name for p in hits})[:5])
    rep['pairs'] = pairs
    cec = BASE / 'cec_tolib.csv'
    if cec.exists():
        rows = list(csv.DictReader(cec.open(encoding='utf-8-sig')))
        rep['cec_rows'] = len(rows); rep['cec_empty'] = sum(1 for r in rows if not (r.get('cec') or '').strip())
        rep['cec_cols'] = list(rows[0].keys()) if rows else []
    cm = BASE / 'convert_manifest.csv'
    if cm.exists():
        rows = list(csv.DictReader(cm.open(encoding='utf-8-sig')))
        rep['manifest_rows'] = len(rows); rep['manifest_clean_true'] = sum(1 for r in rows if str(r.get('clean', '')).lower() == 'true')
        rep['manifest_cols'] = list(rows[0].keys()) if rows else []
    script = R / 'phase2/ys/keep_ablation.py'
    if script.exists():
        t = script.read_text(encoding='utf-8', errors='ignore')
        rep['keep_script_has_noattr'] = 'noattr' in t
        rep['keep_script_mentions_keep'] = t.lower().count('keep')
        rep['keep_script_lines'] = [l.strip() for l in t.splitlines() if 'keep' in l.lower() or 'noattr' in l][:15]
    for name in ('DFF', 'mappings', 'alpha', 'delta'):
        rep[f'gt_{name}'] = [str(p.relative_to(R)) for p in R.rglob(f'*{name}*') if p.is_file()][:8]
    (OUT / 'NO_KEEP_DIRS.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in rep.items() if k not in ('pairs', 'gt_DFF', 'gt_mappings', 'gt_alpha', 'gt_delta')}, ensure_ascii=False)[:1200])


if __name__ == '__main__':
    main()
