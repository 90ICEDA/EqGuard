"""Offline endpoint-cone precheck on an independent small netlist.

Definitions:
  D cone: endpoint = DFF.D net; include the combinational driver of D; walk fanin;
          stop at PI nets and at DFF outputs; exclude the register body itself.
  PO cone: endpoint = PO net; include the actual driver gate (even if it is the only member);
          walk fanin; stop at PI/DFF outputs; exclude registers.
Single-point, direct-PI, direct-Q and empty combinational cones are classified, not dropped.
Exports members, reloads the CSV, and requires exact set equality.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/endpoint_cone_precheck_20261109'
sys.path.insert(0, str(OUT))
import Signed_common as S  # noqa: E402

CONST = {'#0', '#1', '0', '1', "1'b0", "1'b1"}


def main():
    src = S.F / 'orig/rs232t1000__injalpha_d1_s42.v'
    g = S.raw_network(src, S.lib_pins)
    pins = g['pins']
    find = g['find']
    driven = set(g['drivers'])
    all_nets = {n for _, conns in pins.values() for _, n in conns}
    pi_nets = {n for n in all_nets if find(n) not in g['drivers'] and n not in CONST}

    def is_dff(cell):
        return 'DFF' in pins[cell][0].upper()

    def inputs_of(cell):
        typ, conns = pins[cell]
        return [n for p, n in conns if p in S.lib_pins[typ]['inputs']]

    def outputs_of(cell):
        typ, conns = pins[cell]
        return {p: n for p, n in conns if p in S.lib_pins[typ]['outputs']}

    def cone_from(start_net, include_driver=True):
        """Return (members ordered by depth, unknown nets, stop kinds)."""
        members, unknown = [], []
        seen_cells, seen_nets = set(), {find(start_net)}
        stop = collections.Counter()
        frontier = [(start_net, 0)]
        first = True
        while frontier:
            net, depth = frontier.pop(0)
            owners = g['drivers'].get(find(net), set())
            if not owners:
                stop['pi' if net in pi_nets else 'dangling'] += 1
                if net not in pi_nets and net not in CONST:
                    unknown.append(net)
                continue
            for cell in owners:
                if is_dff(cell):
                    stop['dff_q'] += 1
                    continue
                if cell in seen_cells:
                    continue
                seen_cells.add(cell)
                members.append(dict(cell=cell, gate=pins[cell][0], depth=depth,
                                    role='driver' if first and include_driver else 'comb'))
                for inp in inputs_of(cell):
                    if find(inp) in seen_nets or inp in CONST:
                        continue
                    seen_nets.add(find(inp))
                    frontier.append((inp, depth + 1))
            first = False
        return members, unknown, stop

    cones = []
    for cell in pins:
        if not is_dff(cell):
            continue
        typ, conns = pins[cell]
        d_net = dict(conns).get('D')
        if d_net is None:
            continue
        members, unknown, stop = cone_from(d_net)
        cones.append(dict(cone_id=f'D:{cell}', kind='D', endpoint=d_net, driver_cell=(members[0]['cell'] if members else ''),
                          members=members, unknown=unknown, stop=stop))
    for i, po_net in enumerate(g['po']):
        members, unknown, stop = cone_from(po_net)
        cones.append(dict(cone_id=f'PO:{po_net}', kind='PO', endpoint=po_net,
                          driver_cell=(members[0]['cell'] if members else ''),
                          members=members, unknown=unknown, stop=stop))

    rows = []
    for c in cones:
        for m in c['members']:
            rows.append(dict(cone_id=c['cone_id'], kind=c['kind'], endpoint=c['endpoint'],
                             driver_cell=c['driver_cell'], member_cell=m['cell'], member_gate=m['gate'],
                             depth=m['depth'], role=m['role']))
    S.table(OUT / 'CONE_MEMBERS.csv', rows)
    summary = []
    for c in cones:
        size = len(c['members'])
        drivers = {c['driver_cell']} if c['driver_cell'] else set()
        direct_pi = bool(size == 0 and c['stop'].get('pi'))
        direct_q = bool(size == 0 and c['stop'].get('dff_q'))
        summary.append(dict(cone_id=c['cone_id'], kind=c['kind'], endpoint=c['endpoint'],
                            driver_cell=c['driver_cell'], members=size,
                            singleton=int(size == 1), direct_pi=int(direct_pi), direct_q=int(direct_q),
                            empty_comb=int(size == 0), dangling_nets=len(c['unknown'])))
    S.table(OUT / 'CONE_SUMMARY.csv', summary)

    # reload and compare
    loaded = collections.defaultdict(set)
    for r in S.rows(OUT / 'CONE_MEMBERS.csv'):
        loaded[r['cone_id']].add(r['member_cell'])
    ok = True
    for c in cones:
        if loaded[c['cone_id']] != {m['cell'] for m in c['members']}:
            ok = False
    # overlap between cones of the same kind
    by_kind = collections.defaultdict(list)
    for c in cones:
        by_kind[c['kind']].append((c['cone_id'], {m['cell'] for m in c['members']}))
    overlaps = {}
    for kind, lst in by_kind.items():
        pairs = 0
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                if lst[i][1] & lst[j][1]:
                    pairs += 1
        overlaps[kind] = dict(cones=len(lst), overlapping_pairs=pairs,
                              pairs_total=len(lst) * (len(lst) - 1) // 2)
    stats = dict(source=str(src.relative_to(ROOT)), cones=len(cones),
                 d_cones=sum(c['kind'] == 'D' for c in cones), po_cones=sum(c['kind'] == 'PO' for c in cones),
                 members=len(rows), singleton=sum(r['singleton'] for r in summary),
                 direct_pi=sum(r['direct_pi'] for r in summary), direct_q=sum(r['direct_q'] for r in summary),
                 empty_comb=sum(r['empty_comb'] for r in summary),
                 dangling=sum(r['dangling_nets'] for r in summary), overlaps=overlaps)
    S.write_json(OUT / 'PRECHECK.json', dict(passed=ok, stats=stats,
                                             note='export->reload member sets must match exactly; no model calls'))
    print(json.dumps(dict(passed=ok, stats=stats), ensure_ascii=False))


if __name__ == '__main__':
    main()
