from picsort import core


def test_theme_has_all_semantic_roles():
    for role in ("header", "success", "warning", "fallback", "error",
                 "dim", "panel_bg", "teal", "purple"):
        assert role in core.THEME
        assert isinstance(core.THEME[role], str)
        assert core.THEME[role].startswith("#")


def test_status_color_aliases_point_at_theme():
    assert core.GREEN == core.THEME["success"]
    assert core.YELLOW == core.THEME["warning"]
    assert core.RED == core.THEME["error"]
    assert core.DIM == core.THEME["dim"]
    assert core.FALLBACK == core.THEME["fallback"]


def test_mode_and_type_colors_come_from_theme():
    media = core.MODE_CONFIGS["media"]
    docs = core.MODE_CONFIGS["documents"]
    assert media["accent"] == core.THEME["teal"]
    assert docs["accent"] == core.THEME["purple"]
    assert media["types"]["photo"]["color"] == core.THEME["success"]
    assert media["types"]["video"]["color"] == core.THEME["header"]
    assert docs["types"]["pdf"]["color"] == core.THEME["error"]
    assert docs["types"]["ppt"]["color"] == core.THEME["purple"]
    assert docs["types"]["word"]["color"] == core.THEME["header"]
    assert docs["types"]["excel"]["color"] == core.THEME["success"]
