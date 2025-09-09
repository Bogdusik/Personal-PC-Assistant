# assistant/nlu.py
import re

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "args": {"type": "object"},
        "speak": {"type": "string"}
    },
    "required": ["intent", "args"]
}

def _clean(s: str) -> str:
    t = s.lower()
    t = t.replace("ё", "е")
    t = re.sub(r"[\"'’`.,;:!?()\[\]{}]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

# более агрессивная нормализация имён под алиасы
def _normalize_app_name(name: str) -> str:
    t = _clean(name)

    # быстрые проверки по подстрокам (ловим сложные фразы)
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

    # таблица синонимов (на случай чистых однословных названий)
    NAME_ALIASES = {
        # браузеры
        "хром": "chrome", "chrome": "chrome", "гугл хром": "chrome", "браузер": "chrome",
        # редакторы
        "блокнот": "notepad", "заметки": "notepad", "ноутпад": "notepad", "notepad": "notepad",
        "vs code": "code", "visual studio code": "code", "vscode": "code", "вс код": "code", "code": "code", "код": "code",
        # мессенджеры
        "телеграм": "telegram", "телеграмм": "telegram", "telegram": "telegram", "tg": "telegram", "тг": "telegram",
        "дискорд": "discord", "discord": "discord",
        # игры
        "стим": "steam", "steam": "steam",
        # системные
        "калькулятор": "calc", "calc": "calc", "calculator": "calc",
        "cmd": "cmd", "командная строка": "cmd",
        "powershell": "powershell", "пауршелл": "powershell",
    }
    return NAME_ALIASES.get(t, t)

def nlu_rules(phrase: str) -> dict:
    t = _clean(phrase)

    # Поиск
    m = re.search(r"(загугли|найди|поиск(ай)?)\s+(.+)", t)
    if m:
        query = m.group(3).strip()
        return {"intent": "open_browser_search", "args": {"query": query}, "speak": "Открываю поиск."}

    m2 = re.search(r"открой .*браузер.*(?:и|и\s+там)\s+(.+)", t)
    if m2:
        query = m2.group(1).strip()
        return {"intent": "open_browser_search", "args": {"query": query}, "speak": "Ищу в браузере."}

    # Открыть приложение (разрешим свободную форму с/без глагола)
    m3 = re.search(r"(?:открой|запусти|включи)\s+([a-zA-Zа-яА-Я0-9\.\-\s_]+)$", t)
    if m3:
        alias_raw = m3.group(1).strip()
        alias = _normalize_app_name(alias_raw)
        return {"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {alias_raw}."}

    # Если сказали только имя приложения (без глагола): "хром", "телеграмм", "блокнот"
    if re.fullmatch(r"[a-zA-Zа-яА-Я0-9\.\-\s_]+", t) and len(t) <= 30:
        alias = _normalize_app_name(t)
        if alias != t:  # нашли нормализацию к известному алиасу
            return {"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {t}."}

    # Громкость
    m4 = re.search(r"(установи|поставь)\s+громкость\s+(\d{1,3})", t)
    if m4:
        level = int(m4.group(2))
        return {"intent": "system_volume", "args": {"level": level}, "speak": f"Громкость {max(0, min(100, level))}%."}

    # Скриншот
    if re.search(r"\b(сделай\s+скрин(шот)?)\b", t):
        return {"intent": "screenshot", "args": {}, "speak": "Скриншот готов."}

    return {"intent": "smalltalk", "args": {"text": phrase}, "speak": "Пока умею: поиск, запуск приложений, громкость и скриншот."}
