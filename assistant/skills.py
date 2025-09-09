# assistant/skills.py
from __future__ import annotations
import os
import glob
import shutil
import difflib
import urllib.parse
import webbrowser
import subprocess
import datetime
import logging
from typing import Tuple, List
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import mss

# Наполняется из main.py: APP_ALIASES.update(cfg["app_aliases"])
APP_ALIASES: dict[str, str] = {}

# -------------------- Вспомогательные --------------------

def _normalize_path(p: str) -> str:
    """Разворачивает %VARS% и нормализует путь."""
    return os.path.normpath(os.path.expandvars(str(p).strip()))

def _exists(p: str | None) -> bool:
    return bool(p) and os.path.exists(p)  # type: ignore[arg-type]

def _best_fuzzy(key: str, candidates: List[str], cutoff: float = 0.8) -> str | None:
    """Находит ближайший ключ среди candidates по difflib (для опечаток)."""
    if not key or not candidates:
        return None
    matches = difflib.get_close_matches(key.lower().strip(), [c.lower() for c in candidates], n=1, cutoff=cutoff)
    return matches[0] if matches else None

# -------------------- Браузерный скилл --------------------

def open_browser_search(query: str) -> None:
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query or "")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Не удалось открыть браузер: {e}")

# -------------------- Резолв пути к приложениям --------------------

def _resolve_app_path(alias: str) -> Tuple[str | None, list[str]]:
    """
    Возвращает (path, extra_args) для запуска приложения.
    Порядок поиска:
      1) config.json (точно) → затем fuzzy по ключам config.json
      2) PATH (shutil.which)
      3) известные пути (включая Discord через Update.exe или app-*)
    """
    a = (alias or "").lower().strip()

    # --- 1) Прямое попадание в config.json
    path_cfg = APP_ALIASES.get(a)
    if path_cfg:
        path_cfg = _normalize_path(path_cfg)
        if _exists(path_cfg):
            if a == "discord" and os.path.basename(path_cfg).lower() == "update.exe":
                return path_cfg, ["--processStart", "Discord.exe"]
            return path_cfg, []

    # --- 1.5) Fuzzy-совпадение по ключам config.json (опечатки: «телеграмм» vs "telegram")
    if APP_ALIASES and a not in APP_ALIASES:
        guess = _best_fuzzy(a, list(APP_ALIASES.keys()), cutoff=0.8)
        if guess:
            path_guess = _normalize_path(APP_ALIASES[guess])
            if _exists(path_guess):
                if guess == "discord" and os.path.basename(path_guess).lower() == "update.exe":
                    return path_guess, ["--processStart", "Discord.exe"]
                return path_guess, []

    # --- 2) Поиск в PATH (notepad, calc и т.п.)
    exe_name = a if a.endswith(".exe") else f"{a}.exe"
    found = shutil.which(a) or shutil.which(exe_name)
    if found and _exists(found):
        return found, []

    # --- 3) Известные пути (Windows)
    known = {
        # системные
        "notepad":      r"C:\Windows\System32\notepad.exe",
        "блокнот":      r"C:\Windows\System32\notepad.exe",
        "calc":         r"C:\Windows\System32\calc.exe",
        "калькулятор":  r"C:\Windows\System32\calc.exe",
        "cmd":          r"C:\Windows\System32\cmd.exe",
        "powershell":   r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",

        # редакторы
        "code":         r"%USERPROFILE%\AppData\Local\Programs\Microsoft VS Code\Code.exe",

        # браузеры
        "chrome":       r"C:\Program Files\Google\Chrome\Application\chrome.exe",

        # мессенджеры
        "telegram":     r"%APPDATA%\Telegram Desktop\Telegram.exe",
        # для discord используем отдельную ветку ниже
        "discord_update": r"%LOCALAPPDATA%\Discord\Update.exe",

        # игры/клиенты
        "steam":        r"C:\Program Files (x86)\Steam\Steam.exe",
    }

    # --- Discord: сначала пробуем Update.exe с аргами, потом прямой Discord.exe в app-*
    if a == "discord":
        upd = _normalize_path(known["discord_update"])
        if _exists(upd):
            return upd, ["--processStart", "Discord.exe"]
        pattern = _normalize_path(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe")
        candidates = sorted(glob.glob(pattern))
        if candidates:
            return candidates[-1], []  # последняя обычно самая свежая

    # --- Остальные из known
    known_path = known.get(a)
    if known_path:
        known_path = _normalize_path(known_path)
        if _exists(known_path):
            return known_path, []

    # --- 3.5) Fuzzy-совпадение по ключам known (если в config.json нет)
    guess2 = _best_fuzzy(a, list(known.keys()), cutoff=0.8)
    if guess2:
        kp = known.get(guess2)
        if kp:
            kp = _normalize_path(kp)
            if _exists(kp):
                if guess2 == "discord_update":  # защита от прямого вызова алиаса
                    return kp, ["--processStart", "Discord.exe"]
                return kp, []

    return None, []

# -------------------- Скиллы --------------------

def open_app(alias: str) -> None:
    path, extra_args = _resolve_app_path(alias)
    if not path:
        print(f"Не знаю приложение: {alias}")
        return
    try:
        # os.startfile хорошо открывает .exe/.lnk, но аргументы не передать → используем его только без extra_args
        lower = path.lower()
        if not extra_args and (lower.endswith(".lnk") or lower.endswith(".exe")):
            os.startfile(path)
            return
        # если нужны аргументы — subprocess (без shell)
        subprocess.Popen([path, *extra_args])
    except Exception as e:
        print(f"Не получилось открыть {alias}: {e}")

def system_volume(level: int) -> None:
    level = max(0, min(100, int(level)))
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        vmin, vmax, _ = volume.GetVolumeRange()
        target = vmin + (vmax - vmin) * (level / 100.0)
        volume.SetMasterVolumeLevel(target, None)
    except Exception as e:
        print(f"Не удалось установить громкость: {e}")

def screenshot() -> None:
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"screenshot_{ts}.png"
        with mss.mss() as sct:
            sct.shot(output=fn)
        print(f"Скриншот: {fn}")
        logging.info(f"Скриншот сохранён: {fn}")
    except Exception as e:
        print(f"Не удалось сделать скриншот: {e}")

def open_website(url: str) -> None:
    """Открывает сайт по URL."""
    import webbrowser
    try:
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        print(f"Открываю сайт: {url}")
    except Exception as e:
        print(f"Не удалось открыть сайт: {e}")


SKILLS = {
    "open_browser_search": open_browser_search,
    "open_app": open_app,
    "system_volume": system_volume,
    "screenshot": screenshot,
    "open_website": open_website,   # ✅ добавили сюда
}
