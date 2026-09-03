from rich.panel import Panel
from rich.table import Table

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
