import io
import sys
from contextlib import redirect_stdout

import pytest

from picsort import cli


def test_version_flag_short_circuits_no_network(capsys):
    cli.main(["--version"])
    out = capsys.readouterr().out
    assert "picsort" in out
    assert "0.1.0" in out


def test_version_short_flag(capsys):
    cli.main(["-V"])
    out = capsys.readouterr().out
    assert "0.1.0" in out


def test_select_mode_returns_valid_key(monkeypatch):
    for choice, expect in (("1", "media"), ("2", "documents")):
        monkeypatch.setattr("builtins.input", lambda *a, **k: choice)
        assert cli.select_mode() == expect
