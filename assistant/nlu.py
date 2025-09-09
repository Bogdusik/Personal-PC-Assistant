# assistant/nlu.py
# NLU: custom_commands (config.json) -> быстрые правила -> LLM (Ollama) -> fallback

from __future__ import annotations
import re
import json
import time
import os
import requests
from typing import Any, Dict

# ===================== Настройки =====================

USE_RULES_FIRST = True

# Ollama
def _get_ollama_model() -> str:
    # 1) ENV
    env = os.environ.get("OLLAMA_MODEL")
    if env:
        return env
    # 2) config.json
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            m = cfg.get("ollama_model")
            if m:
                return str(m)
    except Exception:
        pass
    # 3) дефолт
    return "gemma3:12b"

OLLAMA_ENABLED = True
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = _get_ollama_model()
OLLAMA_TIMEOUT = 35
OLLAMA_RETRIES = 2
OLLAMA_RETRY_BACKOFF = 0.8

ALLOWED_INTENTS = {
    "open_app",
    "open_browser_search",
    "system_volume",
    "screenshot",
    "smalltalk",
    "open_website",  # опционально
}

PROMPT_SYSTEM = """Ты — локальный голосовой ассистент на ПК.
Верни ТОЛЬКО один JSON-объект без пояснений/разметки.

Допустимые intents:
- "open_app": args = {"alias": "chrome|notepad|telegram|discord|steam|code|calc|cmd|powershell"}.
  "браузер" → "chrome"; "блокнот/заметки/ноутпад" → "notepad".
- "open_browser_search": args = {"query": "<строка_поиска>"}.
- "system_volume": args = {"level": 0..100}.
- "screenshot": args = {}.
- "smalltalk": args = {"text": "<строка>"}.
- "open_website": args = {"url": "<домен или URL>"}.

Ответ содержит поля: intent, args, speak.
Примеры:
{"intent":"open_app","args":{"alias":"notepad"},"speak":"Открываю блокнот."}
{"intent":"open_browser_search","args":{"query":"новости windows 12"},"speak":"Открываю поиск."}
{"intent":"system_volume","args":{"level":20},"speak":"Громкость 20%."}
{"intent":"screenshot","args":{},"speak":"Скриншот готов."}
{"intent":"smalltalk","args":{"text":"Привет!"},"speak":"Привет!"}
"""

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "args": {"type": "object"},
        "speak": {"type": "string"},
        "confidence": {"type": "number"},
        "normalized_text": {"type": "string"}
    },
    "required": ["intent", "args"]
}

# ===================== Кешируем config.json =====================

_CFG_MTIME = 0.0
_CFG_CACHE = {}

def load_config_cached() -> dict:
    """Ленивая подгрузка config.json с кешем по mtime."""
    global _CFG_MTIME, _CFG_CACHE
    try:
        st = os.stat("config.json")
        if st.st_mtime != _CFG_MTIME:
            with open("config.json", "r", encoding="utf-8") as f:
                _CFG_CACHE = json.load(f)
            _CFG_MTIME = st.st_mtime
    except Exception:
        pass
    return _CFG_CACHE or {}

# ===================== Морфология (опц.) =====================

try:
    import pymorphy2
    _MORPH = pymorphy2.MorphAnalyzer()
except Exception:
    _MORPH = None

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")
def _lemmatize_line(s: str) -> str:
    t = _clean(s)
    if not _MORPH:
        return t
    lemmas = []
    for w in _TOKEN_RE.findall(t):
        try:
            lemmas.append(_MORPH.parse(w)[0].normal_form)
        except Exception:
            lemmas.append(w.lower())
    return " ".join(lemmas)

# ===================== Утилиты =====================

_CJK_RE = re.compile(r"[\u3400-\u9FFF\uF900-\uFAFF]")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.S)

def _has_too_much_cjk(s: str, max_ratio: float = 0.15) -> bool:
    if not s:
        return False
    cjk = len(_CJK_RE.findall(s))
    return (cjk / max(1, len(s))) > max_ratio

def _extract_json(s: str) -> dict | None:
    if not s:
        return None
    m = _JSON_OBJECT_RE.search(s.strip())
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def _clean(s: str) -> str:
    t = s.lower()
    t = t.replace("ё", "е")
    t = re.sub(r"[\"'’`.,;:!?()\[\]{}]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _wrap(cmd: dict, conf: float, phrase: str) -> dict:
    cmd = dict(cmd)
    cmd.setdefault("speak", None)
    cmd["confidence"] = max(0.0, min(1.0, float(conf)))
    cmd["normalized_text"] = phrase.strip()
    return cmd

def _normalize_app_name(name: str) -> str:
    t = _clean(name)
    if "google chrome" in t or "гугл хром" in t or "хром" in t or "chrome" in t or "браузер" in t:
        return "chrome"
    if "visual studio code" in t or "vs code" in t or "vscode" in t or "вс код" in t or t == "код":
        return "code"
    if "телеграмм" in t or "телеграм" in t or "tg" in t or "тг" in t or "telegram" in t:
        return "telegram"
    if "дискорд" in t or "discord" in t:
        return "discord"
    if "стим" in t or "steam" in t:
        return "steam"
    if "калькулятор" in t or "calc" in t or "calculator" in t:
        return "calc"
    if t in ("блокнот", "заметки", "ноутпад", "notepad"):
        return "notepad"
    if t in ("командная строка", "cmd", "консоль"):
        return "cmd"
    if "powershell" in t or "пауршелл" in t:
        return "powershell"

    NAME_ALIASES = {
        "хром": "chrome", "chrome": "chrome", "гугл хром": "chrome", "браузер": "chrome",
        "блокнот": "notepad", "заметки": "notepad", "ноутпад": "notepad", "notepad": "notepad",
        "vs code": "code", "visual studio code": "code", "vscode": "code", "вс код": "code", "code": "code", "код": "code",
        "телеграм": "telegram", "телеграмм": "telegram", "telegram": "telegram", "tg": "telegram", "тг": "telegram",
        "дискорд": "discord", "discord": "discord",
        "стим": "steam", "steam": "steam",
        "калькулятор": "calc", "calc": "calc", "calculator": "calc",
        "cmd": "cmd", "командная строка": "cmd",
        "powershell": "powershell", "пауршелл": "powershell",
    }
    return NAME_ALIASES.get(t, t)

def _coerce_and_validate(obj: Dict[str, Any]) -> Dict[str, Any] | None:
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
        except Exception:
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

    if speak is not None and not isinstance(speak, str):
        speak = str(speak)
    if speak is not None:
        speak = speak.strip()
    obj["intent"], obj["args"], obj["speak"] = intent, args, speak
    return obj

# ===================== Custom commands =====================

def _custom_rules(phrase: str) -> dict | None:
    """equals | startswith | contains | regex — из config.json/custom_commands"""
    cfg = load_config_cached()
    customs = cfg.get("custom_commands") or []
    if not isinstance(customs, list):
        return None

    text_orig = (phrase or "").strip()
    text_norm = _clean(text_orig)

    for rule in customs:
        try:
            mtype  = (rule.get("match_type") or "equals").lower()
            patt   = (rule.get("pattern") or "").strip()
            intent = rule.get("intent")
            args   = rule.get("args") or {}
            speak  = rule.get("speak")

            if not intent or intent not in ALLOWED_INTENTS:
                continue

            matched = False
            if mtype == "equals":
                matched = (text_norm == _clean(patt))
            elif mtype == "startswith":
                matched = text_norm.startswith(_clean(patt))
            elif mtype == "contains":
                matched = (_clean(patt) in text_norm)
            elif mtype == "regex":
                try:
                    if re.search(patt, text_orig, re.IGNORECASE):
                        matched = True
                except Exception:
                    matched = False

            if matched:
                obj = {"intent": intent, "args": args, "speak": speak}
                coerced = _coerce_and_validate(obj)
                if coerced:
                    return _wrap(coerced, 0.95, phrase)
        except Exception:
            continue
    return None

# ===================== Правила =====================

_SEARCH_VERB_RE = re.compile(
    r"\b("
    r"загугл(?:и|ите|ить|ю)|"
    r"найд(?:и|ите|у)|"
    r"поиск(?:ай|айте|ать)"
    r")\b\s+(.+)", re.IGNORECASE
)

_OPEN_VERB_RE = re.compile(
    r"\b("
    r"открой|откройте|открыть|открыл|запусти|запустите|запустить|включи|включите|включить"
    r")\b\s+([a-zA-Zа-яА-Я0-9\.\-\s_]+)$", re.IGNORECASE
)

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

    m3 = _OPEN_VERB_RE.search(orig)
    if m3:
        alias_raw = m3.group(2).strip()
        alias = _normalize_app_name(alias_raw)
        return _wrap({"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {alias_raw}."}, 0.9, orig)

    if re.fullmatch(r"[a-zA-Zа-яА-Я0-9\.\-\s_]+", orig) and len(orig) <= 30:
        alias = _normalize_app_name(orig)
        if alias != _clean(orig):
            return _wrap({"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {orig}."}, 0.9, orig)

    m4 = re.search(r"(установить|поставить)\s+громкость\s+(\d{1,3})", _lemmatize_line(orig))
    if m4:
        m4o = re.search(r"\b(\d{1,3})\b", orig)
        level = int(m4o.group(1)) if m4o else int(m4.group(2))
        level = max(0, min(100, level))
        return _wrap({"intent": "system_volume", "args": {"level": level}, "speak": f"Громкость {level}%."}, 0.9, orig)

    if re.search(r"\b(сделать\s+скриншот|сделать\s+скрин)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "screenshot", "args": {}, "speak": "Скриншот готов."}, 0.9, orig)

    return _wrap({"intent": "smalltalk", "args": {"text": orig}, "speak": "Пока умею: поиск, запуск приложений, громкость и скриншот."}, 0.6, orig)

# ===================== LLM (Ollama) =====================

def _ollama_once(user_text: str) -> dict | None:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{PROMPT_SYSTEM}\nФраза пользователя: {user_text}\nJSON:",
        "stream": True,
        "temperature": 0.0,
        "format": "json",
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT, stream=True)
        r.raise_for_status()
    except Exception:
        return None

    buf = ""
    try:
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            part = data.get("response", "")
            buf += part
            if data.get("done"):
                break
    except Exception:
        return None

    if _has_too_much_cjk(buf):
        return None

    obj = _extract_json(buf)
    if not obj:
        return None
    obj = _coerce_and_validate(obj)
    if not obj:
        return None
    return _wrap(obj, 0.7, user_text)

def _ollama_generate(user_text: str) -> dict | None:
    for i in range(OLLAMA_RETRIES + 1):
        res = _ollama_once(user_text)
        if res is not None:
            return res
        if i < OLLAMA_RETRIES:
            time.sleep((1 + i) * OLLAMA_RETRY_BACKOFF)
    return None

# ===================== Публичная точка входа =====================

def nlu_rules(phrase: str) -> dict:
    phrase = (phrase or "").strip()

    # 0) пользовательские правила (из config.json)
    custom = _custom_rules(phrase)
    if custom:
        return custom

    # 1) быстрые правила
    if USE_RULES_FIRST:
        rule_cmd = _rules_nlu(phrase)
        if rule_cmd.get("intent") != "smalltalk":
            return rule_cmd

    # 2) LLM
    if OLLAMA_ENABLED:
        llm_cmd = _ollama_generate(phrase)
        if isinstance(llm_cmd, dict) and llm_cmd.get("intent") in ALLOWED_INTENTS:
            return llm_cmd

    # 3) fallback
    if not USE_RULES_FIRST:
        return _rules_nlu(phrase)
    return _wrap({"intent": "smalltalk", "args": {"text": phrase}, "speak": "Пока умею: поиск, запуск приложений, громкость и скриншот."}, 0.5, phrase)
