"""Netlist indexing and cut construction for round 3 (structure only)."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

SEQ_PINS = {"CK", "CLK", "RN", "RST", "RESET", "SN", "SET", "SE", "SI"}


def hkey(s: str) -> str:
    return hashlib.sha256(("r3|" + s).encode()).hexdigest()


def load_module(js: Path, top: str) -> dict:
    return json.loads(js.read_text(encoding="utf-8"))["modules"][top]


def build_index(mod: dict) -> dict:
    netbits = {nm: tuple(b for b in info.get("bits", []) if isinstance(b, int))
               for nm, info in mod.get("netnames", {}).items()}
    for nm, p in mod.get("ports", {}).items():
        netbits[nm] = tuple(b for b in p.get("bits", []) if isinstance(b, int))
    bit_driver = defaultdict(set)
    bit_consumer = defaultdict(set)
    cell_inputs = defaultdict(list)
    cell_outs = {}
    dff_cells = {}
    for cn, cell in mod.get("cells", {}).items():
        typ = str(cell.get("type", "")).upper()
        con = cell.get("connections", {})
        dirs = cell.get("port_directions", {})
        outs = []
        for pin, bits in con.items():
            is_out = dirs.get(pin) == "output" or (not dirs and pin in ("Y", "Q", "QN"))
            if is_out:
                outs += [b for b in bits if isinstance(b, int)]
                for b in bits:
                    if isinstance(b, int):
                        bit_driver[b].add(cn)
            elif pin.upper() not in SEQ_PINS:
                cell_inputs[cn].append((pin, bits))
                for b in bits:
                    if isinstance(b, int):
                        bit_consumer[b].add(cn)
        cell_outs[cn] = outs
        if "DFF" in typ or "LATCH" in typ:
            dff_cells[cn] = con
    return dict(netbits=netbits, bit_driver=bit_driver, bit_consumer=bit_consumer,
                cell_inputs=cell_inputs, cell_outs=cell_outs, dff_cells=dff_cells,
                cells=mod.get("cells", {}), ports=mod.get("ports", {}))


def net_of_bit(idx: dict, bit: int) -> str | None:
    for nm, bits in idx["netbits"].items():
        if len(bits) == 1 and bits[0] == bit:
            return nm
    return None


def out_ports(idx: dict) -> list[str]:
    return sorted(n for n, p in idx["ports"].items() if p.get("direction") == "output")


def reach(idx: dict, bit: int, cap: int = 20000) -> tuple[int, int]:
    po_bits = {b for p in idx["ports"].values() if p.get("direction") == "output"
               for b in p.get("bits", []) if isinstance(b, int)}
    frontier, visited = [bit], {bit}
    po, dff = set(), set()
    while frontier and len(visited) < cap:
        nxt = []
        for b in frontier:
            if b in po_bits:
                po.add(b)
            for cn in idx["bit_consumer"].get(b, ()):
                if cn in idx["dff_cells"]:
                    dff.add((cn, b))
                    continue
                for ob in idx["cell_outs"].get(cn, ()):
                    if ob not in visited:
                        visited.add(ob)
                        nxt.append(ob)
        frontier = nxt
    return len(po), len(dff)


def dff_d_targets(idx: dict) -> list[dict]:
    out = []
    for cn, con in idx["dff_cells"].items():
        dbits = [b for b in con.get("D", []) if isinstance(b, int)]
        if len(dbits) != 1:
            continue
        net = net_of_bit(idx, dbits[0])
        if not net:
            continue
        drv = idx["bit_driver"].get(dbits[0], set())
        if len(drv) != 1:
            continue
        dcn = next(iter(drv))
        if "DFF" in str(idx["cells"][dcn].get("type", "")).upper():
            continue
        out.append(dict(kind="dff_next", cell=cn, target=net, driver=dcn, bit=dbits[0]))
    return out


def cut_for(idx: dict, net: str, depth: int = 2, max_cut: int = 3) -> dict:
    """Collect the fan-in boundary, then optionally select a subset.

    Returns leaf_total (all named single-bit leaves found), selected, truncated,
    depth_used, leaves, reason. A truncated selection is never a complete boundary.
    """
    bits = idx["netbits"].get(net, ())
    if len(bits) != 1:
        return dict(leaves=[], leaf_total=0, selected=0, truncated=False,
                    depth_used=0, reason="target_not_single_bit")
    start = bits[0]
    seen = {start}
    frontier = [(start, 0)]
    leaves = []
    hit_cap = False
    while frontier:
        b, d = frontier.pop()
        drv = idx["bit_driver"].get(b, set())
        is_dff = bool(drv) and all(c in idx["dff_cells"] for c in drv)
        if d >= depth or not drv or len(drv) != 1 or is_dff:
            leaves.append((b, d))
            continue
        cn = next(iter(drv))
        for _pin, ibits in idx["cell_inputs"].get(cn, []):
            for nb in ibits:
                if not isinstance(nb, int) or nb == b or nb in seen:
                    continue
                if len(seen) >= 64:
                    hit_cap = True
                    continue
                seen.add(nb)
                frontier.append((nb, d + 1))
    named = []
    for b, d in leaves:
        nm = net_of_bit(idx, b)
        if not nm or nm in ("0", "1", "x", "z") or nm.startswith("$"):
            continue
        named.append((d, nm))
    named.sort(key=lambda x: (-x[0], hkey(x[1])))
    chosen = []
    for d, nm in named:
        if nm not in chosen:
            chosen.append(nm)
        if len(chosen) >= max_cut:
            break
    truncated = hit_cap or len(named) > max_cut
    if len(chosen) < 2:
        reason = "cut_too_small"
    elif max(d for d, _ in named[: len(chosen)]) < 2:
        reason = "cut_not_nonlocal"
    else:
        reason = ""
    if reason:
        return dict(leaves=chosen, leaf_total=len(named), selected=len(chosen),
                    truncated=truncated, depth_used=depth, reason=reason)
    return dict(leaves=chosen, leaf_total=len(named), selected=len(chosen),
                truncated=truncated, depth_used=depth, reason="")
