"""Tests that skills raise SkillError on failure."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from assistant.core.exceptions import (
    AssistantError,
    AudioError,
    ConfigError,
    OllamaError,
    SkillError,
)


class TestExceptionHierarchy:
    def test_skill_error_is_assistant_error(self):
        exc = SkillError("test")
        assert isinstance(exc, AssistantError)

    def test_ollama_error_is_assistant_error(self):
        exc = OllamaError("test")
        assert isinstance(exc, AssistantError)

    def test_config_error_is_assistant_error(self):
        exc = ConfigError("test")
        assert isinstance(exc, AssistantError)

    def test_audio_error_is_assistant_error(self):
        exc = AudioError("test")
        assert isinstance(exc, AssistantError)

    def test_all_catchable_as_base(self):
        for cls in (SkillError, OllamaError, ConfigError, AudioError):
            try:
                raise cls("boom")
            except AssistantError:
                pass


class TestCloseAppProtectedProcesses:
    def test_close_lsass_raises_skill_error(self):
        from assistant.skills.app_control import PROTECTED_PROCESSES, close_app
        assert "lsass.exe" in PROTECTED_PROCESSES
        with pytest.raises(SkillError, match="защищённый"):
            close_app("lsass")

    def test_close_winlogon_raises_skill_error(self):
        from assistant.skills.app_control import close_app
        with pytest.raises(SkillError, match="защищённый"):
            close_app("winlogon")


class TestOpenAppUnknownRaisesSkillError:
    def test_open_unknown_raises(self):
        from assistant.skills.app_control import open_app
        with (
            patch("assistant.skills.app_control._resolve_app_path", return_value=(None, [])),
        ):
            with pytest.raises(SkillError, match="Не знаю"):
                open_app("nonexistent_app_xyz")
