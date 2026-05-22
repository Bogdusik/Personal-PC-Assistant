"""Tests for app path resolution — mocks filesystem and registry."""
from __future__ import annotations

from unittest.mock import patch


def _resolver():
    from assistant.skills.app_control import _resolve_app_path
    return _resolve_app_path


class TestKnownAliases:
    def test_notepad_resolves_to_known_path(self):
        with patch("assistant.skills.app_control._exists", return_value=True):
            path, args = _resolver()("notepad")
        assert path is not None
        assert "notepad" in path.lower()
        assert args == []

    def test_settings_returns_ms_settings_uri(self):
        path, args = _resolver()("settings")
        assert path == "ms-settings:"
        assert args == []

    def test_unknown_alias_returns_none(self):
        with (
            patch("assistant.skills.app_control._exists", return_value=False),
            patch("assistant.skills.app_control._find_app_path", return_value=None),
            patch("assistant.skills.app_control.shutil.which", return_value=None),
        ):
            path, args = _resolver()("totally_unknown_app_xyz")
        assert path is None

    def test_empty_alias_returns_none(self):
        path, args = _resolver()("")
        assert path is None
        assert args == []


class TestAppAliasConfig:
    def test_custom_alias_from_config(self):
        from assistant.skills.app_control import APP_ALIASES
        APP_ALIASES["myapp"] = r"C:\fake\myapp.exe"
        try:
            with patch("assistant.skills.app_control._exists", return_value=True):
                path, args = _resolver()("myapp")
            assert path == r"C:\fake\myapp.exe"
        finally:
            APP_ALIASES.pop("myapp", None)

    def test_ms_settings_uri_in_config(self):
        from assistant.skills.app_control import APP_ALIASES
        APP_ALIASES["testms"] = "ms-settings:bluetooth"
        try:
            path, args = _resolver()("testms")
            assert path == "ms-settings:bluetooth"
        finally:
            APP_ALIASES.pop("testms", None)
