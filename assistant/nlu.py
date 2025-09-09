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

def nlu_rules(phrase: str) -> dict:
    t = phrase.lower().strip()

    m = re.search(r"(загугли|найди|поиск(ай)?)\s+(.+)", t)
    if m:
        query = m.group(3).strip()
        return {"intent": "open_browser_search", "args": {"query": query}, "speak": "Открываю поиск."}

    m2 = re.search(r"открой .*браузер.*(?:и|и\s+там)\s+(.+)", t)
    if m2:
        query = m2.group(1).strip()
        return {"intent": "open_browser_search", "args": {"query": query}, "speak": "Ищу в браузере."}

    m3 = re.search(r"(открой|запусти|включи)\s+([a-zA-Zа-яА-Я0-9\.\-\s_]+)$", t)
    if m3:
        alias_raw = m3.group(2).strip()
        alias = (alias_raw
                 .replace("гугл хром", "chrome")
                 .replace("хром", "chrome")
                 .replace("блокнот", "notepad")
                 .replace("телеграм", "telegram"))
        return {"intent": "open_app", "args": {"alias": alias}, "speak": f"Открываю {alias_raw}."}

    m4 = re.search(r"(установи|поставь)\s+громкость\s+(\d{1,3})", t)
    if m4:
        level = int(m4.group(2))
        return {"intent": "system_volume", "args": {"level": level}, "speak": f"Громкость {max(0,min(100,level))}%."}

    if re.search(r"\b(сделай\s+скрин(шот)?)\b", t):
        return {"intent": "screenshot", "args": {}, "speak": "Скриншот готов."}

    return {"intent": "smalltalk", "args": {"text": phrase}, "speak": "Пока умею поиск, запуск приложений, громкость и скриншот."}
