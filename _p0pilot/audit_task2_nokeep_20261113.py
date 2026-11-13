"""Read existing keep/no-keep assets, certificates, and evaluation records."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parent
PANEL = P / 'heldout_composition_20261110'
CONFIRM = P / 'lcone_confirmation_assets_20261112'
STATUS = re.compile(r'Of those cells (\d+) are proven and (\d+) are unproven')
FRONTENDS = re.compile(r'^([23])\. Executing Verilog-2005 frontend: (.+)$', re.M)
KEEP_ATTR = re.compile(r'\(\*[^*]*\bkeep\b[^*]*\*\)', re.S | re.I)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return [{k: v.strip().lstrip('\ufeff') for k, v in r.items()} for r in csv.DictReader(f)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(path):
    clean = path.strip().replace('\ufeff','').replace('\\','/')
    if clean.startswith('/mnt/'):
        clean = clean[5] + ':' + clean[6:]
    return ROOT / clean


def inspect_log(path):
    text = path.read_text(encoding='utf-8')
    files = {step: local(p) for step,p in FRONTENDS.findall(text)}
    assert files.keys() == {'2','3'} and all(p.is_file() for p in files.values())
    assert 'Equivalence successfully proven!' in text
    proven, unproven = map(int, STATUS.findall(text)[-1])
    assert proven and unproven == 0
    return files['2'], files['3'], proven


def check_keep(stage, candidate, source, scheme):
    scripts = stage / 'logs'
    stem = candidate.stem
    script = (scripts / f'{stem}.ys').read_text(encoding='utf-8')
    assert (scripts / f'{stem}.rc').read_text().strip() == '0'
    assert str(source.relative_to(ROOT)).replace('\\','/') in script
    actions = [line for line in script.splitlines() if re.search(r'\b(?:attrmap|setattr)\b.*\bkeep\b', line)]
    if scheme == 'keepnone':
        assert not actions
    else:
        assert len(actions) == 1 and 'setattr -set keep 1' in actions[0]
        assert script.index(actions[0]) < script.index('\nopt -full')
    return dict(script_sha256=sha(scripts / f'{stem}.ys'), scheme_keep_action=bool(actions),
                source_explicit_keep_count=len(KEEP_ATTR.findall(source.read_text(encoding='utf-8'))))


def main():
    layouts = read(P / 'control_boundary_v3_20261104/input_contract.json')['shared_inputs']
    by_split = {s: {v['view'].split('__keep')[0].split('__ys_')[0] for v in obj['views']}
                for s,obj in layouts.items()}
    registry = {local(r['target']):r for r in read(P / 'lcone_head_gate_20261112/CONFIRMATION_REGISTRY.json')['registered']
                if r['status'] == 'registered_evidence_only'}
    extra = {local(r['target']):r for r in read(P / 'lcone_head_protocol_20261112/SOURCE_ONLY_EVIDENCE.json')['results']}
    graph_report = {r['view']:r for r in read(CONFIRM / 'GRAPH_REPORT.json')['views']}
    structural = {(r['host'],r['view'],r['recipe']):r for stage in ('2A','2B') for r in rows(PANEL / f'KEEP_STAGE{stage}.csv')}
    assert len(structural) == 20
    outputs = []
    for tag in ('A','B'):
        stage = ROOT / f'generate_trans/keepab_panel_20_stage2{tag.lower()}'
        for r in rows(PANEL / f'CEC_STAGE3{tag}.csv'):
            log = local(r['log'])
            orig, target, count = inspect_log(log)
            assert orig == local(r['reference']) and orig.stem == r['view']
            assert target.stem == f"{r['view']}__{r['scheme']}__ys_{r['recipe']}" and target.is_relative_to(stage / 'conv')
            assert r['status'] == 'PASS' and int(r['unproven']) == 0 and count == int(r['total']) == int(r['proven'])
            row = dict(host=r['host'], source=orig.stem, recipe=r['recipe'], keep=r['scheme'],
                       split='|'.join(s for s, ss in by_split.items() if orig.stem in ss) or 'source_not_in_task1_splits',
                       host_in_train=any(s.endswith('train') and any(x.startswith(r['host']+'__') for x in ss) for s,ss in by_split.items()),
                       host_in_val=any(s.endswith('val') and any(x.startswith(r['host']+'__') for x in ss) for s,ss in by_split.items()),
                       path=target.relative_to(ROOT).as_posix(), target_sha256=sha(target), log_sha256=sha(log), proven=count,
                       **check_keep(stage,target,orig,r['scheme']))
            s = structural[r['host'],r['view'],r['recipe']]
            assert s['status'] == 'supported' and s['none_dff'] == s['cur_dff']
            row.update(anchor_names=int(s['none_anchor' if r['scheme']=='keepnone' else 'cur_anchor']))
            row.update(functional_gt='not_bound', D_positive=None, D_negative=None, PO_positive=None, PO_negative=None,
                       graph='not_bound', existing_model_result='none')
            gt = registry.get(target) or extra.get(target)
            if gt:
                assert gt['sha256']['target'] == row['target_sha256'] and gt['sha256']['log'] == row['log_sha256']
                assert gt['sha256'].get('source',gt['sha256'].get('original')) == sha(orig)
                support = Counter(f"{e['kind']}_{e['status']}" for e in gt['endpoints'])
                row.update({k:support[k] for k in ('D_positive','D_negative','PO_positive','PO_negative')})
                row['functional_gt'] = 'paired_D_PO' if support['D_positive'] and support['PO_positive'] else 'PO_positive_only'
            if target.stem in graph_report:
                item = graph_report[target.stem]
                assert item['target_sha256'] == row['target_sha256']
                assert item['graph_sha256'] == sha(CONFIRM / target.stem / 'GRAPH_ENDPOINTS.npz')
                assert item['endpoint_sha256'] == sha(CONFIRM / target.stem / 'ENDPOINTS.json')
                truth = read(CONFIRM / target.stem / 'ENDPOINTS.json')
                assert len(truth) == 1770 and sum(e['rankable'] for e in truth)==1207
                assert {(e['kind'],e['endpoint']) for e in truth if e['status']=='positive'} == {
                    ('D','DFF_18_Q_reg'), ('D','DFF_19_Q_reg'), ('PO','g8021')}
                row.update(graph='bound_39v3', existing_model_result='N_best_A_D_only__B_separate_head')
            outputs.append(row)
    assert len({(r['source'],r['recipe'],r['keep']) for r in outputs}) == len(outputs) == 40
    assert sum(r['functional_gt'] == 'paired_D_PO' for r in outputs) == 4
    assert sum(r['functional_gt'] == 'PO_positive_only' for r in outputs) == 8

    legacy = rows(P / 'nokeep41_20261111/NOKEEP41_MANIFEST.csv')
    replacements = []
    for r in legacy:
        path = local(r['output'])
        assert path.stat().st_size == int(r['bytes']) and sha(path) == r['sha256'] and r['cec']=='PASS'
        original, candidate, proven = inspect_log(local(r['cec_log']).with_suffix('.log'))
        assert candidate == path and original.stem == r['base']
        replacements.append(dict(host=r['host'], recipe=r['recipe'], old_view=r['view'],
                                 cec_golden=original.relative_to(ROOT).as_posix(), proven=proven))
    assert len(replacements) == 41
    result = P / 'task2_nokeep_audit_20261113'
    result.mkdir(exist_ok=True)
    for name, records in [('PANEL40.csv',outputs), ('TRAIN_REPLACEMENT41.csv',replacements)]:
        with (result / name).open('x',encoding='utf-8-sig',newline='') as f:
            w = csv.DictWriter(f,fieldnames=list(records[0]))
            w.writeheader()
            w.writerows(records)
    print('panel',Counter((r['host'],r['recipe']) for r in outputs),Counter(r['functional_gt'] for r in outputs))
    print('source explicit keep',Counter(r['source_explicit_keep_count'] for r in outputs))
    print('41 replacement counts',Counter(r['host'] for r in replacements),Counter(r['recipe'] for r in replacements))


if __name__ == '__main__':
    main()
