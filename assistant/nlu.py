from __future__ import annotations
import re, json, time, os, requests
from typing import Any, Dict, Optional, List

USE_RULES_FIRST = True

def _get_ollama_model() -> str:
    env = os.environ.get("OLLAMA_MODEL")
    if env:
        return env
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            m = cfg.get("ollama_model")
            if m:
                return str(m)
    except Exception:
        pass
    return "gemma3:12b"

OLLAMA_ENABLED = True
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = _get_ollama_model()
OLLAMA_TIMEOUT = 35
OLLAMA_RETRIES = 2
OLLAMA_RETRY_BACKOFF = 0.8

ALLOWED_INTENTS = {
    "open_app", "open_browser_search", "system_volume", "screenshot", "smalltalk",
    "open_website", "minimize_app", "close_app", "system_shutdown", "system_restart",
    "system_sleep", "system_lock", "wifi_toggle", "brightness_set", "clipboard_copy", "clipboard_paste",
    "confirm_action", "cancel_action", "system_status", "list_commands", "delete_command", "teach_command",
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


_CFG_MTIME = 0.0
_CFG_CACHE = {}

def load_config_cached() -> dict:
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
    t = re.sub(r"[\"'''`.,;:!?()\[\]{}]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _wrap(cmd: dict, conf: float, phrase: str) -> dict:
    cmd = dict(cmd)
    cmd.setdefault("speak", None)
    cmd["confidence"] = max(0.0, min(1.0, float(conf)))
    cmd["normalized_text"] = phrase.strip()
    return cmd

def _normalize_app_name(name: str) -> str:
    """Нормализует имя приложения с улучшенной обработкой ошибок."""
    try:
        if not name or not isinstance(name, str):
            return ""
            
        t = _clean(name)
        
        # Убираем лишние слова
        t = re.sub(r'\b(открой|открыть|запусти|запустить|включи|включить|мой|мои|мне|для|меня)\b', '', t).strip()
    except Exception as e:
        print(f"⚠️ Ошибка нормализации имени приложения '{name}': {e}")
        return name
    
    # Проводник и файлы
    if any(word in t for word in ["проводник", "файлы", "explorer", "папки"]):
        return "explorer"
    
    # Настройки
    if any(word in t for word in ["параметры", "настройки", "settings", "стройке"]):
        return "settings"
    
    # Музыка и Spotify
    if any(word in t for word in ["музыка", "спотифай", "spotify", "музыкальный"]):
        return "spotify"
    
    # ASUS Armoury
    if any(word in t for word in ["armoury", "asus", "армори"]):
        return "armoury"
    
    # Браузеры
    if any(word in t for word in ["chrome", "хром", "браузер", "гугл", "google"]):
        return "chrome"
    
    # Редакторы кода
    if any(word in t for word in ["code", "код", "vscode", "vs code", "visual studio"]):
        return "code"
    
    # Мессенджеры
    if any(word in t for word in ["telegram", "телеграм", "телеграмм", "tg", "тг"]):
        return "telegram"
    if any(word in t for word in ["discord", "дискорд"]):
        return "discord"
    
    # Игры
    if any(word in t for word in ["steam", "стим", "игры"]):
        return "steam"
    
    # Системные утилиты
    if any(word in t for word in ["калькулятор", "calc", "calculator"]):
        return "calc"
    if any(word in t for word in ["блокнот", "notepad", "заметки", "текст"]):
        return "notepad"
    if any(word in t for word in ["cmd", "консоль", "командная", "терминал"]):
        return "cmd"
    if any(word in t for word in ["powershell", "пауршелл", "пауэршелл"]):
        return "powershell"
    
    # Фото и изображения
    if any(word in t for word in ["фото", "фотографии", "картинки", "изображения", "paint", "краска", "рисование", "редактор"]):
        return "фото редактор"
    
    # Календарь (учитываем частые опечатки ASR)
    if any(word in t for word in [
        "календарь", "calendar", "дата", "события",
        "календарим", "календарик", "колендарь", "колендаль"
    ]):
        return "календарь"
    
    # Почта
    if any(word in t for word in ["почта", "mail", "email", "письма"]):
        return "почта"
    
    # Наушники/аудио
    if any(word in t for word in ["наушники", "наушен", "аудио", "звук", "музыка"]):
        return "spotify"
    
    return t

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

def _custom_rules(phrase: str) -> dict | None:
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

_SEARCH_VERB_RE = re.compile(
    r"\b("
    r"загугл(?:и|ите|ить|ю)|"
    r"найд(?:и|ите|у)|"
    r"поиск(?:ай|айте|ать)"
    r")\b\s+(.+)", re.IGNORECASE
)

_OPEN_VERB_RE = re.compile(
    r"\b("
    r"открой|откройте|открыть|открыл|запусти|запустите|запустить|включи|включите|включить|включил|включила"
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

    # Умный поиск приложений
    smart_search_patterns = [
        r"\b(найди|ищи|поищи|найти)\s+(.+?)(?:\s+для\s+(.+))?$",
        r"\b(умный\s+поиск|ии\s+поиск|ай\s+поиск)\s+(.+)$",
        r"\b(что\s+такое|что\s+это)\s+(.+)$",
        r"\b(покажи|найди)\s+(.+?)(?:\s+программу|приложение)?$"
    ]
    
    for pattern in smart_search_patterns:
        m = re.search(pattern, lem)
        if m:
            app_name = m.group(2).strip() if len(m.groups()) >= 2 else m.group(1).strip()
            context = m.group(3).strip() if len(m.groups()) >= 3 and m.group(3) else ""
            if app_name:
                return _wrap({
                    "intent": "smart_search", 
                    "args": {"app_name": app_name, "context": context}, 
                    "speak": f"Ищу {app_name} с помощью ИИ..."
                }, 0.9, orig)

    m5 = re.search(
        r"\b(свернуть|минимизировать|убрать\s+в\s+трей|спрятать|скрой|сокрой)\s+(.+)",
        _lemmatize_line(orig),
    )
    if m5:
        app_name = m5.group(2).strip()
        alias = _normalize_app_name(app_name)
        return _wrap({"intent": "minimize_app", "args": {"alias": alias}, "speak": f"Сворачиваю {app_name}."}, 0.9, orig)

    m6 = re.search(r"\b(закрыть|выключить|завершить)\s+(.+)", _lemmatize_line(orig))
    if m6:
        app_name = m6.group(2).strip()
        alias = _normalize_app_name(app_name)
        return _wrap({"intent": "close_app", "args": {"alias": alias}, "speak": f"Закрываю {app_name}."}, 0.9, orig)

    m3 = _OPEN_VERB_RE.search(orig)
    if m3:
        alias_raw = m3.group(2).strip()
        alias = _normalize_app_name(alias_raw)
        # В ответе используем нормализованное имя, чтобы не повторять
        # кривое распознавание типа "Откроекалендарь" или "колендаль"
        speak_name = alias if alias else alias_raw
        return _wrap(
            {"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {speak_name}."},
            0.9,
            orig,
        )

    if re.fullmatch(r"[a-zA-Zа-яА-Я0-9\.\-\s_]+", orig) and len(orig) <= 30:
        if not re.search(r"\b(открой|закрой|сверни|открыть|закрыть|свернуть|запусти|включи)\b", orig, re.IGNORECASE):
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

    if re.search(r"\b(выключить\s+компьютер|выключить\s+систему|завершить\s+работу|выключить\s+пк|выключить\s+комп)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "system_shutdown", "args": {}, "speak": "Выключаю систему."}, 0.9, orig)

    if re.search(r"\b(перезагрузить\s+компьютер|перезагрузить\s+систему|рестарт)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "system_restart", "args": {}, "speak": "Перезагружаю систему."}, 0.9, orig)

    if re.search(r"\b(уснуть|спать|режим\s+сна|сон)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "system_sleep", "args": {}, "speak": "Перевожу в режим сна."}, 0.9, orig)

    if re.search(r"\b(заблокировать\s+компьютер|заблокировать\s+систему|блокировка)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "system_lock", "args": {}, "speak": "Блокирую систему."}, 0.9, orig)

    if re.search(r"\b(включить\s+вайфай|выключить\s+вайфай|переключить\s+вайфай)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "wifi_toggle", "args": {}, "speak": "Переключаю Wi-Fi."}, 0.9, orig)

    m7 = re.search(r"\b(яркость|освещение)\s+(\d{1,3})\b", _lemmatize_line(orig))
    if m7:
        level = int(m7.group(2))
        level = max(0, min(100, level))
        return _wrap({"intent": "brightness_set", "args": {"level": level}, "speak": f"Устанавливаю яркость {level}%."}, 0.9, orig)

    if re.search(r"\b(скопировать\s+в\s+буфер|копировать\s+в\s+буфер)\b", _lemmatize_line(orig)):
        text = orig.replace("скопировать в буфер", "").replace("копировать в буфер", "").strip()
        if text:
            return _wrap({"intent": "clipboard_copy", "args": {"text": text}, "speak": "Копирую в буфер."}, 0.9, orig)

    if re.search(r"\b(вставить\s+из\s+буфера|показать\s+буфер)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "clipboard_paste", "args": {}, "speak": "Показываю содержимое буфера."}, 0.9, orig)

    # Команды подтверждения и отмены
    if re.search(r"\b(да|подтверждаю|согласен|выполняй|делай|ок|хорошо|подтвердить)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "confirm_action", "args": {}, "speak": "Подтверждаю действие."}, 0.9, orig)

    if re.search(r"\b(нет|отмена|отменить|не надо|не нужно|стоп|останови|откажись)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "cancel_action", "args": {}, "speak": "Отменяю действие."}, 0.9, orig)

    # Команды управления системой
    if re.search(r"\b(статус|статус системы|покажи статус|информация о системе)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "system_status", "args": {}, "speak": "Показываю статус системы."}, 0.9, orig)

    if re.search(r"\b(покажи команды|список команд|мои команды|команды)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "list_commands", "args": {}, "speak": "Показываю список команд."}, 0.9, orig)

    if re.search(r"\b(удали команду|удалить команду|удалить)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "delete_command", "args": {}, "speak": "Удаляю команду."}, 0.9, orig)

    if re.search(r"\b(обучи команду|создай команду|новая команда|добавь команду)\b", _lemmatize_line(orig)):
        return _wrap({"intent": "teach_command", "args": {}, "speak": "Создаю новую команду."}, 0.9, orig)

    return _wrap({"intent": "smalltalk", "args": {"text": orig}, "speak": "Пока умею: поиск, запуск приложений, громкость, скриншот, сворачивание, закрытие, управление системой, Wi-Fi, яркость и буфер обмена."}, 0.6, orig)

def _ollama_generate(user_text: str) -> dict | None:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{PROMPT_SYSTEM}\nФраза пользователя: {user_text}\nJSON:",
        "stream": True,
        "temperature": 0.0,
        "format": "json",
    }
    for i in range(OLLAMA_RETRIES + 1):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT, stream=True)
            r.raise_for_status()
            buf = ""
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    buf += data.get("response", "")
                    if data.get("done"):
                        break
                except Exception:
                    continue
            
            if _has_too_much_cjk(buf):
                continue
            
            obj = _extract_json(buf)
            if obj:
                obj = _coerce_and_validate(obj)
                if obj:
                    return _wrap(obj, 0.7, user_text)
        except Exception:
            pass
        if i < OLLAMA_RETRIES:
            time.sleep((1 + i) * OLLAMA_RETRY_BACKOFF)
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
    return _wrap({"intent": "smalltalk", "args": {"text": phrase}, "speak": "Пока умею: поиск, запуск приложений, громкость и скриншот."}, 0.5, phrase)