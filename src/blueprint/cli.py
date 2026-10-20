"""`bp` -- render a LinkML schema to a static HTML ER diagram."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import yaml

from .parse import parse_linkml_file
from .render import render_html


def output_path(schema_path: Path) -> Path:
    """mydb.yaml -> mydb.html, schema.linkml.yaml -> schema.linkml.html."""
    return schema_path.with_suffix(".html")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bp", description=__doc__)
    ap.add_argument("schema", type=Path, help="LinkML schema (.yaml)")
    ap.add_argument("-o", "--output", help="output file, or '-' for stdout (default: <schema>.html)")
    ap.add_argument("--open", action="store_true", help="open the result in a browser")
    args = ap.parse_args(argv)

    try:
        schema = parse_linkml_file(args.schema)
    except (OSError, yaml.YAMLError) as e:
        print(f"bp: {e}", file=sys.stderr)
        return 1

    for p in schema.problems:
        print(f"{p.level}: {p.class_name}.{p.slot}: {p.message}", file=sys.stderr)

    html = render_html(schema, source=args.schema.name)
    if args.output == "-":
        sys.stdout.write(html)
        return 0

    out = Path(args.output) if args.output else output_path(args.schema)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0
