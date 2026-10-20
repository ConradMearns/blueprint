from pathlib import Path

from blueprint.cli import main, output_path
from blueprint.parse import parse_linkml, parse_linkml_file
from blueprint.render import TABLE_W, layered_layout, render_html

EXAMPLE = Path(__file__).parent.parent / "examples" / "ecommerce.linkml.yaml"


def test_output_path_is_a_neighbour_html_file():
    assert output_path(Path("mydb.yaml")) == Path("mydb.html")
    assert output_path(Path("dir/schema.linkml.yaml")) == Path("dir/schema.linkml.html")
    assert output_path(Path("weird.yml")) == Path("weird.html")


def test_referencing_tables_sit_left_of_referenced_ones():
    schema = parse_linkml_file(EXAMPLE)
    boxes = layered_layout(schema).boxes
    for fk in schema.foreign_keys:
        if fk.from_class != fk.to_class:
            assert boxes[fk.from_class].x < boxes[fk.to_class].x, fk


def test_tables_do_not_overlap():
    boxes = list(layered_layout(parse_linkml_file(EXAMPLE)).boxes.values())
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert a.x + TABLE_W <= b.x or b.x + TABLE_W <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y


def test_long_edges_get_a_lane_per_skipped_column():
    schema = parse_linkml_file(EXAMPLE)
    layout = layered_layout(schema)
    col = {name: round(box.x) for name, box in layout.boxes.items()}
    step = sorted(set(col.values()))[1] - sorted(set(col.values()))[0]
    for i, fk in enumerate(schema.foreign_keys):
        skipped = max(0, abs(col[fk.to_class] - col[fk.from_class]) // step - 1)
        assert len(layout.lanes[i]) == skipped


def test_html_is_static_and_complete():
    schema = parse_linkml_file(EXAMPLE)
    html = render_html(schema)
    assert html.startswith("<!doctype html>")
    assert "<script" not in html
    assert html.count('class="table"') == len(schema.classes)
    assert html.count('class="edge"') == len(schema.foreign_keys)


def test_html_escapes_schema_text():
    html = render_html(parse_linkml('name: x\nclasses:\n  A:\n    description: "<b>&"\n'))
    assert "<b>&" not in html
    assert "&lt;b&gt;&amp;" in html


def test_problems_are_listed():
    html = render_html(parse_linkml("name: x\nclasses:\n  A:\n    attributes:\n      b: { range: Nope }\n"))
    assert "1 problem" in html
    assert 'range &quot;Nope&quot; is not a known class' in html


def test_cli_writes_neighbour_file(tmp_path):
    schema = tmp_path / "shop.yaml"
    schema.write_text(EXAMPLE.read_text())
    assert main([str(schema)]) == 0
    assert "OrderLine" in (tmp_path / "shop.html").read_text()


def test_cli_reports_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "missing.yaml")]) == 1
    assert "bp:" in capsys.readouterr().err
