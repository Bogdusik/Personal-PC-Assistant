from __future__ import annotations
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from .normalizer import _clean, _lemmatize_line, _normalize_app_name, _wrap
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)

USE_RULES_FIRST = True
OLLAMA_ENABLED = True

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"

ALLOWED_INTENTS = {
    "open_app", "open_browser_search", "system_volume", "screenshot", "smalltalk",
    "open_website", "minimize_app", "close_app", "system_shutdown", "system_restart",
    "system_sleep", "system_lock", "wifi_toggle", "brightness_set",
    "clipboard_copy", "clipboard_paste", "confirm_action", "cancel_action",
    "system_status", "list_commands", "delete_command", "teach_command",
    "smart_search", "ai_search",
}

PROMPT_SYSTEM = """Ты — локальный голосовой ассистент на ПК.
Верни ТОЛЬКО один JSON-объект без пояснений/разметки.

Допустимые intents:
- "open_app": args = {"alias": "chrome|notepad|telegram|discord|steam|code|calc|cmd|powershell|spotify|armoury|explorer|settings"}.
- "open_browser_search": args = {"query": "<строка_поиска>"}.
- "system_volume": args = {"level": 0..100}.
- "screenshot": args = {}.
- "smalltalk": args = {"text": "<строка>"}.
- "open_website": args = {"url": "<домен или URL>"}.
- "minimize_app": args = {"alias": "chrome|spotify|telegram|discord|steam|code|explorer|armoury|settings"}.
- "close_app": args = {"alias": "chrome|spotify|telegram|discord|steam|code|explorer|armoury|settings"}.
- "system_shutdown": args = {}.
- "system_restart": args = {}.
- "system_sleep": args = {}.
- "system_lock": args = {}.
- "wifi_toggle": args = {}.
- "brightness_set": args = {"level": 0..100}.
- "clipboard_copy": args = {"text": "<строка>"}.
- "clipboard_paste": args = {}.

Ответ содержит поля: intent, args, speak.
Примеры:
{"intent":"open_app","args":{"alias":"notepad"},"speak":"Открываю блокнот."}
{"intent":"system_shutdown","args":{},"speak":"Выключаю систему."}
{"intent":"brightness_set","args":{"level":50},"speak":"Устанавливаю яркость 50%."}
{"intent":"wifi_toggle","args":{},"speak":"Переключаю Wi-Fi."}
{"intent":"clipboard_copy","args":{"text":"Привет мир"},"speak":"Копирую в буфер."}
"""

_CFG_MTIME: float = 0.0
_CFG_CACHE: dict = {}

_ollama_client = OllamaClient()


def _get_ollama_model() -> str:
    env = os.environ.get("OLLAMA_MODEL")
    if env:
        return env
    cfg = load_config_cached()
    m = cfg.get("ollama_model")
    return str(m) if m else "gemma3:12b"


def load_config_cached() -> dict:
    global _CFG_MTIME, _CFG_CACHE
    try:
        st = _CONFIG_PATH.stat()
        if st.st_mtime != _CFG_MTIME:
            with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                _CFG_CACHE = json.load(f)
            _CFG_MTIME = st.st_mtime
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Не удалось загрузить конфиг: %s", exc)
    return _CFG_CACHE or {}


def _coerce_and_validate(obj: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    intent = obj.get("intent")
    args = obj.get("args", {})
    speak = obj.get("speak")
    if not isinstance(intent, str) or intent not in ALLOWED_INTENTS:
        return None
    if not isinstance(args, dict):
        args = {}

    if intent == "open_app":
        alias = args.get("alias")
        if not isinstance(alias, str) or not alias.strip():
            return None
        args["alias"] = _normalize_app_name(alias)

    elif intent == "system_volume":
        lvl = args.get("level")
        try:
            lvl = int(lvl)
        except (TypeError, ValueError):
            return None
        args["level"] = max(0, min(100, lvl))

    elif intent == "open_browser_search":
        q = args.get("query")
        if not isinstance(q, str) or not q.strip():
            return None
        args["query"] = q.strip()

    elif intent == "open_website":
        url = args.get("url")
        if not isinstance(url, str) or not url.strip():
            return None
        args["url"] = url.strip()

    elif intent == "screenshot":
        args = {}

    elif intent == "smalltalk":
        text = args.get("text")
        if not isinstance(text, str) or not text.strip():
            if isinstance(speak, str) and speak.strip():
                args["text"] = speak.strip()
            else:
                args["text"] = "Хорошо."

    elif intent == "brightness_set":
        lvl = args.get("level")
        try:
            lvl = int(lvl)
        except (TypeError, ValueError):
            return None
        args["level"] = max(0, min(100, lvl))

    if speak is not None and not isinstance(speak, str):
        speak = str(speak)
    if speak is not None:
        speak = speak.strip()
    obj["intent"], obj["args"], obj["speak"] = intent, args, speak
    return obj


def _custom_rules(phrase: str) -> dict | None:
    cfg = load_config_cached()
    customs = cfg.get("custom_commands") or []
    if not isinstance(customs, list):
        return None

    text_orig = (phrase or "").strip()
    text_norm = _clean(text_orig)

    for rule in customs:
        try:
            mtype = (rule.get("match_type") or "equals").lower()
            patt = (rule.get("pattern") or "").strip()
            intent = rule.get("intent")
            args = rule.get("args") or {}
            speak = rule.get("speak")

            if not intent or intent not in ALLOWED_INTENTS:
                continue

            matched = False
            if mtype == "equals":
                matched = text_norm == _clean(patt)
            elif mtype == "startswith":
                matched = text_norm.startswith(_clean(patt))
            elif mtype == "contains":
                matched = _clean(patt) in text_norm
            elif mtype == "regex":
                try:
                    compiled = re.compile(patt, re.IGNORECASE)
                    matched = bool(compiled.search(text_orig))
                except re.error as exc:
                    logger.warning("Неверный regex-паттерн '%s': %s", patt, exc)
                    matched = False

            if matched:
                obj = {"intent": intent, "args": args, "speak": speak}
                coerced = _coerce_and_validate(obj)
                if coerced:
                    return _wrap(coerced, 0.95, phrase)
        except Exception as exc:
            logger.warning("Ошибка обработки правила: %s", exc)
            continue
    return None


_SEARCH_VERB_RE = re.compile(
    r"\b("
    r"загугл(?:и|ите|ить|ю)|"
    r"найд(?:и|ите|у)|"
    r"поиск(?:ай|айте|ать)"
    r")\b\s+(.+)",
    re.IGNORECASE,
)

_OPEN_VERB_RE = re.compile(
    r"\b("
    r"открой|откройте|открыть|открыл|запусти|запустите|запустить|включи|включите|включить|включил|включила"
    r")\b\s+([a-zA-Zа-яА-Я0-9\.\-\s_]+)$",
    re.IGNORECASE,
)

_SMART_SEARCH_PATTERNS = [
    re.compile(r"\b(найди|ищи|поищи|найти)\s+(.+?)(?:\s+для\s+(.+))?$"),
    re.compile(r"\b(умный\s+поиск|ии\s+поиск|ай\s+поиск)\s+(.+)$"),
    re.compile(r"\b(что\s+такое|что\s+это)\s+(.+)$"),
    re.compile(r"\b(покажи|найди)\s+(.+?)(?:\s+программу|приложение)?$"),
]


def _rules_nlu(phrase: str) -> dict:
    orig = (phrase or "").strip()
    if not orig:
        return _wrap({"intent": "smalltalk", "args": {"text": ""}, "speak": "Я тебя не расслышал."}, 0.5, "")

    m0 = _SEARCH_VERB_RE.search(orig)
    if m0:
        query = m0.group(2).strip()
        if query:
            return _wrap({"intent": "open_browser_search", "args": {"query": query}, "speak": "Открываю поиск."}, 0.9, orig)

    lem = _lemmatize_line(orig)

    m2 = re.search(r"открыть .* браузер .* (?:и|и там)\s+(.+)", lem)
    if m2:
        query = m2.group(1).strip()
        if query:
            return _wrap({"intent": "open_browser_search", "args": {"query": query}, "speak": "Ищу в браузере."}, 0.9, orig)

    for pattern in _SMART_SEARCH_PATTERNS:
        m = pattern.search(lem)
        if m:
            app_name = m.group(2).strip() if len(m.groups()) >= 2 else m.group(1).strip()
            context = m.group(3).strip() if len(m.groups()) >= 3 and m.group(3) else ""
            if app_name:
                return _wrap({
                    "intent": "smart_search",
                    "args": {"app_name": app_name, "context": context},
                    "speak": f"Ищу {app_name}...",
                }, 0.9, orig)

    m5 = re.search(r"\b(свернуть|минимизировать|убрать\s+в\s+трей|спрятать|скрой|сокрой)\s+(.+)", lem)
    if m5:
        alias = _normalize_app_name(m5.group(2).strip())
        return _wrap({"intent": "minimize_app", "args": {"alias": alias}, "speak": f"Сворачиваю {alias}."}, 0.9, orig)

    m6 = re.search(r"\b(закрыть|выключить|завершить)\s+(.+)", lem)
    if m6:
        alias = _normalize_app_name(m6.group(2).strip())
        return _wrap({"intent": "close_app", "args": {"alias": alias}, "speak": f"Закрываю {alias}."}, 0.9, orig)

    m3 = _OPEN_VERB_RE.search(orig)
    if m3:
        alias_raw = m3.group(2).strip()
        alias = _normalize_app_name(alias_raw)
        speak_name = alias if alias else alias_raw
        return _wrap({"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {speak_name}."}, 0.9, orig)

    if re.fullmatch(r"[a-zA-Zа-яА-Я0-9\.\-\s_]+", orig) and len(orig) <= 30:
        if not re.search(r"\b(открой|закрой|сверни|открыть|закрыть|свернуть|запусти|включи)\b", orig, re.IGNORECASE):
            alias = _normalize_app_name(orig)
            if alias != _clean(orig):
                return _wrap({"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {orig}."}, 0.9, orig)

    m4 = re.search(r"(установить|поставить)\s+громкость\s+(\d{1,3})", lem)
    if m4:
        m4o = re.search(r"\b(\d{1,3})\b", orig)
        level = int(m4o.group(1)) if m4o else int(m4.group(2))
        return _wrap({"intent": "system_volume", "args": {"level": max(0, min(100, level))}, "speak": f"Громкость {level}%."}, 0.9, orig)

    if re.search(r"\b(сделать\s+скриншот|сделать\s+скрин)\b", lem):
        return _wrap({"intent": "screenshot", "args": {}, "speak": "Скриншот готов."}, 0.9, orig)

    if re.search(r"\b(выключить\s+компьютер|выключить\s+систему|завершить\s+работу|выключить\s+пк|выключить\s+комп)\b", lem):
        return _wrap({"intent": "system_shutdown", "args": {}, "speak": "Выключаю систему."}, 0.9, orig)

    if re.search(r"\b(перезагрузить\s+компьютер|перезагрузить\s+систему|рестарт)\b", lem):
        return _wrap({"intent": "system_restart", "args": {}, "speak": "Перезагружаю систему."}, 0.9, orig)

    if re.search(r"\b(уснуть|спать|режим\s+сна|сон)\b", lem):
        return _wrap({"intent": "system_sleep", "args": {}, "speak": "Перевожу в режим сна."}, 0.9, orig)

    if re.search(r"\b(заблокировать\s+компьютер|заблокировать\s+систему|блокировка)\b", lem):
        return _wrap({"intent": "system_lock", "args": {}, "speak": "Блокирую систему."}, 0.9, orig)

    if re.search(r"\b(включить\s+вайфай|выключить\s+вайфай|переключить\s+вайфай)\b", lem):
        return _wrap({"intent": "wifi_toggle", "args": {}, "speak": "Переключаю Wi-Fi."}, 0.9, orig)

    m7 = re.search(r"\b(яркость|освещение)\s+(\d{1,3})\b", lem)
    if m7:
        level = max(0, min(100, int(m7.group(2))))
        return _wrap({"intent": "brightness_set", "args": {"level": level}, "speak": f"Яркость {level}%."}, 0.9, orig)

    if re.search(r"\b(скопировать\s+в\s+буфер|копировать\s+в\s+буфер)\b", lem):
        text = orig.replace("скопировать в буфер", "").replace("копировать в буфер", "").strip()
        if text:
            return _wrap({"intent": "clipboard_copy", "args": {"text": text}, "speak": "Копирую в буфер."}, 0.9, orig)

    if re.search(r"\b(вставить\s+из\s+буфера|показать\s+буфер)\b", lem):
        return _wrap({"intent": "clipboard_paste", "args": {}, "speak": "Содержимое буфера."}, 0.9, orig)

    if re.search(r"\b(да|подтверждаю|согласен|выполняй|делай|ок|хорошо|подтвердить)\b", lem):
        return _wrap({"intent": "confirm_action", "args": {}, "speak": "Подтверждаю."}, 0.9, orig)

    if re.search(r"\b(нет|отмена|отменить|не надо|не нужно|стоп|останови|откажись)\b", lem):
        return _wrap({"intent": "cancel_action", "args": {}, "speak": "Отменяю."}, 0.9, orig)

    if re.search(r"\b(статус|статус системы|покажи статус|информация о системе)\b", lem):
        return _wrap({"intent": "system_status", "args": {}, "speak": "Показываю статус."}, 0.9, orig)

    if re.search(r"\b(покажи команды|список команд|мои команды|команды)\b", lem):
        return _wrap({"intent": "list_commands", "args": {}, "speak": "Список команд."}, 0.9, orig)

    if re.search(r"\b(удали команду|удалить команду|удалить)\b", lem):
        return _wrap({"intent": "delete_command", "args": {}, "speak": "Удаляю команду."}, 0.9, orig)

    if re.search(r"\b(обучи команду|создай команду|новая команда|добавь команду)\b", lem):
        return _wrap({"intent": "teach_command", "args": {}, "speak": "Создаю команду."}, 0.9, orig)

    return _wrap(
        {"intent": "smalltalk", "args": {"text": orig}, "speak": "Пока умею: поиск, запуск приложений, громкость, скриншот, управление системой, Wi-Fi, яркость и буфер обмена."},
        0.6,
        orig,
    )


def _ollama_generate(user_text: str) -> dict | None:
    raw = _ollama_client.ask(user_text, _get_ollama_model(), PROMPT_SYSTEM)
    if raw:
        coerced = _coerce_and_validate(raw)
        if coerced:
            return _wrap(coerced, 0.7, user_text)
    return None


def nlu_rules(phrase: str) -> dict:
    phrase = (phrase or "").strip()

    custom = _custom_rules(phrase)
    if custom:
        return custom

    if USE_RULES_FIRST:
        rule_cmd = _rules_nlu(phrase)
        if rule_cmd.get("intent") != "smalltalk":
            return rule_cmd

    if OLLAMA_ENABLED:
        llm_cmd = _ollama_generate(phrase)
        if isinstance(llm_cmd, dict) and llm_cmd.get("intent") in ALLOWED_INTENTS:
            return llm_cmd

    if not USE_RULES_FIRST:
        return _rules_nlu(phrase)

    return _wrap(
        {"intent": "smalltalk", "args": {"text": phrase}, "speak": "Пока умею: поиск, запуск приложений, громкость и скриншот."},
        0.5,
        phrase,
    )
