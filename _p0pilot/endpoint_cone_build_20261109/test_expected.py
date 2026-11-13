"""Independent expected-member tests for cone_builder (hand-written expectations, not re-exported by the builder)."""
import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/endpoint_cone_build_20261109'
sys.path.insert(0, str(OUT))
import Signed_common as S
import cone_builder as B

TESTS = {
    'true_pi': ("""
module t ( a, o );
  input a;
  output o;
  DFFX2 d(.D(a), .Q(q));
  assign o = a;
endmodule
""", dict(d_cones={'d': dict(flag='direct_pi', members=0)}, po={'o': dict(flag='direct_pi', members=0)})),
    'po_unique_driver': ("""
module t ( a, o );
  input a;
  output o;
  INVX0 u(.IN(a), .QN(o));
endmodule
""", dict(po={'o': dict(members=1, cells=['u'])})),
    'direct_q': ("""
module t ( a, o );
  input a;
  output o;
  DFFX2 d1(.D(a), .Q(q));
  DFFX2 d2(.D(q), .Q(r));
  assign o = q;
endmodule
""", dict(d_cones={'d2': dict(members=0, dff_q=True)})),
    'alias_vector': ("""
module t ( a, o );
  input [3:0] a;
  output o;
  wire w;
  assign w = a[1];
  DFFX2 d(.D(w), .Q(q));
  assign o = w;
endmodule
""", dict(d_cones={'d': dict(flag='direct_pi', members=0)})),
    'undeclared_internal': ("""
module t ( a, o );
  input a;
  output o;
  wire w;
  AND2X2 g(.IN1(a), .IN2(w), .Q(y));
  DFFX2 d(.D(y), .Q(q));
  assign o = y;
endmodule
""", dict(d_cones={'d': dict(cells=['g'], unknown=['w'])})),
    'unknown_mixed': ("""
module t ( a, o );
  input a;
  output o;
  wire w;
  AND2X2 g1(.IN1(a), .IN2(w), .Q(y));
  AND2X2 g2(.IN1(y), .IN2(a), .Q(z));
  DFFX2 d(.D(z), .Q(q));
  assign o = z;
endmodule
""", dict(d_cones={'d': dict(cells=['g2', 'g1'], unknown=['w'])})),
    'po_no_driver': ("""
module t ( a, o, p );
  input a;
  output o, p;
  assign o = a;
endmodule
""", dict(po={'p': dict(flag='dangling', members=0, unknown=True)})),
    'constant': ("""
module t ( a, o );
  input a;
  output o;
  DFFX2 d(.D(1'b0), .Q(q));
  assign o = q;
endmodule
""", dict(d_cones={'d': dict(flag='const', members=0)})),
    'xz': ("""
module t ( a, o );
  input a;
  output o;
  DFFX2 d(.D(1'bx), .Q(q));
  assign o = q;
endmodule
""", dict(d_cones={'d': dict(flag='xz', members=0)})),
    'wrong_declaration': ("""
module t ( o );
  output o;
  wire a;
  DFFX2 d(.D(a), .Q(q));
  assign o = a;
endmodule
""", dict(d_cones={'d': dict(flag='dangling', members=0, unknown=True)})),
}


def main():
    tdir = OUT / 'tests'
    tdir.mkdir(exist_ok=True)
    rows = []
    for name, (text, exp) in TESTS.items():
        p = tdir / f'{name}.v'
        p.write_text(text, encoding='utf-8')
        b = B.build(p)
        by = {c['cone_id']: c for c in b['cones']}
        ok, detail = True, []
        for cellkey, want in exp.get('d_cones', {}).items():
            c = by.get(f'D:{cellkey}')
            if c is None:
                ok = False; detail.append(f'missing D:{cellkey}'); continue
            cells = {m['cell'] for m in c['members']}
            if 'flag' in want and c.get('flag') != want['flag']:
                ok = False; detail.append(f'{cellkey} flag {c.get("flag")} != {want["flag"]}')
            if 'members' in want and len(cells) != want['members']:
                ok = False; detail.append(f'{cellkey} members {len(cells)} != {want["members"]}')
            if 'cells' in want and cells != set(want['cells']):
                ok = False; detail.append(f'{cellkey} cells {sorted(cells)} != {want["cells"]}')
            if 'unknown' in want:
                if want['unknown'] is True:
                    if not c['unknown']:
                        ok = False; detail.append(f'{cellkey} expected unknown')
                elif set(c['unknown']) != set(want['unknown']):
                    ok = False; detail.append(f'{cellkey} unknown {c["unknown"]} != {want["unknown"]}')
            if want.get('dff_q') and not c['boundary'].get('dff_q'):
                ok = False; detail.append(f'{cellkey} missing dff_q boundary')
        for net, want in exp.get('po', {}).items():
            c = by.get(f'PO:{net}')
            if c is None:
                ok = False; detail.append(f'missing PO:{net}'); continue
            cells = {m['cell'] for m in c['members']}
            if 'flag' in want and c.get('flag') != want['flag']:
                ok = False; detail.append(f'PO {net} flag {c.get("flag")} != {want["flag"]}')
            if 'members' in want and len(cells) != want['members']:
                ok = False; detail.append(f'PO {net} members {len(cells)} != {want["members"]}')
            if 'cells' in want and cells != set(want['cells']):
                ok = False; detail.append(f'PO {net} cells {sorted(cells)} != {want["cells"]}')
            if want.get('unknown') and not c['unknown']:
                ok = False; detail.append(f'PO {net} expected unknown')
        rows.append(dict(test=name, passed=int(ok), detail='; '.join(detail)))
    S.table(OUT / 'TEST_RESULTS.csv', rows)
    S.write_json(OUT / 'TEST_RESULTS.json', dict(passed=all(r['passed'] for r in rows), rows=rows))
    print(json.dumps(dict(passed=all(r['passed'] for r in rows), rows=rows), ensure_ascii=False))


if __name__ == '__main__':
    main()
