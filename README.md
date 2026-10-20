# blueprint

Render a **[LinkML](https://linkml.io/) schema as an ER diagram** in a single,
static HTML file.

![blueprint rendering a LinkML schema as an ER diagram](docs/screenshot.png)

Point it at a LinkML schema and blueprint draws an entity-relationship diagram —
one table per class, columns from slots, and edges for the foreign-key
relationships implied by slots whose range is another class. The output is one
self-contained `.html` file you can open locally, commit, or host anywhere. The
diagram is plain HTML + SVG; a small inline script turns it into an infinite
canvas you can pan, zoom and rearrange.

Same idea as [dbml](https://dbml.dbdiagram.io/), except **LinkML is the source
of truth** — no custom DSL.

## Usage

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv run bp mydb.yaml              # writes mydb.html next to the schema
uv run bp mydb.yaml -o out.html  # choose the output path
uv run bp mydb.yaml -o -         # write to stdout
uv run bp mydb.yaml --open       # also open it in a browser
```

To put `bp` on your PATH: `uv tool install .`

Schema problems (e.g. a slot whose range is an unknown class) are printed to
stderr and listed at the top of the page; the affected columns are highlighted.

## Editing the canvas

Drag the background to pan, scroll (or pinch) to zoom, and use the controls in
the bottom-left to zoom or fit everything in view. Drag tables to rearrange
them, then click **Save canvas** in the top bar. The ◐ button toggles light/dark
(it follows your OS setting until you pick one). The page writes
itself back out with your layout embedded:

- **Chromium-based browsers** open a save dialog the first time — browsers
  can't start it in the page's own folder, so navigate to `mydb.html` once and
  overwrite it. The browser then remembers that file for this page, and later
  saves (even after a restart) write straight back to it, at most asking you to
  allow editing.
- **Other browsers** download a copy, which you move over the original or point
  `bp --layout` at (below).

The HTML file _is_ the layout store. Re-running `bp mydb.yaml` reads the layout
saved in `mydb.html` before overwriting it, so editing the schema never undoes
your canvas:

- tables you placed stay where they are;
- tables new to the schema are placed below the existing ones;
- tables removed from the schema simply disappear.

```bash
bp mydb.yaml --layout ~/Downloads/mydb.html   # take the layout from another copy
bp mydb.yaml --relayout                       # discard it and lay out from scratch
```

**Reset layout** in the page does the same as `--relayout` once saved.

Until you save a layout, tables are placed automatically in columns by
foreign-key depth: a table sits to the left of every table it references, so
edges flow left to right, and edges that skip a column are routed through a
reserved lane rather than under other tables.

## Development

```bash
uv run pytest
```

| Concern                 | Module                    |
| ----------------------- | ------------------------- |
| Parse LinkML → ER model | `src/blueprint/parse.py`  |
| Layout + HTML/SVG       | `src/blueprint/render.py` |
| Page styles             | `src/blueprint/static/style.css` |
| Pan / zoom / drag / save | `src/blueprint/static/canvas.js` |
| `bp` command            | `src/blueprint/cli.py`    |

Edge routing exists twice — `edge_path` in `render.py` and `edgePath` in
`canvas.js` — so edges redrawn while dragging match what `bp` emits; keep them
in step.

### LinkML subset supported

`classes` with inline `attributes` and/or referenced top-level `slots`,
reusable `slots`, `slot_usage` overrides, `is_a` / `mixins` inheritance, and
`imports` (slots/classes/types/enums pulled from sibling files, resolved
relative to the importing file). Attributes and slots are interchangeable. A
slot is treated as a **foreign key** when its `range` matches another class
name; `identifier: true` (or `key: true`) marks the **primary key**.

Equivalence across these representations is locked down by `tests/fixtures/` —
every variant of the ecommerce schema must produce the same diagram (see that
folder's README).

## Issue tracking

This repo uses [Seeds](https://github.com/jayminwest/seeds) (`sd`) for git-native
issue tracking. Run `sd prime` for the workflow, `sd ready` to find work.
