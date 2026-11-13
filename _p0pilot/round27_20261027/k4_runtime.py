"""Round27 resumable I/O. Existing evidence is never overwritten or removed."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from contextlib import contextmanager
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
PANEL = Path(os.environ.get('SAT_K4_PANEL', str(TABLES / 'sat_k4_alltrain_round27'))).resolve()


def dependency_index_fast(module):
    """Same native dependency contract; cache the gate set outside node loops."""
    drivers = {}
    for name, c in module['cells'].items():
        dirs = c.get('port_directions', {})
        for pin, bits in c['connections'].items():
            if dirs.get(pin) == 'output' or (not dirs and pin in ('Q', 'QN', 'Y')):
                if len(bits) != 1:
                    raise ValueError('Scalar library pins required')
                bit = bits[0]
                if isinstance(bit, int):
                    if bit in drivers:
                        raise ValueError('Multiple native drivers')
                    drivers[bit] = (name, pin)
    deps = {}
    for bit, (name, pin) in drivers.items():
        cell = module['cells'][name]
        if 'DFF' not in cell['type'].upper():
            deps[bit] = sorted({b for p, bits in cell['connections'].items()
                                if p != pin for b in bits if isinstance(b, int)})
    gates = set(deps)
    pending = {b: len(set(ins) & gates) for b, ins in deps.items()}
    consumers = {}
    for b, ins in deps.items():
        for a in set(ins) & gates:
            consumers.setdefault(a, []).append(b)
    ready = deque(b for b, n in pending.items() if n == 0)
    visited = 0
    while ready:
        bit = ready.popleft()
        visited += 1
        for nxt in consumers.get(bit, []):
            pending[nxt] -= 1
            if pending[nxt] == 0:
                ready.append(nxt)
    if visited != len(deps):
        raise ValueError('Combinational cycle')
    return drivers, deps


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write_new(path, obj):
    path = Path(path)
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def fresh_dir(parent, prefix='attempt'):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    for i in range(100000):
        p = parent / f'{prefix}_{i:05d}'
        try:
            p.mkdir()
            return p
        except FileExistsError:
            continue
    raise RuntimeError('Too many attempts')


def read_plan(path):
    p = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    h = p.pop('plan_sha')
    if hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest() != h:
        raise ValueError(f'Plan hash mismatch: {path}')
    return p


def view_base_path(folder):
    folder = Path(folder)
    fixed = folder/'base_inputs_normalized.npz'
    return fixed if fixed.exists() else folder/'base_inputs.npz'


@contextmanager
def exclusive_lock(path):
    """OS lock releases on crash; the lock file stays on disk."""
    import msvcrt
    with Path(path).open('a+b') as f:
        if f.tell() == 0:
            f.write(b'0')
            f.flush()
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as e:
            raise RuntimeError(f'Another runner owns {path}') from e
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def memory_available_gib():
    import ctypes
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in ('total_phys', 'avail_phys',
             'total_page', 'avail_page', 'total_virtual', 'avail_virtual', 'extended')]
    m = Memory()
    m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise OSError('Cannot read memory status')
    return min(m.avail_phys, m.avail_page) / 2**30


def validate_complete(folder):
    """Do not equate coverage.json existence with verified completion."""
    folder = Path(folder)
    try:
        plan = read_plan(folder / 'plan.json')
        item, = plan['views']
        if sha(ROOT / item['source']) != item['source_sha']:
            raise ValueError('Source changed')
        info = json.loads((folder / 'coverage.json').read_text())
        bound_base = folder/info.get('base_file', 'base_inputs.npz')
        if info['base_sha'] != sha(bound_base):
            raise ValueError('Base digest mismatch')
        for name, digest in info['feature_sha'].items():
            if sha(folder / (name + '.npy')) != digest:
                raise ValueError('Feature digest mismatch')
        with np.load(bound_base) as z:
            ids = z['global_ids']
        real = np.load(folder / 'real.npy', mmap_mode='r')
        records = json.loads((folder / 'records.json').read_text())
        if real.shape != (len(ids), 19) or len(records) != len(ids):
            raise ValueError('Node/feature dimensions mismatch')
        if info['columns'][-1] != 'covered' or len(info['columns']) != 19:
            raise ValueError('Invalid feature column contract')
        seen, paths = set(), set()
        for r in records:
            i = r['local_node']
            if i in seen or not 0 <= i < len(ids) or int(ids[i]) != r['global_node'] or r['view'] != item['view']:
                raise ValueError('Record coordinate mismatch')
            seen.add(i)
            if 'evidence' in r:
                paths.add(r['evidence'])
            if real[i, 18] and (r['status'] != 'eligible' or r['features']['has_unknown']):
                raise ValueError('Invalid covered record')
            expected = np.zeros(19, np.float32)
            if r['status'] == 'eligible':
                if 'evidence' not in r:
                    raise ValueError('Eligible node lacks evidence')
                if not r['features']['has_unknown']:
                    expected[:18] = [r['features'][c] for c in info['columns'][:18]]
                    expected[18] = 1
            if not np.array_equal(real[i], expected):
                raise ValueError('Feature/record mismatch')
        saved_by_path = {}
        for path in paths:
            p = ROOT / path
            saved = json.loads(p.read_text())
            if saved['source_sha'] != item['source_sha']:
                raise ValueError('Evidence source mismatch')
            for key, name in [('model_sha', 'model.v'), ('script_sha', 'run.ys'), ('log_sha', 'run.log')]:
                digest = (hashlib.sha256((p.parent/name).read_text(encoding='utf-8').encode()).hexdigest()
                          if name == 'run.ys' else sha(p.parent/name))
                if saved[key] != digest:
                    raise ValueError('Evidence digest mismatch')
            if any(q['status'] not in ('proved', 'refuted') for q in saved['queries']):
                raise ValueError('Incomplete solver evidence')
            saved_by_path[path] = saved
        for r in records:
            if 'evidence' in r:
                saved = saved_by_path[r['evidence']]
                table = saved['tables'][str(r['evidence_ordinal'])]
                if any(r[k] != table[k] for k in ('table', 'features', 'inputs')):
                    raise ValueError('Record/evidence table mismatch')
        snapshots = json.loads((folder/'snapshots.json').read_text())
        for snap in snapshots:
            if snap['source_sha'] != item['source_sha'] or sha(ROOT/snap['folder']/'raw.json') != snap['raw_sha']:
                raise ValueError('Snapshot binding mismatch')
            if any(s['raw_sha'] != snap['raw_sha'] for s in saved_by_path.values()):
                raise ValueError('Query/raw snapshot mismatch')
        return True, dict(nodes=len(ids), covered=int(real[:, 18].sum()), batches=len(paths))
    except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
        return False, str(e)


def prepare_inputs(panel=PANEL):
    """Coordinator only: stream NPZ members once, mmap, then make small view bases.

    Cache paths are versioned by the complete source NPZ digest. Interrupted
    cache builds remain untouched; subsequent runs use a new build directory.
    """
    panel = Path(panel)
    plan = read_plan(panel / 'plan.json')
    source = panel / 'base_inputs.npz'
    digest = sha(source)
    cache_root = panel / 'input_cache' / digest
    cache_root.mkdir(parents=True, exist_ok=True)
    cache = None
    for p in sorted(cache_root.glob('build_*')):
        if (p / 'complete.json').exists():
            info = json.loads((p / 'complete.json').read_text())
            if all(sha(p / n) == h for n, h in info['members'].items()):
                cache = p
                break
    if cache is None:
        cache = fresh_dir(cache_root, 'build')
        members = {}
        with zipfile.ZipFile(source) as z:
            for key in ('global_ids', 'view_index', 'x', 'edge_index'):
                name = key + '.npy'
                with z.open(name) as src, (cache / name).open('xb') as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                members[name] = sha(cache / name)
        write_new(cache / 'complete.json', dict(source_sha=digest, members=members))
    arrays = {k: np.load(cache / (k + '.npy'), mmap_mode='r')
              for k in ('global_ids', 'view_index', 'x', 'edge_index')}
    gids, vi, x, ei = (arrays[k] for k in ('global_ids', 'view_index', 'x', 'edge_index'))
    if x.shape[0] != len(gids) or len(vi) != len(gids):
        raise ValueError('Invalid frozen base shapes')
    if ei.size and (ei.min() < 0 or ei.max() >= len(gids)):
        raise ValueError('Invalid edge coordinates')
    for i, item in enumerate(plan['views']):
        folder = panel / 'views' / item['view']
        ids = np.flatnonzero(vi == i)
        target = folder / 'base_inputs.npz'
        if target.exists():
            with np.load(target) as z:
                if not np.array_equal(z['global_ids'], gids[ids]):
                    raise ValueError(f'Existing per-view base mismatch: {target}')
                if not np.array_equal(z['x'], x[ids]):
                    raise ValueError(f'Existing per-view base features mismatch: {target}')
                existing_edges = z['edge_index']
            reverse = np.full(len(gids), -1, np.int64)
            reverse[ids] = np.arange(len(ids))
            keep = reverse[ei[0]] >= 0
            expected_edges = reverse[ei[:, keep]]
            if np.array_equal(existing_edges, expected_edges):
                continue
            if not np.array_equal(existing_edges.T, expected_edges):
                raise ValueError(f'Existing base is not a simple legacy edge transpose: {target}')
            fixed = folder/'base_inputs_normalized.npz'
            if fixed.exists():
                with np.load(fixed) as z:
                    if not (np.array_equal(z['global_ids'], gids[ids]) and
                            np.array_equal(z['x'], x[ids]) and
                            np.array_equal(z['edge_index'], expected_edges)):
                        raise ValueError(f'Normalized input mismatch: {fixed}')
            else:
                with fixed.open('xb') as f:
                    np.savez_compressed(f, global_ids=gids[ids], x=x[ids],
                        edge_index=expected_edges, view_index=np.zeros(len(ids), np.int64))
                write_new(folder/'base_inputs_normalized.binding.json', dict(
                    source_sha=digest, original_base_sha=sha(target), normalized_sha=sha(fixed),
                    repair='Exact edge transpose validated against frozen global graph; original retained'))
            continue
        reverse = np.full(len(gids), -1, np.int64)
        reverse[ids] = np.arange(len(ids))
        keep = reverse[ei[0]] >= 0
        if not np.all(reverse[ei[1, keep]] >= 0):
            raise ValueError('Cross-view edge')
        # Exclusive creation: even an interrupted file is retained for audit.
        attempt = fresh_dir(folder, 'base_input_attempt')
        built = attempt / 'base_inputs.npz'
        with built.open('xb') as f:
            np.savez_compressed(f, global_ids=gids[ids], x=x[ids],
                                edge_index=reverse[ei[:, keep]],
                                view_index=np.zeros(len(ids), np.int64))
        write_new(attempt / 'binding.json', dict(source_sha=digest, view=item['view'],
                                                base_sha=sha(built)))
        # Copy, never move. Canonical path is created only after complete build.
        with built.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)


def load_view_inputs(folder, panel=PANEL, names_path=None):
    """Workers only read their small base and stream selected signal names."""
    folder, panel = Path(folder), Path(panel)
    plan = read_plan(folder / 'plan.json')
    if len(plan['views']) != 1:
        raise ValueError('One view per worker required')
    base = view_base_path(folder)
    if not base.exists():
        raise RuntimeError('Missing per-view base; run coordinator preparation first')
    with np.load(base) as z:
        ids = z['global_ids']
    with np.load(panel / 'base_inputs.npz') as z:
        # global_ids/view_index are small; x and edges are NEVER loaded here.
        all_ids, all_vi = z['global_ids'], z['view_index']
    names = [x['view'] for x in read_plan(panel / 'plan.json')['views']]
    index = names.index(plan['views'][0]['view'])
    if not np.array_equal(ids, all_ids[all_vi == index]):
        raise ValueError('Per-view coordinates differ from frozen panel')
    if len(np.unique(ids)) != len(ids) or not len(ids):
        raise ValueError('Empty or duplicate coordinates')
    wanted = set(map(int, ids))
    selected = {}
    names_path = names_path or ROOT / 'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt'
    last_id = int(ids.max())
    with Path(names_path).open(encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i in wanted:
                selected[i] = line.rstrip('\r\n')
            if i >= last_id:
                break
    if len(selected) != len(ids):
        raise ValueError('Missing graph node names')
    view = plan['views'][0]['view']
    return ids, {int(g): view for g in ids}, {int(g): i for i, g in enumerate(ids)}, selected


def checked_yosys(script, log, timeout=600):
    """Persist raw output and return code even on timeout/WSL failure."""
    log = Path(log)
    ys = log.with_suffix('.ys')
    with ys.open('x', encoding='utf-8', newline='\n') as f:
        f.write(script)
    wsl = lambda p: '/mnt/' + str(Path(p).resolve()).replace('\\', '/')[0].lower() + str(Path(p).resolve()).replace('\\', '/')[2:]
    start = time.perf_counter()
    cmd = ['wsl', '-e', 'bash', '-lc',
           f'cd "{wsl(ROOT)}" && exec timeout --signal=TERM --kill-after=10s {timeout}s yosys -s "{wsl(ys)}"']
    timed_out = False
    # Direct file streaming prevents huge capture buffers and preserves partial logs.
    with log.open('xb') as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        try:
            rc = p.wait(timeout=timeout+15)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], capture_output=True)
            rc = p.wait()
    text = log.read_text(encoding='utf-8', errors='replace')
    write_new(log.with_suffix('.execution.json'), dict(rc=rc, timeout=timed_out,
              seconds=time.perf_counter()-start, command=cmd, log_sha=sha(log)))
    if rc or timed_out or 'ERROR:' in text:
        raise RuntimeError(f'Yosys/WSL failed: rc={rc}, timeout={timed_out}; retained {log}')
    return text


def complete_statuses(log, count, parser):
    markers = [int(x) for x in re.findall(r'^\s*SATQ(\d{6})\s*$', log, re.M)]
    if markers != list(range(count)):
        raise ValueError('Missing/duplicate/out-of-order query markers')
    statuses = parser(log)
    if len(statuses) != count or any(s not in ('proved', 'refuted') for s in statuses):
        raise ValueError('Incomplete SAT batch; retain old evidence and use new attempt')
    if 'ERROR:' in log:
        raise ValueError('Failed solver output')
    return statuses


def find_bound_batch(batch, code, script, source_sha, raw_sha, count, parser):
    """Recover complete legacy logs without solving; never overwrite a failure.

    Script identity includes absolute witness/model paths. Old canonical batches
    use the original script; retry attempts have only those directory paths changed.
    """
    batch = Path(batch)
    candidates = [batch] + sorted(batch.glob('attempt_*'))
    for folder in candidates:
        actual_script = script.replace(str(batch).replace('\\', '/'), str(folder).replace('\\', '/'))
        # The scripts contain WSL paths rather than Windows paths.
        old = '/mnt/' + str(batch).replace('\\', '/')[0].lower() + str(batch).replace('\\', '/')[2:]
        new = '/mnt/' + str(folder).replace('\\', '/')[0].lower() + str(folder).replace('\\', '/')[2:]
        actual_script = actual_script.replace(old, new)
        result, model, ys, log = (folder / n for n in ('results.json', 'model.v', 'run.ys', 'run.log'))
        try:
            if model.read_bytes() != code.encode() or ys.read_text(encoding='utf-8') != actual_script:
                continue
            statuses = complete_statuses(log.read_text(encoding='utf-8', errors='replace'), count, parser)
            if result.exists():
                saved = json.loads(result.read_text())
                if not (saved['model_sha'] == sha(model) and saved['script_sha'] == hashlib.sha256(actual_script.encode()).hexdigest()
                        and saved['log_sha'] == sha(log) and saved['source_sha'] == source_sha
                        and saved['raw_sha'] == raw_sha):
                    continue
                if [q['status'] for q in saved['queries']] != statuses:
                    continue
                return folder, saved, statuses, actual_script
            execution = log.with_suffix('.execution.json')
            if execution.exists():
                e = json.loads(execution.read_text())
                if e['rc'] or e['timeout'] or e['log_sha'] != sha(log):
                    continue
            return folder, None, statuses, actual_script
        except (OSError, ValueError, KeyError, UnicodeError):
            continue
    return None
