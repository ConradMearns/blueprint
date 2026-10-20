"""linkml-herd: render a LinkML schema as a static ER-diagram HTML page."""

from .parse import parse_linkml, parse_linkml_file
from .render import render_html

__all__ = ["parse_linkml", "parse_linkml_file", "render_html"]
