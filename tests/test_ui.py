from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from picsort import core, ui


def test_console_print_writes():
    ui.CONSOLE.print("hello")  # must not raise


def test_center_block_pads():
    out = ui._center_block("abc")
    assert out.strip() == "abc"
    assert out != "abc"  # has leading padding


def test_human_bytes():
    assert ui._human_bytes(0) == "0 B"
    assert ui._human_bytes(1024) == "1.0 KB"


def test_summary_panel_is_panel():
    cfg = core.MODE_CONFIGS["media"]
    panel = {"sources": 1, "scanned": 2, "copied": 2, "duplicates": 0, "fallback": 0, "errors": 0}
    p = ui._summary_panel(cfg, panel, {"photo": 2, "video": 0}, 5.0)
    assert isinstance(p, Panel)


def test_per_type_table_is_table():
    cfg = core.MODE_CONFIGS["documents"]
    t = ui._per_type_table({"pdf": 1, "word": 0, "excel": 0, "ppt": 0}, cfg)
    assert isinstance(t, Table)


from rich.layout import Layout


def test_build_layout_has_title_and_body():
    from picsort import ui
    cfg = core.MODE_CONFIGS["media"]
    left = ui._left_panel(cfg, Text("L"))
    right = ui._right_panel(cfg, {"copied": 0, "duplicates": 0, "fallback": 0, "errors": 0},
                            {}, [], 0, 0, 0.0, None, None)
    layout = ui._build_layout(cfg, left, right)
    assert isinstance(layout, Layout)
    names = [c.name for c in layout.children]
    assert "title" in names
    assert "body" in names


def test_title_bar_has_traffic_light_dots_and_title():
    p = ui._title_bar()
    assert isinstance(p, Panel)
    text = p.renderable
    assert isinstance(text, Text)
    assert "picsort" in text.plain
    styles = [str(span.style) for span in text._spans]
    for dot in ("FF5F56", "FFBD2E", "27C93F"):
        assert any(dot in s for s in styles), f"{dot} not found in styles"
