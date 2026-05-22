"""Tests for NLU rules engine — no Ollama or Windows APIs needed."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def disable_ollama():
    """Force rules-only mode so tests never call the network."""
    with patch("assistant.nlu.engine.OLLAMA_ENABLED", False):
        yield


def _nlu(phrase: str) -> dict:
    from assistant.nlu import nlu_rules
    return nlu_rules(phrase)


class TestOpenApp:
    def test_open_notepad_russian(self):
        result = _nlu("открой блокнот")
        assert result["intent"] == "open_app"
        assert result["args"]["alias"] == "notepad"

    def test_open_chrome(self):
        result = _nlu("открой хром")
        assert result["intent"] == "open_app"
        assert result["args"]["alias"] == "chrome"

    def test_open_telegram(self):
        result = _nlu("запусти телеграм")
        assert result["intent"] == "open_app"
        assert result["args"]["alias"] == "telegram"

    def test_open_settings(self):
        result = _nlu("открой настройки")
        assert result["intent"] == "open_app"
        assert result["args"]["alias"] == "settings"


class TestBrowserSearch:
    def test_search_verb(self):
        result = _nlu("загугли погода в москве")
        assert result["intent"] == "open_browser_search"
        assert "погода" in result["args"]["query"].lower()

    def test_find_verb(self):
        result = _nlu("найди рецепт блинов")
        assert result["intent"] in ("open_browser_search", "smart_search")


class TestSystemVolume:
    def test_set_volume_50(self):
        result = _nlu("установить громкость 50")
        assert result["intent"] == "system_volume"
        assert result["args"]["level"] == 50

    def test_volume_clamped_at_100(self):
        result = _nlu("установить громкость 150")
        if result["intent"] == "system_volume":
            assert result["args"]["level"] <= 100


class TestScreenshot:
    def test_screenshot(self):
        result = _nlu("сделать скриншот")
        assert result["intent"] == "screenshot"
        assert result["args"] == {}


class TestSystemCommands:
    def test_shutdown(self):
        result = _nlu("выключить компьютер")
        assert result["intent"] == "system_shutdown"

    def test_restart(self):
        result = _nlu("перезагрузить систему")
        assert result["intent"] == "system_restart"

    def test_sleep(self):
        result = _nlu("режим сна")
        assert result["intent"] == "system_sleep"

    def test_lock(self):
        result = _nlu("заблокировать компьютер")
        assert result["intent"] == "system_lock"

    def test_wifi(self):
        result = _nlu("переключить вайфай")
        assert result["intent"] == "wifi_toggle"


class TestConfirmCancel:
    def test_confirm(self):
        result = _nlu("да")
        assert result["intent"] == "confirm_action"

    def test_cancel(self):
        result = _nlu("нет отмена")
        assert result["intent"] == "cancel_action"


class TestSmallTalk:
    def test_empty_phrase_returns_smalltalk(self):
        result = _nlu("")
        assert result["intent"] == "smalltalk"

    def test_unknown_phrase_returns_smalltalk(self):
        result = _nlu("какая-то непонятная фраза без смысла xyz")
        assert result["intent"] == "smalltalk"
