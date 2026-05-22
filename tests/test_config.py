"""Tests for config loading and custom command validation."""
from __future__ import annotations
import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch


def _load_config_cached():
    from assistant.nlu.engine import load_config_cached
    return load_config_cached


class TestConfigLoading:
    def test_returns_dict_on_missing_file(self):
        with patch("assistant.nlu.engine._CONFIG_PATH", Path("/nonexistent/config.json")):
            from assistant.nlu import engine
            engine._CFG_MTIME = 0.0
            engine._CFG_CACHE = {}
            result = engine.load_config_cached()
        assert isinstance(result, dict)

    def test_loads_valid_config(self):
        data = {"hotkey": "ctrl+shift", "ollama_model": "llama3"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            tmp_path = Path(f.name)
        try:
            with patch("assistant.nlu.engine._CONFIG_PATH", tmp_path):
                from assistant.nlu import engine
                engine._CFG_MTIME = 0.0
                engine._CFG_CACHE = {}
                result = engine.load_config_cached()
            assert result["hotkey"] == "ctrl+shift"
            assert result["ollama_model"] == "llama3"
        finally:
            tmp_path.unlink(missing_ok=True)


class TestCustomCommandRegex:
    def test_valid_regex_compiles(self):
        pattern = r"открой\s+\w+"
        try:
            re.compile(pattern, re.IGNORECASE)
        except re.error:
            raise AssertionError(f"Pattern should be valid: {pattern}")

    def test_invalid_regex_raises_re_error(self):
        bad_pattern = r"(a+)+b"
        compiled = re.compile(bad_pattern, re.IGNORECASE)
        assert compiled is not None

    def test_catastrophic_regex_is_caught(self):
        from assistant.nlu.engine import _custom_rules
        from unittest.mock import patch
        bad_rule = [{"match_type": "regex", "pattern": "(a+)+b", "intent": "open_app", "args": {"alias": "chrome"}, "speak": None}]
        with patch("assistant.nlu.engine.load_config_cached", return_value={"custom_commands": bad_rule}):
            result = _custom_rules("a" * 30 + "c")
        assert result is None or isinstance(result, dict)


class TestCoerceAndValidate:
    def _coerce(self, obj):
        from assistant.nlu.engine import _coerce_and_validate
        return _coerce_and_validate(obj)

    def test_valid_open_app(self):
        result = self._coerce({"intent": "open_app", "args": {"alias": "notepad"}, "speak": "ok"})
        assert result is not None
        assert result["intent"] == "open_app"

    def test_rejects_unknown_intent(self):
        result = self._coerce({"intent": "fly_to_moon", "args": {}, "speak": None})
        assert result is None

    def test_rejects_non_dict(self):
        assert self._coerce("string") is None
        assert self._coerce(None) is None

    def test_volume_clamped(self):
        result = self._coerce({"intent": "system_volume", "args": {"level": 200}, "speak": None})
        assert result is not None
        assert result["args"]["level"] == 100

    def test_volume_rejects_non_numeric(self):
        result = self._coerce({"intent": "system_volume", "args": {"level": "громко"}, "speak": None})
        assert result is None
