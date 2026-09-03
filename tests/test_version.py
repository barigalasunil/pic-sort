import tomllib

from pathlib import Path

import picsort


def test_picsort_imports():
    assert isinstance(picsort.__version__, str)


def test_pyproject_version_matches_init():
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    # version is sourced dynamically from picsort.__version__, so the attr
    # path must point at it.
    assert "version" in data["project"]["dynamic"]
    assert data["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "picsort.__version__"
    assert data["project"]["name"] == "picsort-cli"
    assert data["project"]["scripts"]["picsort"] == "picsort.cli:main"
