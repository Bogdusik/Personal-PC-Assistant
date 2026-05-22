from __future__ import annotations

import logging
import re

try:
    import pymorphy2
    _MORPH = pymorphy2.MorphAnalyzer()
except ImportError:
    _MORPH = None
    logging.warning("pymorphy2 не установлен — лемматизация отключена")

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")
_CJK_RE = re.compile(r"[㐀-鿿豈-﫿]")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.S)


def _clean(s: str) -> str:
    t = s.lower()
    t = t.replace("ё", "е")
    t = re.sub(r"[\"'''`.,;:!?()\[\]{}]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _lemmatize_line(s: str) -> str:
    t = _clean(s)
    if not _MORPH:
        return t
    lemmas = []
    for w in _TOKEN_RE.findall(t):
        try:
            lemmas.append(_MORPH.parse(w)[0].normal_form)
        except (AttributeError, IndexError):
            lemmas.append(w.lower())
    return " ".join(lemmas)


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
        import json
        return json.loads(m.group(0))
    except (ValueError, json.JSONDecodeError):
        return None


def _wrap(cmd: dict, conf: float, phrase: str) -> dict:
    cmd = dict(cmd)
    cmd.setdefault("speak", None)
    cmd["confidence"] = max(0.0, min(1.0, float(conf)))
    cmd["normalized_text"] = phrase.strip()
    return cmd


def _normalize_app_name(name: str) -> str:
    try:
        if not name or not isinstance(name, str):
            return ""
        t = _clean(name)
        t = re.sub(r'\b(открой|открыть|запусти|запустить|включи|включить|мой|мои|мне|для|меня)\b', '', t).strip()
    except Exception as exc:
        logging.warning("Ошибка нормализации имени '%s': %s", name, exc)
        return name

    if any(word in t for word in ["проводник", "файлы", "explorer", "папки"]):
        return "explorer"
    if any(word in t for word in ["параметры", "настройки", "settings", "стройке"]):
        return "settings"
    if any(word in t for word in ["музыка", "спотифай", "spotify", "музыкальный"]):
        return "spotify"
    if any(word in t for word in ["armoury", "asus", "армори"]):
        return "armoury"
    if any(word in t for word in ["chrome", "хром", "браузер", "гугл", "google"]):
        return "chrome"
    if any(word in t for word in ["code", "код", "vscode", "vs code", "visual studio"]):
        return "code"
    if any(word in t for word in ["telegram", "телеграм", "телеграмм", "tg", "тг"]):
        return "telegram"
    if any(word in t for word in ["discord", "дискорд"]):
        return "discord"
    if any(word in t for word in ["steam", "стим", "игры"]):
        return "steam"
    if any(word in t for word in ["калькулятор", "calc", "calculator"]):
        return "calc"
    if any(word in t for word in ["блокнот", "notepad", "заметки", "текст"]):
        return "notepad"
    if any(word in t for word in ["cmd", "консоль", "командная", "терминал"]):
        return "cmd"
    if any(word in t for word in ["powershell", "пауршелл", "пауэршелл"]):
        return "powershell"
    if any(word in t for word in ["фото", "фотографии", "картинки", "изображения", "paint", "краска", "рисование", "редактор"]):
        return "фото редактор"
    if any(word in t for word in ["календарь", "calendar", "дата", "события", "календарим", "календарик", "колендарь", "колендаль"]):
        return "календарь"
    if any(word in t for word in ["почта", "mail", "email", "письма"]):
        return "почта"
    if any(word in t for word in ["наушники", "наушен", "аудио", "звук"]):
        return "spotify"
    return t
