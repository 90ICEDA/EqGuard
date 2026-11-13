"""netmap.py —— **SAT 网名 → `.pt` 节点 id 的结构化映射**（2026-10-23 新增 ✓）。

为什么需要它 ✗（旧 `resolve()` 只有 4–26% 命中率）：
  · `.pt` 的节点 = **单元（cell）**，名字是 `dump_node_names.py` 用 parser2 重放 `.v` 反推的
    （实测 `struct JSON cells == pt nodes`，1:1 ✓），例如 `DFF_1016_Q_reg`；
  · SAT 表里存的是 **网名（net）**，例如 `n8104` / `U7157.IN5` —— 两者**不同构** ✗；
  · 且综合后大量 `assign a = b;` **别名**（单视图实测 2.4 万条 ✗）→ SAT 常证的正是别名两端 ✗。

本模块给 `resolve` 补三层 ✓（严格按优先级，前一层命中即返回）：
  1. **直接查名**（旧行为 ✓，保持向后兼容）           —— `exact` / `base` 查表
  2. **assign 别名追踪**（≤ `max_alias` 层 ✓）→ 再查名   —— `assign a = b` ⇒ a 的证据贴到 b 的节点
  3. **网 → 驱动单元**（只认**输出脚** ✓）→ 查单元名     —— `Q/QN/Y/Z/...`（优先用 yosys JSON 的
     `port_directions` 判方向 ✓，缺失时退回保守输出脚集合 ⚠️）

实测（每格 400 个 proved 网名，见 `phase2/ys/check_netmap.py` ✓）：
  s38417 ys_id 8% → **93%**｜ys_abc 7% → **99%**｜ys_opt 8% → **91%**
  rs232 ys_id 26% → 92%｜s15850 ys_id 16% → 89%｜s38584 ys_id 12% → 96%
  → 旧版"覆盖率 0.29%"里 **约 90% 是映射层丢的**，不是 SAT 没证出来 ✓。

⚠️ 口径：
  · 只把**输出脚**所驱动网的名字算作该单元的证据 ✓（输入脚不算 ✗，否则会贴错到下游门 ✗）；
  · 追不到（≈7%：模块 input 端口 / 常量 / 未命名单元）记 `miss` ✓，**不静默当 0** ✗；
  · 全程只读 `.v` / `.json` ✓，不改任何网表 ✓。
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

DEC = re.compile(r"^g_{1,2}(.+)_\d+$")

# `.v` 行级解析 ✓（yosys 输出一行一条语句 ✓）
INST_RE = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s+(\\?[^\s(]+)\s*\((.*)\)\s*;\s*$")
PORT_RE = re.compile(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)")
ASSIGN_RE = re.compile(r"assign\s+([^=;]+?)\s*=\s*([^;]+);")
NETAPP = re.compile(r"^[\\\w\.\$\[\]]+$")          # 只接受单网（拒绝拼接/常量表达式 ✓）
KW = {"module", "wire", "input", "output", "inout", "assign", "reg", "parameter",
      "localparam", "endmodule", "always", "initial", "supply0", "supply1", "tri"}

# JSON 缺失时的保守输出脚集合 ⚠️（已验证：配合 assign 追踪仍可达 77–99% ✓）
OUT_PINS_FALLBACK = {"Q", "QN", "Y", "Z", "X", "CO", "S", "O", "ON"}


def base_name(n: str) -> str:
    """`g__TrojanAHJ.B_86` → `TrojanAHJ.B`；`g_U0_p1_122` → `U0_p1`；否则原样 ✓。"""
    m = DEC.match(n or "")
    return m.group(1) if m else (n or "")


def _clean(net: str) -> str:
    return str(net).strip().lstrip("\\")



class _ViewCtx:
    """单个视图的映射上下文 ✓（懒加载 ✓，只建一次 ✓）。"""

    __slots__ = ("view", "v_path", "alias", "net2cell", "net2all", "net_bits", "bit2cell",
                 "bit2all", "type2out", "n_cells", "has_json")

    def __init__(self, view: str, v_path: Path | None, json_path: Path | None):
        self.view = view
        self.v_path = v_path
        self.alias: dict[str, str] = {}
        self.net2cell: dict[str, set[str]] = defaultdict(set)     # .v 解析（按输出脚 ✓）
        self.net2all: dict[str, set[str]] = defaultdict(set)      # .v 解析（任意脚 ✓ incident ⚠️）
        self.net_bits: dict[str, list[int]] = {}                  # JSON netnames → bits
        self.bit2cell: dict[int, list[str]] = {}                  # JSON 输出 bit → cell
        self.bit2all: dict[int, list[str]] = {}                   # JSON 任意 bit → cell
        self.type2out: dict[str, set[str]] = {}                    # JSON cell type → 输出脚 ✓
        self.n_cells = 0
        self.has_json = False
        if json_path is not None and json_path.exists():
            self._load_json(json_path)
        if v_path is not None and v_path.exists():
            self._load_v(v_path)

    # ---------- yosys JSON：精确判输出脚 + bit 级驱动 ✓ ----------
    def _load_json(self, p: Path) -> None:
        try:
            j = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        mods = j.get("modules") or {}
        if not mods:
            return
        mod = next(iter(mods.values()))
        t2o: dict[str, set[str]] = defaultdict(set)
        for cname, c in (mod.get("cells") or {}).items():
            direc = c.get("port_directions") or {}
            conns = c.get("connections") or {}
            self.n_cells += 1
            outs = {pin for pin, d in direc.items() if d == "output"}
            if outs:
                t2o[str(c.get("type", ""))] |= outs
            for pin, d in direc.items():
                if d != "output":
                    continue
                for b in conns.get(pin, []) or []:
                    if isinstance(b, int):
                        self.bit2cell.setdefault(b, []).append(cname)
            for pin in conns:
                for b in conns.get(pin, []) or []:
                    if isinstance(b, int) and cname not in self.bit2all.setdefault(b, []):
                        self.bit2all[b].append(cname)
        self.type2out = dict(t2o)
        for nm, inf in (mod.get("netnames") or {}).items():
            bits = [b for b in (inf.get("bits") or []) if isinstance(b, int)]
            if bits:
                self.net_bits[_clean(nm)] = bits
        self.has_json = True

    # ---------- .v：单元实例 + assign 别名 ✓ ----------
    def _load_v(self, p: Path) -> None:
        text = p.read_text(encoding="utf-8", errors="replace")
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith("assign"):
                for a, b in ASSIGN_RE.findall(s):
                    a, b = _clean(a), _clean(b)
                    if NETAPP.match(a) and NETAPP.match(b) and a != b:
                        self.alias[a] = b
                continue
            m = INST_RE.match(s)
            if not m:
                continue
            typ, inst, ports = m.groups()
            if typ in KW:
                continue
            inst = _clean(inst)
            outs = self.type2out.get(typ) or OUT_PINS_FALLBACK   # 有 JSON 用精确 ✓，否则保守 ⚠️
            if not self.has_json:
                self.n_cells += 1
            outsU = {o.upper() for o in outs}
            for pin, net in PORT_RE.findall(ports):
                net = _clean(net)
                if not net or not NETAPP.match(net):
                    continue
                self.net2all[net].add(inst)                 # 任意脚 ✓（incident 用 ⚠️）
                if pin.upper() in outsU:
                    self.net2cell[net].add(inst)

    # ---------- 查表工具 ✓ ----------
    def chase(self, net: str, max_depth: int = 8) -> str:
        seen = set()
        cur = net
        while cur in self.alias and cur not in seen and len(seen) < max_depth:
            seen.add(cur)
            cur = self.alias[cur]
        return cur

    def drivers(self, net: str) -> list[str]:
        """该网的驱动单元名 ✓（先 bit 级精确 ✓，再 .v 正则 ⚠️）。去重保序 ✓。"""
        out: list[str] = []
        for key in (net, net.split("[")[0]):
            for b in self.net_bits.get(key, ()):
                for c in self.bit2cell.get(b, ()):
                    if c not in out:
                        out.append(c)
            for c in sorted(self.net2cell.get(key, ())):
                if c not in out:
                    out.append(c)
        return out

    def incident(self, net: str) -> list[str]:
        """与该网**任意脚**相连的单元名 ✓（driver + sinks ⚠️，口径 = incident ✓）。"""
        out: list[str] = []
        for key in (net, net.split("[")[0]):
            for b in self.net_bits.get(key, ()):
                for c in self.bit2all.get(b, ()):
                    if c not in out:
                        out.append(c)
            for c in sorted(self.net2all.get(key, ())):
                if c not in out:
                    out.append(c)
        return out


class NetMapper:
    """按视图缓存的 网名 → `.pt` 节点 id 映射器 ✓。

    exact / basem：`build_maps()` 的产物（逐视图 名字→ids ✓）；
    views_dir    ：fold 的 `trans/` 目录（`<view>.v` ✓）；
    struct_dirs  ：yosys JSON 缓存目录（`<view>.json` ✓，可多个 ✓）。
    """

    def __init__(self, exact: dict, basem: dict, views_dir: Path | None,
                 struct_dirs: list[Path] | None = None, use_json: bool = True,
                 max_alias: int = 8, verbose: bool = False,
                 include_sinks: bool = False):
        self.exact = exact
        self.basem = basem
        self.views_dir = Path(views_dir) if views_dir else None
        self.struct_dirs = [Path(d) for d in (struct_dirs or [])]
        self.use_json = use_json
        self.max_alias = max_alias
        self.verbose = verbose
        self.include_sinks = include_sinks      # ⚠️ True → 证据贴到 driver + sinks（incident 口径）
        self.stat: dict[str, int] = defaultdict(int)
        self.stat_by_view: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._ctx: dict[str, _ViewCtx] = {}
        self._cache: dict[tuple[str, str], list[int]] = {}

    # ---------- 视图上下文 ✓ ----------
    def _ctx_of(self, view: str) -> _ViewCtx:
        c = self._ctx.get(view)
        if c is not None:
            return c
        vp = (self.views_dir / f"{view}.v") if self.views_dir else None
        jp = None
        if self.use_json:
            for d in self.struct_dirs:
                cand = d / f"{view}.json"
                if cand.exists():
                    jp = cand
                    break
        c = _ViewCtx(view, vp, jp)
        self._ctx[view] = c
        if self.verbose:
            print(f"[netmap] {view}: alias={len(c.alias)} net2cell={len(c.net2cell)} "
                  f"netnames={len(c.net_bits)} cells={c.n_cells} json={c.has_json}")
        return c

    # ---------- 名字查表 ✓ ----------
    def _lookup(self, view: str, nm: str) -> list[int]:
        ex = self.exact.get(view) or {}
        bs = self.basem.get(view) or {}
        ids = ex.get(nm)
        if ids:
            return ids
        ids = bs.get(nm)
        if ids:
            return ids
        head = nm.split("[")[0]
        if head != nm:
            ids = ex.get(head) or bs.get(head)
            if ids:
                return ids
        return []

    # ---------- 对外接口 ✓ ----------
    def ids(self, view: str, net: str) -> list[int]:
        """SAT 网名 → `.pt` 节点 id 列表 ✓（空 = 追不到 ✓，调用方记 miss ✓）。"""
        net = _clean(net)
        if not net:
            return []
        key = (view, net)
        got = self._cache.get(key)
        if got is not None:
            return got
        out, how = self._resolve(view, net)
        if self.include_sinks:
            c = self._ctx_of(view)
            a = c.chase(net, self.max_alias)
            extra: list[int] = []
            for src in ((net,) if a == net else (net, a)):
                for cell in c.incident(src):
                    for i in self._lookup(view, cell):
                        if i not in extra:
                            extra.append(i)
            if extra:
                merged = list(dict.fromkeys(out + extra))
                if not out:
                    how = "incident_only"
                self._cache[key] = merged
                self.stat[how] += 1
                self.stat_by_view[view][how] += 1
                return merged
        self._cache[key] = out
        self.stat[how] += 1
        self.stat_by_view[view][how] += 1
        return out

    def _resolve(self, view: str, net: str) -> tuple[list[int], str]:
        # 1) 直接查名 ✓（旧行为）
        ids = self._lookup(view, net)
        if ids:
            return ids, "direct"
        c = self._ctx_of(view)
        # 2) assign 别名追踪 → 查名 ✓
        a = c.chase(net, self.max_alias)
        if a != net:
            ids = self._lookup(view, a)
            if ids:
                return ids, "alias_name"
        # 3) 网 → 驱动单元 → 查单元名 ✓
        for src in ((net,) if a == net else (net, a)):
            for cell in c.drivers(src):
                ids = self._lookup(view, cell)
                if ids:
                    return ids, "driver_cell"
        # 4) 追不到 ✓（≈7%）
        return [], "miss"

    # ---------- 统计 ✓ ----------
    def summary(self) -> dict:
        tot = sum(self.stat.values()) or 1
        return {
            "queries": int(tot),
            **{k: int(v) for k, v in sorted(self.stat.items())},
            "hit_rate": round(1.0 - self.stat.get("miss", 0) / tot, 6),
            "note": ("direct=旧口径直查 ✓ / alias_name=assign 追踪后直查 ✓ / "
                     "driver_cell=网→驱动单元 ✓ / miss=追不到（input 端口·常量·未命名单元）⚠️"),
        }


def default_struct_dirs(base: Path) -> list[Path]:
    """N4 目录下的两个 yosys JSON 缓存 ✓（`struct/` 与 `struct_node/` ✓）。"""
    out: list[Path] = []
    for name in ("struct", "struct_node"):
        d = Path(base) / "logs" / name
        if d.exists():
            out.append(d)
    return out
