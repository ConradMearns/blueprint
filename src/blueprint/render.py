"""Render a parsed schema as a single self-contained HTML page.

Tables are absolutely positioned boxes with fixed header/row heights, so we
know exactly where every column sits and can draw the foreign-key edges as SVG
without measuring anything in a browser. The page works without JavaScript;
a small inline script adds dragging and a "Save canvas" button that writes the
page back out with the edited layout embedded. Re-rendering reads that layout
back (see `read_saved_layout`), so schema changes keep the user's canvas.

Edge routing is mirrored in `static/canvas.js` (`edgePath` / `num`) so edges redrawn while dragging match what we emit here.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from html import escape
from importlib.resources import files
from itertools import pairwise
from pathlib import Path
from typing import Any

from .parse import Class, ForeignKey, Schema

TABLE_W = 260
HEADER_H = 44
ROW_H = 24
BORDER = 1
COL_GAP = 140  # horizontal room between layers for edges + labels
ROW_GAP = 40
PAD = 48
LOOP = 36  # how far a same-side edge bulges out

Point = tuple[float, float]


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
    # Per foreign-key id: points where a long edge enters/leaves each column it
    # crosses (pairs, left-to-right in travel order), so it passes between
    # tables rather than under them.
    waypoints: dict[str, list[Point]] = field(default_factory=dict)


def column_x(col: int) -> float:
    return PAD + col * (TABLE_W + COL_GAP)


def table_height(c: Class) -> float:
    return 2 * BORDER + HEADER_H + max(1, len(c.slots)) * ROW_H


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


def auto_layout(schema: Schema) -> Layout:
    """Place tables in columns by foreign-key depth (a simple Sugiyama layout).

    Referencing tables sit to the left of what they point at, so edges flow
    left-to-right. Edges that skip columns reserve a lane in every column they
    cross, and a few barycenter sweeps order each column to reduce crossings.
    """
    depth = _depths(schema)
    max_depth = max(depth.values(), default=0)
    col_of = {name: max_depth - d for name, d in depth.items()}

    # Items are ("t", class name) for tables and ("l", fk id) for lanes.
    Item = tuple[str, str]
    columns: list[list[Item]] = [[] for _ in range(max_depth + 1)]
    for c in schema.classes:
        columns[col_of[c.name]].append(("t", c.name))

    neighbours: dict[Item, set[Item]] = {}
    for fk in schema.foreign_keys:
        a, b = col_of[fk.from_class], col_of[fk.to_class]
        step = 1 if b > a else -1
        chain: list[Item] = [("t", fk.from_class)]
        for col in range(a + step, b, step):
            columns[col].append(("l", fk.id))
            chain.append(("l", fk.id))
        chain.append(("t", fk.to_class))
        for u, v in pairwise(chain):
            if u != v:
                neighbours.setdefault(u, set()).add(v)
                neighbours.setdefault(v, set()).add(u)

    def sweep(order: range, ref_offset: int) -> None:
        for col in order:
            ref = {item: i for i, item in enumerate(columns[col + ref_offset])}

            def key(pair: tuple[int, Item], ref: dict[Item, int] = ref) -> float:
                idx, item = pair
                hits = [ref[n] for n in neighbours.get(item, ()) if n in ref]
                return sum(hits) / len(hits) if hits else idx

            columns[col] = [item for _, item in sorted(enumerate(columns[col]), key=key)]

    for _ in range(2):
        sweep(range(1, len(columns)), -1)
        sweep(range(len(columns) - 2, -1, -1), +1)

    heights = {c.name: table_height(c) for c in schema.classes}
    boxes: dict[str, Box] = {}
    lane_y: dict[tuple[str, int], float] = {}
    for col, items in enumerate(columns):
        y: float = PAD
        for kind, ref in items:
            if kind == "t":
                boxes[ref] = Box(x=column_x(col), y=y, h=heights[ref])
                y += heights[ref] + ROW_GAP
            else:
                lane_y[(ref, col)] = y + ROW_H / 2
                y += ROW_H + ROW_GAP / 2

    waypoints: dict[str, list[Point]] = {}
    for fk in schema.foreign_keys:
        a, b = col_of[fk.from_class], col_of[fk.to_class]
        forward = b > a
        points: list[Point] = []
        for col in range(a + (1 if forward else -1), b, 1 if forward else -1):
            left, y = column_x(col), lane_y[(fk.id, col)]
            points += [(left, y), (left + TABLE_W, y)] if forward else [(left + TABLE_W, y), (left, y)]
        if points:
            waypoints[fk.id] = points
    return Layout(boxes=boxes, waypoints=waypoints)


def apply_saved_layout(schema: Schema, auto: Layout, saved: dict[str, Any]) -> Layout:
    """Pin tables where the user left them on the canvas.

    Tables the saved layout knows keep their position; tables new to the
    schema keep their auto-layout column but are stacked below the pinned
    ones, so they never land on top of them. Saved edge waypoints are reused
    only while both ends of the edge are pinned tables.
    """
    pins: dict[str, Box] = {}
    for c in schema.classes:
        pos = (saved.get("tables") or {}).get(c.name)
        if isinstance(pos, dict) and all(isinstance(pos.get(k), (int, float)) for k in ("x", "y")):
            pins[c.name] = Box(x=pos["x"], y=pos["y"], h=table_height(c))
    if not pins:
        return auto

    below = max(b.y + b.h for b in pins.values()) + ROW_GAP * 2
    next_y: dict[float, float] = {}
    boxes: dict[str, Box] = {}
    for c in schema.classes:
        if c.name in pins:
            boxes[c.name] = pins[c.name]
        else:
            x = auto.boxes[c.name].x
            y = next_y.get(x, below)
            boxes[c.name] = Box(x=x, y=y, h=table_height(c))
            next_y[x] = y + boxes[c.name].h + ROW_GAP

    waypoints: dict[str, list[Point]] = {}
    saved_edges = saved.get("edges") or {}
    for fk in schema.foreign_keys:
        pts = saved_edges.get(fk.id)
        if fk.from_class in pins and fk.to_class in pins and isinstance(pts, list):
            try:
                waypoints[fk.id] = [(float(x), float(y)) for x, y in pts]
            except (TypeError, ValueError):
                pass
    return Layout(boxes=boxes, waypoints=waypoints)


def read_saved_data(html_path: Path) -> dict[str, Any]:
    """The embedded data of a page previously written by bp (or saved from it), or {}."""
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.search(r'<script[^>]*\bid="bp-data"[^>]*>(.*?)</script>', text, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def read_saved_layout(html_path: Path) -> dict[str, Any]:
    """Pull the canvas layout out of a page previously written by bp (or saved from it)."""
    layout = read_saved_data(html_path).get("layout")
    return layout if isinstance(layout, dict) else {}


def read_saved_theme(html_path: Path) -> str | None:
    """The theme a previous `bp --theme` baked into the page, if it is still one we know."""
    theme = read_saved_data(html_path).get("theme")
    return theme if theme in THEMES else None


# --- edge routing (mirrored in static/canvas.js) ----------------------------


def num(v: float) -> str:
    """Round to 0.1 and print the way JS's String(number) does."""
    r = math.floor(v * 10 + 0.5) / 10
    return str(int(r)) if r == int(r) else repr(r)


def row_y(box: Box, index: int) -> float:
    """Vertical centre of the index-th column row, or of the header when index < 0."""
    if index < 0:
        return box.y + BORDER + HEADER_H / 2
    return box.y + BORDER + HEADER_H + index * ROW_H + ROW_H / 2


def edge_path(src: Box, sy: float, dst: Box, ty: float, waypoints: list[Point]) -> tuple[str, Point]:
    """SVG path between two rows, plus where to put the cardinality label.

    Curves leave/enter the facing sides of the two tables and cross any
    intermediate columns straight through their reserved lane (`waypoints`).
    """
    if not waypoints and dst.x < src.right and src.x < dst.right:
        # Tables overlap horizontally (incl. self-references): loop out to the right.
        sx, tx = src.right, dst.right
        bulge = LOOP + abs(ty - sy) / 6
        d = f"M{num(sx)},{num(sy)} C{num(sx + bulge)},{num(sy)} {num(tx + bulge)},{num(ty)} {num(tx)},{num(ty)}"
        return d, (max(sx, tx) + bulge * 0.75, (sy + ty) / 2)

    forward = dst.x > src.x
    sx, tx = (src.right, dst.x) if forward else (src.x, dst.right)
    anchors = [(sx, sy), *waypoints, (tx, ty)]
    d = f"M{num(sx)},{num(sy)}"
    for j in range(1, len(anchors)):
        (ax, ay), (bx, by) = anchors[j - 1], anchors[j]
        if j % 2:  # across a gap between columns
            mx = (ax + bx) / 2
            d += f" C{num(mx)},{num(ay)} {num(mx)},{num(by)} {num(bx)},{num(by)}"
        else:  # straight through a lane
            d += f" L{num(bx)},{num(by)}"
    (ax, ay), (bx, by) = anchors[0], anchors[1]
    return d, ((ax + bx) / 2, (ay + by) / 2)


# --- HTML --------------------------------------------------------------------


def _slot_index(c: Class, slot: str | None) -> int:
    return next((i for i, s in enumerate(c.slots) if s.name == slot), -1)


def _edge_svg(fk: ForeignKey, classes: dict[str, Class], layout: Layout) -> str:
    src, dst = layout.boxes[fk.from_class], layout.boxes[fk.to_class]
    sy = row_y(src, _slot_index(classes[fk.from_class], fk.from_slot))
    ty = row_y(dst, _slot_index(classes[fk.to_class], fk.to_slot))
    waypoints = layout.waypoints.get(fk.id, [])
    d, (lx, ly) = edge_path(src, sy, dst, ty, waypoints)

    attrs = {
        "data-id": fk.id,
        "data-from": fk.from_class,
        "data-from-slot": fk.from_slot,
        "data-to": fk.to_class,
        "data-to-slot": fk.to_slot or "",
    }
    if waypoints:
        attrs["data-waypoints"] = json.dumps([[x, y] for x, y in waypoints])
    title = f"{fk.from_class}.{fk.from_slot} → {fk.to_class}" + (f".{fk.to_slot}" if fk.to_slot else "")
    return (
        '<g class="edge"' + "".join(f' {k}="{escape(v)}"' for k, v in attrs.items()) + ">"
        f"<title>{escape(title)}</title>"
        f'<path d="{d}" marker-end="url(#arrow)"/>'
        f'<text x="{num(lx)}" y="{num(ly)}">{escape(fk.cardinality)}</text></g>'
    )


def _table_html(c: Class, box: Box) -> str:
    rows = []
    for s in c.slots:
        kinds = [k for k, on in (("pk", s.pk), ("fk", s.ref_class), ("unresolved", s.unresolved)) if on]
        marker = "⚠️" if s.unresolved else "🔑" if s.pk else "🔗" if s.ref_class else ""
        tip = f'Unknown range "{s.range}"' if s.unresolved else (s.description or "")
        rows.append(
            f'<div class="row {" ".join(kinds)}" data-slot="{escape(s.name)}"'
            + (f' title="{escape(tip)}"' if tip else "")
            + f'><span class="marker">{marker}</span>'
            f'<span class="name">{escape(s.name)}{"<span class=req>*</span>" if s.required else ""}</span>'
            f'<span class="type">{escape(s.range)}{"[]" if s.multivalued else ""}</span></div>'
        )
    if not rows:
        rows.append('<div class="row empty"><span></span><span class="name">no columns</span></div>')
    desc = (
        f'<span class="desc" title="{escape(c.description)}">{escape(c.description)}</span>'
        if c.description
        else ""
    )
    return (
        f'<section class="table" id="{escape(c.name)}" data-name="{escape(c.name)}"'
        f' style="left:{num(box.x)}px;top:{num(box.y)}px">'
        f'<header><span class="title">{escape(c.name)}</span>{desc}</header>' + "".join(rows) + "</section>"
    )


def _issues_html(schema: Schema) -> str:
    n = len(schema.problems)
    if not n:
        return '<span class="stat"><strong>0</strong> issues</span>'
    items = "".join(
        f'<li title="{escape(p.message)}"><a href="#{escape(p.class_name)}" data-table="{escape(p.class_name)}">'
        f"<code>{escape(p.class_name)}.{escape(p.slot)}</code></a> — {escape(p.message)}</li>"
        for p in schema.problems
    )
    return (
        f'<details class="issues"><summary>⚠️ <strong>{n}</strong> issue{"s" if n != 1 else ""}</summary>'
        f'<ul class="problems">{items}</ul></details>'
    )


def _json_script(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _asset(name: str) -> str:
    return files("blueprint").joinpath("static", name).read_text(encoding="utf-8")


# "auto" follows the OS light/dark setting; the rest are the blocks in themes.css.
THEMES = ("auto", *re.findall(r':root\[data-theme="([\w-]+)"\]', _asset("themes.css")))


def _theme_menu(theme: str) -> str:
    options = "".join(
        f'<option value="{t}"{" selected" if t == theme else ""}>{t.capitalize()}</option>' for t in THEMES
    )
    return f'<select id="theme" title="Theme" aria-label="Theme">{options}</select>'


def _bounds(layout: Layout) -> tuple[float, float, float, float]:
    """Extent of everything drawn, in canvas coordinates (positions may be negative)."""
    xs = [b.x for b in layout.boxes.values()] + [b.right + 2 * LOOP for b in layout.boxes.values()]
    ys = [b.y for b in layout.boxes.values()] + [b.y + b.h for b in layout.boxes.values()]
    for pts in layout.waypoints.values():
        xs += [x for x, _ in pts]
        ys += [y + d for _, y in pts for d in (-ROW_H, ROW_H)]
    return (min(xs, default=0), min(ys, default=0), max(xs, default=0), max(ys, default=0))


def render_html(
    schema: Schema,
    *,
    saved_layout: dict[str, Any] | None = None,
    source: str | None = None,
    output_name: str | None = None,
    theme: str = "auto",
) -> str:
    """Render the schema as a complete, self-contained HTML document.

    `saved_layout` is the canvas layout read back from a previous render (see
    `read_saved_layout`); tables it mentions keep their position. `theme` is
    one of THEMES; viewers can still switch theme in the page.
    """
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r} (choose from {', '.join(THEMES)})")
    auto = auto_layout(schema)
    layout = apply_saved_layout(schema, auto, saved_layout or {})
    pinned = layout is not auto
    classes = {c.name: c for c in schema.classes}

    # Without JS the page just scrolls, so shift everything into view; the
    # script replaces this with a pannable, zoomable view fitted to the content.
    x0, y0, x1, y1 = _bounds(layout)
    width, height = x1 - x0 + 2 * PAD, y1 - y0 + 2 * PAD

    edges = "".join(_edge_svg(fk, classes, layout) for fk in schema.foreign_keys)
    tables = "".join(_table_html(c, layout.boxes[c.name]) for c in schema.classes)
    heading = escape(schema.title or schema.name)

    data = {
        "file": output_name,
        "theme": theme,
        "geometry": {
            "tableW": TABLE_W,
            "headerH": HEADER_H,
            "rowH": ROW_H,
            "border": BORDER,
            "loop": LOOP,
            "pad": PAD,
        },
        # What "Save canvas" writes and the next `bp` run reads back.
        "layout": {
            "tables": {n: {"x": b.x, "y": b.y} for n, b in layout.boxes.items()},
            "edges": {k: [[x, y] for x, y in v] for k, v in layout.waypoints.items()},
        }
        if pinned
        else {},
        # Where "Reset layout" puts things.
        "auto": {
            "tables": {n: {"x": b.x, "y": b.y} for n, b in auto.boxes.items()},
            "edges": {k: [[x, y] for x, y in v] for k, v in auto.waypoints.items()},
        },
    }

    file_label = ""
    if source:
        target = f" → {escape(output_name)}" if output_name else ""
        file_label = f'<span class="file" title="{escape(source)}{target}">{escape(source)}{target}</span>'
    description = f' title="{escape(schema.description)}"' if schema.description else ""

    return f"""<!doctype html>
<html lang="en"{"" if theme == "auto" else f' data-theme="{theme}"'}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading}</title>
<script>try {{ const r = document.documentElement, t = localStorage.getItem("bp-theme:" + location.pathname + ":" + (r.dataset.theme || "auto")); if (t === "auto") delete r.dataset.theme; else if (t) r.dataset.theme = t; }} catch {{}}</script>
<style>
:root {{ --table-w: {TABLE_W}px; --header-h: {HEADER_H}px; --row-h: {ROW_H}px; }}
{_asset("themes.css")}
{_asset("style.css")}</style>
</head>
<body>
<header class="bar">
<span class="brand">blueprint</span>
<h1{description}>{heading}</h1>
{file_label}
<span class="stat"><strong>{len(schema.classes)}</strong> classes</span>
<span class="stat"><strong>{len(schema.foreign_keys)}</strong> relations</span>
{_issues_html(schema)}
<span class="save-state" id="save-state"></span>
<span class="actions" id="actions" hidden>
{_theme_menu(theme)}
<button id="reset" title="Discard manual positions and use the automatic layout">Reset layout</button>
<button id="save" class="primary" title="Write this page back out with the current canvas layout">Save canvas</button>
</span>
</header>
<main class="viewport" id="viewport">
<div class="sizer" id="sizer" style="width:{num(width)}px;height:{num(height)}px">
<div class="world" id="world" style="transform:translate({num(PAD - x0)}px,{num(PAD - y0)}px)">
<svg class="edges" id="edges" width="1" height="1" aria-hidden="true">
<defs><marker id="arrow" viewBox="-10 -10 20 20" refX="0" refY="0" markerWidth="18" markerHeight="18" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><polyline points="-5,-4 0,0 -5,4 -5,-4"/></marker></defs>
{edges}
</svg>
{tables}
</div>
</div>
<div class="legend"><span><span class="dot pk"></span> primary key</span><span><span class="dot fk"></span> foreign key</span></div>
<div class="controls" id="controls" hidden>
<button id="zoom-in" title="Zoom in">+</button>
<button id="zoom-out" title="Zoom out">−</button>
<button id="fit" title="Fit view">⛶</button>
<span id="zoom-level">100%</span>
</div>
</main>
<script type="application/json" id="bp-data">{_json_script(data)}</script>
<script>
{_asset("canvas.js")}</script>
</body>
</html>
"""
