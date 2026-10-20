import json
import re
from pathlib import Path

from blueprint.cli import main, output_path
from blueprint.parse import parse_linkml, parse_linkml_file
from blueprint.render import (
    COL_GAP,
    TABLE_W,
    apply_saved_layout,
    auto_layout,
    num,
    read_saved_layout,
    render_html,
)

EXAMPLE = Path(__file__).parent.parent / "examples" / "ecommerce.linkml.yaml"


def embedded_data(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="bp-data">(.*?)</script>', html, re.DOTALL)
    assert m
    return json.loads(m.group(1))


def save_canvas(html_path: Path, tables: dict, edges: dict | None = None) -> None:
    """Do what the page's "Save canvas" button does to the embedded layout."""
    html = html_path.read_text()
    data = embedded_data(html)
    data["layout"] = {"tables": tables, "edges": edges or {}}
    payload = json.dumps(data).replace("</", "<\\/")
    html_path.write_text(
        re.sub(
            r'(id="bp-data">).*?(</script>)',
            lambda m: m.group(1) + payload + m.group(2),
            html,
            flags=re.DOTALL,
        )
    )


def table_positions(html: str) -> dict[str, tuple[float, float]]:
    found = re.findall(r'data-name="(\w+)" style="left:([\d.]+)px;top:([\d.]+)px', html)
    return {name: (float(x), float(y)) for name, x, y in found}


def test_output_path_is_a_neighbour_html_file():
    assert output_path(Path("mydb.yaml")) == Path("mydb.html")
    assert output_path(Path("dir/schema.linkml.yaml")) == Path("dir/schema.linkml.html")
    assert output_path(Path("weird.yml")) == Path("weird.html")


def test_num_matches_js_number_formatting():
    assert [num(v) for v in (300.0, 312.5, 12.25, 0.04, 1234567.0)] == [
        "300",
        "312.5",
        "12.3",
        "0",
        "1234567",
    ]


# --- auto layout ---------------------------------------------------------------


def test_referencing_tables_sit_left_of_referenced_ones():
    schema = parse_linkml_file(EXAMPLE)
    boxes = auto_layout(schema).boxes
    for fk in schema.foreign_keys:
        if fk.from_class != fk.to_class:
            assert boxes[fk.from_class].x < boxes[fk.to_class].x, fk


def test_tables_do_not_overlap():
    boxes = list(auto_layout(parse_linkml_file(EXAMPLE)).boxes.values())
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert a.x + TABLE_W <= b.x or b.x + TABLE_W <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y


def test_long_edges_get_a_lane_per_skipped_column():
    schema = parse_linkml_file(EXAMPLE)
    layout = auto_layout(schema)
    for fk in schema.foreign_keys:
        span = abs(layout.boxes[fk.to_class].x - layout.boxes[fk.from_class].x) // (TABLE_W + COL_GAP)
        assert len(layout.waypoints.get(fk.id, [])) == 2 * max(0, span - 1), fk.id


# --- saved layout ----------------------------------------------------------------

TWO = "name: x\nclasses:\n  A:\n    attributes:\n      b: { range: B }\n  B:\n    attributes:\n      id: { identifier: true }\n"


def test_saved_positions_are_kept():
    schema = parse_linkml(TWO)
    layout = apply_saved_layout(
        schema, auto_layout(schema), {"tables": {"A": {"x": 500, "y": 20}, "B": {"x": 0, "y": 0}}}
    )
    assert (layout.boxes["A"].x, layout.boxes["A"].y) == (500, 20)
    assert (layout.boxes["B"].x, layout.boxes["B"].y) == (0, 0)


def test_new_tables_are_placed_below_pinned_ones():
    schema = parse_linkml(TWO + "  C:\n    attributes:\n      a: { range: A }\n  D: {}\n")
    saved = {"tables": {"A": {"x": 400, "y": 300}, "B": {"x": 0, "y": 0}, "Gone": {"x": 9, "y": 9}}}
    boxes = apply_saved_layout(schema, auto_layout(schema), saved).boxes
    pinned_bottom = max(boxes[n].y + boxes[n].h for n in ("A", "B"))
    assert boxes["C"].y > pinned_bottom and boxes["D"].y > pinned_bottom
    assert "Gone" not in boxes


def test_saved_edge_lanes_only_survive_between_pinned_tables():
    schema = parse_linkml(TWO + "  C:\n    attributes:\n      a: { range: A }\n")
    lane = [[10, 20], [30, 20]]
    saved = {
        "tables": {"A": {"x": 400, "y": 0}, "B": {"x": 900, "y": 0}},
        "edges": {"A.b->B": lane, "C.a->A": lane},
    }
    layout = apply_saved_layout(schema, auto_layout(schema), saved)
    assert layout.waypoints == {"A.b->B": [(10.0, 20.0), (30.0, 20.0)]}


def test_malformed_saved_layout_falls_back_to_auto():
    schema = parse_linkml(TWO)
    auto = auto_layout(schema)
    assert apply_saved_layout(schema, auto, {"tables": {"A": {"x": "nope"}}, "edges": 3}) is auto


# --- HTML ----------------------------------------------------------------------


def test_html_draws_everything_without_javascript():
    schema = parse_linkml_file(EXAMPLE)
    html = render_html(schema)
    assert html.startswith("<!doctype html>")
    assert html.count('class="table"') == len(schema.classes)
    assert html.count('<g class="edge"') == len(schema.foreign_keys)
    # Interactive controls stay hidden until the script reveals them.
    assert '<div class="actions" id="actions" hidden>' in html


def test_fresh_render_has_no_pinned_layout():
    data = embedded_data(render_html(parse_linkml_file(EXAMPLE)))
    assert data["layout"] == {}
    assert set(data["auto"]["tables"]) == {"Customer", "Address", "Category", "Product", "Order", "OrderLine"}


def test_html_escapes_schema_text():
    html = render_html(parse_linkml('name: x\nclasses:\n  A:\n    description: "<b>&</script>"\n'))
    assert "<b>&" not in html
    assert "&lt;b&gt;&amp;&lt;/script&gt;" in html
    assert html.count("</script>") == 2  # data block + canvas script; nothing leaked


def test_problems_are_listed():
    html = render_html(parse_linkml("name: x\nclasses:\n  A:\n    attributes:\n      b: { range: Nope }\n"))
    assert '<span class="bad"><strong>1</strong> issues' in html
    assert "range &quot;Nope&quot; is not a known class" in html


# --- CLI -------------------------------------------------------------------------


def test_cli_writes_neighbour_file(tmp_path):
    schema = tmp_path / "shop.yaml"
    schema.write_text(EXAMPLE.read_text())
    assert main([str(schema)]) == 0
    assert "OrderLine" in (tmp_path / "shop.html").read_text()


def test_cli_keeps_canvas_edits_across_schema_changes(tmp_path):
    schema = tmp_path / "shop.yaml"
    schema.write_text(EXAMPLE.read_text())
    out = tmp_path / "shop.html"
    main([str(schema)])

    moved = {name: {"x": x + 7, "y": y + 300} for name, (x, y) in table_positions(out.read_text()).items()}
    save_canvas(out, moved)
    assert read_saved_layout(out)["tables"] == moved

    coupon = "classes:\n  Coupon:\n    attributes:\n      order: { range: Order }\n"
    schema.write_text(EXAMPLE.read_text().replace("classes:\n", coupon, 1))
    main([str(schema)])
    positions = table_positions(out.read_text())
    assert {n: positions[n] for n in moved} == {n: (p["x"], p["y"]) for n, p in moved.items()}
    assert positions["Coupon"][1] > max(p["y"] for p in moved.values())

    main([str(schema), "--relayout"])
    assert embedded_data(out.read_text())["layout"] == {}


def test_cli_reads_layout_from_another_file(tmp_path):
    schema = tmp_path / "shop.yaml"
    schema.write_text(TWO)
    downloaded = tmp_path / "downloaded.html"
    main([str(schema), "-o", str(downloaded)])
    save_canvas(downloaded, {"A": {"x": 111, "y": 222}, "B": {"x": 600, "y": 0}})

    main([str(schema), "--layout", str(downloaded)])
    assert table_positions((tmp_path / "shop.html").read_text())["A"] == (111, 222)


def test_cli_reports_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "missing.yaml")]) == 1
    assert "bp:" in capsys.readouterr().err
