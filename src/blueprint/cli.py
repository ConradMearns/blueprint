"""`bp` -- render a LinkML schema to an HTML ER diagram.

Re-running bp keeps the canvas layout saved in the existing output page (via
its "Save canvas" button), so schema edits never undo where you put things.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import yaml

from .parse import parse_linkml_file
from .render import THEMES, read_saved_layout, read_saved_theme, render_html


def output_path(schema_path: Path) -> Path:
    """mydb.yaml -> mydb.html, schema.linkml.yaml -> schema.linkml.html."""
    return schema_path.with_suffix(".html")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("schema", type=Path, help="LinkML schema (.yaml)")
    ap.add_argument("-o", "--output", help="output file, or '-' for stdout (default: <schema>.html)")
    ap.add_argument(
        "--layout",
        type=Path,
        help="take the saved canvas layout from this page instead of the output file "
        "(e.g. a copy the browser saved to Downloads)",
    )
    ap.add_argument(
        "--relayout", action="store_true", help="ignore any saved layout and lay out from scratch"
    )
    ap.add_argument(
        "--theme",
        choices=THEMES,
        help="colour theme baked into the page (default: the one the output page already has, "
        "else auto, which follows the OS light/dark setting)",
    )
    ap.add_argument("--open", action="store_true", help="open the result in a browser")
    args = ap.parse_args(argv)

    try:
        schema = parse_linkml_file(args.schema)
    except (OSError, yaml.YAMLError) as e:
        print(f"bp: {e}", file=sys.stderr)
        return 1

    for p in schema.problems:
        print(f"{p.level}: {p.class_name}.{p.slot}: {p.message}", file=sys.stderr)

    out = None if args.output == "-" else Path(args.output) if args.output else output_path(args.schema)
    layout_from = args.layout or out
    saved = {} if args.relayout or layout_from is None else read_saved_layout(layout_from)
    if saved.get("tables"):
        print(f"keeping canvas layout saved in {layout_from}", file=sys.stderr)

    theme = args.theme or (read_saved_theme(out) if out else None) or "auto"
    html = render_html(
        schema,
        saved_layout=saved,
        source=args.schema.name,
        output_name=out.name if out else None,
        theme=theme,
    )
    if out is None:
        sys.stdout.write(html)
        return 0

    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0
