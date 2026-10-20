"""Render a parsed schema as a single self-contained HTML page (inline CSS + SVG, no JS).

Tables are absolutely positioned boxes with fixed header/row heights, so we
know exactly where every column sits and can draw the foreign-key edges as an
SVG layer underneath without measuring anything in a browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .parse import Class, ForeignKey, Schema

TABLE_W = 260
HEADER_H = 44
ROW_H = 24
COL_GAP = 140  # horizontal room between layers for edges + labels
ROW_GAP = 40
PAD = 48
LOOP = 36  # how far a same-side edge bulges out


@dataclass
class Box:
    x: float
    y: float
    h: float

    @property
    def right(self) -> float:
        return self.x + TABLE_W


@dataclass
class Layout:
    boxes: dict[str, Box]
    # Per foreign key (by index): the y of the lane it uses through each
    # intermediate column, so long edges pass between tables, not under them.
    lanes: dict[int, list[float]]


def column_x(col: int) -> float:
    return PAD + col * (TABLE_W + COL_GAP)


def table_height(c: Class) -> float:
    return HEADER_H + max(1, len(c.slots)) * ROW_H


def _depths(schema: Schema) -> dict[str, int]:
    """A table's depth is 1 + the deepest table it references (ignoring cycles)."""
    targets: dict[str, set[str]] = {c.name: set() for c in schema.classes}
    for fk in schema.foreign_keys:
        if fk.to_class != fk.from_class:
            targets[fk.from_class].add(fk.to_class)

    depth: dict[str, int] = {}

    def visit(name: str, stack: frozenset[str]) -> int:
        if name not in depth:
            deeper = [visit(t, stack | {name}) for t in targets[name] if t not in stack]
            depth[name] = 1 + max(deeper) if deeper else 0
        return depth[name]

    for c in schema.classes:
        visit(c.name, frozenset())
    return depth


def layered_layout(schema: Schema) -> Layout:
    """Place tables in columns by foreign-key depth (a simple Sugiyama layout).

    Referencing tables sit to the left of what they point at, so edges flow
    left-to-right. Edges that skip columns reserve a lane in every column they
    cross, and a few barycenter sweeps order each column to reduce crossings.
    """
    depth = _depths(schema)
    max_depth = max(depth.values(), default=0)
    col_of = {name: max_depth - d for name, d in depth.items()}

    # Items are ("t", class name) for tables and ("l", fk index) for lanes.
    Item = tuple[str, str | int]
    columns: list[list[Item]] = [[] for _ in range(max_depth + 1)]
    for c in schema.classes:
        columns[col_of[c.name]].append(("t", c.name))

    neighbours: dict[Item, set[Item]] = {}
    for i, fk in enumerate(schema.foreign_keys):
        a, b = col_of[fk.from_class], col_of[fk.to_class]
        step = 1 if b > a else -1
        chain: list[Item] = [("t", fk.from_class)]
        for col in range(a + step, b, step):
            columns[col].append(("l", i))
            chain.append(("l", i))
        chain.append(("t", fk.to_class))
        for u, v in zip(chain, chain[1:]):
            if u != v:
                neighbours.setdefault(u, set()).add(v)
                neighbours.setdefault(v, set()).add(u)

    def sweep(order: range, ref_offset: int) -> None:
        for col in order:
            ref = {item: i for i, item in enumerate(columns[col + ref_offset])}

            def key(pair: tuple[int, Item]) -> float:
                idx, item = pair
                hits = [ref[n] for n in neighbours.get(item, ()) if n in ref]
                return sum(hits) / len(hits) if hits else idx

            columns[col] = [item for _, item in sorted(enumerate(columns[col]), key=key)]

    for _ in range(2):
        sweep(range(1, len(columns)), -1)
        sweep(range(len(columns) - 2, -1, -1), +1)

    heights = {c.name: table_height(c) for c in schema.classes}
    boxes: dict[str, Box] = {}
    lane_at: dict[tuple[int, int], float] = {}
    for col, items in enumerate(columns):
        y: float = PAD
        for kind, ref in items:
            if kind == "t":
                boxes[ref] = Box(x=column_x(col), y=y, h=heights[ref])
                y += heights[ref] + ROW_GAP
            else:
                lane_at[(ref, col)] = y + ROW_H / 2
                y += ROW_H + ROW_GAP / 2

    lanes: dict[int, list[float]] = {}
    for i, fk in enumerate(schema.foreign_keys):
        a, b = col_of[fk.from_class], col_of[fk.to_class]
        step = 1 if b > a else -1
        lanes[i] = [lane_at[(i, col)] for col in range(a + step, b, step)]
    return Layout(boxes=boxes, lanes=lanes)


def _row_y(c: Class, box: Box, slot: str | None) -> float:
    """Vertical centre of a column row, or of the header when the slot is unknown."""
    for i, s in enumerate(c.slots):
        if s.name == slot:
            return box.y + HEADER_H + i * ROW_H + ROW_H / 2
    return box.y + HEADER_H / 2


def _curve(ax: float, ay: float, bx: float, by: float) -> str:
    """Cubic Bezier from a to b with horizontal tangents at both ends."""
    mx = (ax + bx) / 2
    return f"C{mx:g},{ay:g} {mx:g},{by:g} {bx:g},{by:g}"


def _edge_svg(fk: ForeignKey, lanes: list[float], classes: dict[str, Class], boxes: dict[str, Box]) -> str:
    src, dst = boxes[fk.from_class], boxes[fk.to_class]
    sy = _row_y(classes[fk.from_class], src, fk.from_slot)
    ty = _row_y(classes[fk.to_class], dst, fk.to_slot)

    if src.x == dst.x:
        # Same column (incl. self-references): loop out to the right.
        sx = tx = src.right
        bulge = LOOP + abs(ty - sy) / 6
        d = f"M{sx:g},{sy:g} C{sx + bulge:g},{sy:g} {tx + bulge:g},{ty:g} {tx:g},{ty:g}"
        lx, ly = sx + bulge * 0.75, (sy + ty) / 2
    else:
        # Leave from / arrive at the facing sides, crossing each intermediate
        # column straight through its reserved lane.
        forward = dst.x > src.x
        sx, tx = (src.right, dst.x) if forward else (src.x, dst.right)
        points = [(sx, sy)]
        for k, lane_y in enumerate(lanes, start=1):
            col_left = src.x + (k if forward else -k) * (TABLE_W + COL_GAP)
            enter, leave = (col_left, col_left + TABLE_W) if forward else (col_left + TABLE_W, col_left)
            points += [(enter, lane_y), (leave, lane_y)]
        points.append((tx, ty))

        d = f"M{sx:g},{sy:g}"
        for j in range(1, len(points)):
            (ax, ay), (bx, by) = points[j - 1], points[j]
            d += f" {_curve(ax, ay, bx, by)}" if j % 2 else f" L{bx:g},{by:g}"
        # Label the first gap, next to the foreign-key column.
        (ax, ay), (bx, by) = points[0], points[1]
        lx, ly = (ax + bx) / 2, (ay + by) / 2

    title = f"{fk.from_class}.{fk.from_slot} → {fk.to_class}" + (f".{fk.to_slot}" if fk.to_slot else "")
    return (
        f'<g class="edge"><title>{escape(title)}</title>'
        f'<path d="{d}" marker-end="url(#arrow)"/>'
        f'<text x="{lx:g}" y="{ly:g}">{escape(fk.cardinality)}</text></g>'
    )


def _table_html(c: Class, box: Box) -> str:
    rows = []
    for s in c.slots:
        classes = [k for k, on in (("pk", s.pk), ("fk", s.ref_class), ("unresolved", s.unresolved)) if on]
        marker = "⚠️" if s.unresolved else "🔑" if s.pk else "🔗" if s.ref_class else ""
        tip = f'Unknown range "{s.range}"' if s.unresolved else (s.description or "")
        rows.append(
            f'<div class="row {" ".join(classes)}"'
            + (f' title="{escape(tip)}"' if tip else "")
            + f'><span class="marker">{marker}</span>'
            f'<span class="name">{escape(s.name)}{"<span class=req>*</span>" if s.required else ""}</span>'
            f'<span class="type">{escape(s.range)}{"[]" if s.multivalued else ""}</span></div>'
        )
    if not rows:
        rows.append('<div class="row empty"><span></span><span class="name">no columns</span></div>')
    desc = escape(c.description or "")
    return (
        f'<section class="table" id="{escape(c.name)}" style="left:{box.x:g}px;top:{box.y:g}px">'
        f'<header><span class="title">{escape(c.name)}</span>'
        f'<span class="desc" title="{desc}">{desc}</span></header>'
        + "".join(rows)
        + "</section>"
    )


def _problems_html(schema: Schema) -> str:
    if not schema.problems:
        return ""
    items = "".join(
        f'<li><a href="#{escape(p.class_name)}">{escape(p.class_name)}.{escape(p.slot)}</a>: {escape(p.message)}</li>'
        for p in schema.problems
    )
    n = len(schema.problems)
    return f'<div class="problems"><strong>{n} problem{"s" if n != 1 else ""}</strong><ul>{items}</ul></div>'


def render_html(schema: Schema, source: str | None = None) -> str:
    """Render the schema as a complete, self-contained HTML document."""
    layout = layered_layout(schema)
    boxes = layout.boxes
    classes = {c.name: c for c in schema.classes}
    width = max((b.right for b in boxes.values()), default=0) + PAD + LOOP * 2
    lane_bottom = max((y for ys in layout.lanes.values() for y in ys), default=0) + ROW_H
    height = max([b.y + b.h for b in boxes.values()] + [lane_bottom]) + PAD

    edges = "".join(
        _edge_svg(fk, layout.lanes[i], classes, boxes) for i, fk in enumerate(schema.foreign_keys)
    )
    tables = "".join(_table_html(c, boxes[c.name]) for c in schema.classes)
    heading = escape(schema.title or schema.name)
    description = f"<p>{escape(schema.description)}</p>" if schema.description else ""
    footer = f"<footer>Generated by blueprint from <code>{escape(source)}</code></footer>" if source else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading}</title>
<style>{CSS}</style>
</head>
<body>
<header class="page">
<h1>{heading}</h1>
{description}
<p class="legend"><span>🔑 primary key</span><span>🔗 foreign key</span><span><span class="req">*</span> required</span><span>[] multivalued</span></p>
{_problems_html(schema)}
</header>
<main class="viewport">
<div class="canvas" style="width:{width:g}px;height:{height:g}px">
<svg class="edges" width="{width:g}" height="{height:g}" aria-hidden="true">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker></defs>
{edges}
</svg>
{tables}
</div>
</main>
{footer}
</body>
</html>
"""


CSS = f"""
:root {{
  --bg: #f1f5f9; --dot: #cbd5e1; --text: #0f172a; --muted: #64748b;
  --card: #ffffff; --border: #c7ccd6; --rule: #eef1f6;
  --head-bg: #1e293b; --head-text: #f8fafc; --head-muted: #cbd5e1;
  --pk: #fffbeb; --fk: #eff6ff; --bad-bg: #fef2f2; --bad: #b91c1c;
  --edge: #64748b; --shadow: rgba(15, 23, 42, 0.12);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #020617; --dot: #1e293b; --text: #e2e8f0; --muted: #94a3b8;
    --card: #0f172a; --border: #334155; --rule: #1e293b;
    --head-bg: #334155; --head-text: #f8fafc; --head-muted: #cbd5e1;
    --pk: #2a2410; --fk: #0f1f3a; --bad-bg: #3b0d0d; --bad: #fca5a5;
    --edge: #94a3b8; --shadow: rgba(0, 0, 0, 0.5);
  }}
}}
:root[data-theme="dark"] {{
  --bg: #020617; --dot: #1e293b; --text: #e2e8f0; --muted: #94a3b8;
  --card: #0f172a; --border: #334155; --rule: #1e293b;
  --head-bg: #334155; --head-text: #f8fafc; --head-muted: #cbd5e1;
  --pk: #2a2410; --fk: #0f1f3a; --bad-bg: #3b0d0d; --bad: #fca5a5;
  --edge: #94a3b8; --shadow: rgba(0, 0, 0, 0.5);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.4 ui-sans-serif, system-ui, -apple-system, sans-serif;
}}
.page {{ padding: 20px 16px 8px; max-width: 960px; }}
.page h1 {{ margin: 0 0 4px; font-size: 20px; }}
.page p {{ margin: 0 0 8px; color: var(--muted); }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; }}
.problems {{ border-left: 3px solid var(--bad); background: var(--bad-bg); padding: 8px 12px; margin: 8px 0; }}
.problems ul {{ margin: 4px 0 0; padding-left: 18px; }}
.problems a {{ color: var(--bad); }}
.viewport {{ overflow: auto; }}
.canvas {{
  position: relative;
  background-image: radial-gradient(var(--dot) 1px, transparent 1px);
  background-size: 20px 20px;
}}
.edges {{ position: absolute; inset: 0; overflow: visible; }}
.edge path {{ fill: none; stroke: var(--edge); stroke-width: 1.5; }}
.edge:hover path {{ stroke: var(--text); stroke-width: 2.5; }}
#arrow path {{ fill: var(--edge); }}
.edge text {{
  font-size: 11px; font-family: ui-monospace, SFMono-Regular, monospace; fill: var(--muted);
  text-anchor: middle; dominant-baseline: middle;
  paint-order: stroke; stroke: var(--bg); stroke-width: 4px; stroke-linejoin: round;
}}
.table {{
  position: absolute; width: {TABLE_W}px; font-size: 12px;
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 2px 8px var(--shadow); overflow: hidden;
}}
.table:target {{ outline: 3px solid var(--bad); }}
.table header {{
  height: {HEADER_H}px; padding: 6px 12px; display: flex; flex-direction: column; justify-content: center;
  background: var(--head-bg); color: var(--head-text);
}}
.table .title {{ font-weight: 700; letter-spacing: 0.02em; }}
.table .desc {{ font-size: 10px; color: var(--head-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.table .desc:empty {{ display: none; }}
.row {{
  height: {ROW_H}px; display: grid; grid-template-columns: 18px 1fr auto; align-items: center; gap: 8px;
  padding: 0 12px; border-top: 1px solid var(--rule); white-space: nowrap;
}}
.row.pk {{ background: var(--pk); }}
.row.fk {{ background: var(--fk); }}
.row.unresolved {{ background: var(--bad-bg); box-shadow: inset 3px 0 0 var(--bad); }}
.row.unresolved .name, .row.unresolved .type {{ color: var(--bad); }}
.row.empty .name {{ color: var(--muted); font-style: italic; font-weight: 400; }}
.marker {{ text-align: center; font-size: 10px; }}
.name {{ font-weight: 500; overflow: hidden; text-overflow: ellipsis; }}
.row.pk .name {{ font-weight: 700; }}
.req {{ color: #dc2626; margin-left: 1px; }}
.type {{ color: var(--muted); font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11px; }}
footer {{ padding: 8px 16px 20px; font-size: 12px; color: var(--muted); }}
"""
