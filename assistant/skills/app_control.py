from __future__ import annotations

import difflib
import glob
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import psutil

from assistant.core.exceptions import SkillError

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"

APP_ALIASES: dict[str, str] = {}
_LAUNCH_LOCK: dict[str, float] = {}
_LAUNCH_COOLDOWN = 2.0
_APP_CACHE: dict[str, tuple[Optional[str], float]] = {}
_CACHE_TIMEOUT = 300

PROTECTED_PROCESSES = frozenset({
    "lsass.exe", "winlogon.exe", "csrss.exe",
    "services.exe", "smss.exe", "wininit.exe", "system",
})


def _cleanup_old_locks() -> None:
    now = time.time()
    for alias in list(_LAUNCH_LOCK.keys()):
        if now - _LAUNCH_LOCK[alias] > _LAUNCH_COOLDOWN * 2:
            _LAUNCH_LOCK.pop(alias, None)


def _is_app_running(alias: str) -> bool:
    known: dict[str, list[str]] = {
        "powershell": ["powershell.exe", "pwsh.exe"],
        "cmd": ["cmd.exe"], "chrome": ["chrome.exe"], "telegram": ["telegram.exe"],
        "discord": ["discord.exe"], "steam": ["steam.exe"], "code": ["code.exe"],
        "cursor": ["cursor.exe"], "notepad": ["notepad.exe"], "calc": ["calc.exe"],
        "spotify": ["spotify.exe"], "explorer": ["explorer.exe"],
        "settings": ["systemsettings.exe", "ms-settings.exe"],
    }
    processes = known.get(alias.lower(), [f"{alias}.exe"])
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"].lower() in [p.lower() for p in processes]:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except psutil.Error:
        pass
    return False


def _normalize_path(p: str) -> str:
    return os.path.normpath(os.path.expandvars(str(p).strip()))


def _exists(p: Optional[str]) -> bool:
    return bool(p) and os.path.exists(p)


def _best_fuzzy(key: str, candidates: list[str], cutoff: float = 0.8) -> Optional[str]:
    if not key or not candidates:
        return None
    matches = difflib.get_close_matches(key.lower().strip(), [c.lower() for c in candidates], n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _find_app_path(app_name: str) -> Optional[str]:
    cache_key = app_name.lower().strip()
    if cache_key in _APP_CACHE:
        cached_result, timestamp = _APP_CACHE[cache_key]
        if time.time() - timestamp < _CACHE_TIMEOUT:
            return cached_result

    translations: dict[str, str] = {
        "календарь": "calendar", "калькулятор": "calculator", "блокнот": "notepad",
        "проводник": "explorer", "файлы": "explorer", "музыка": "music",
        "фото": "photos", "почта": "mail", "настройки": "settings", "параметры": "settings",
        "obs studio": "obs64", "obs": "obs64",
        "discord": "discord", "steam": "steam", "spotify": "spotify",
        "telegram": "telegram", "chrome": "chrome", "code": "code", "cursor": "cursor",
    }
    translated = translations.get(app_name.lower(), app_name.lower())
    username = os.getenv("USERNAME", "")

    search_paths = [
        rf"C:\Windows\System32\{translated}.exe",
        rf"C:\Program Files\{translated.title()}\{translated.title()}.exe",
        rf"C:\Program Files (x86)\{translated.title()}\{translated.title()}.exe",
    ]
    special_paths: dict[str, list[str]] = {
        "calendar": [r"C:\Program Files\Microsoft Office\root\Office16\outlook.exe"],
        "obs64": [r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"],
        "discord": [rf"C:\Users\{username}\AppData\Local\Discord\Update.exe"],
        "spotify": [rf"C:\Users\{username}\AppData\Roaming\Spotify\Spotify.exe"],
        "telegram": [rf"C:\Users\{username}\AppData\Roaming\Telegram Desktop\Telegram.exe"],
        "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
        "code": [rf"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
        "cursor": [rf"C:\Users\{username}\AppData\Local\Programs\cursor\Cursor.exe"],
    }
    if translated in special_paths:
        search_paths.extend(special_paths[translated])

    for path in search_paths:
        if "*" in path:
            matches = glob.glob(path)
            if matches:
                _APP_CACHE[cache_key] = (matches[0], time.time())
                return matches[0]
        elif _exists(path):
            _APP_CACHE[cache_key] = (path, time.time())
            return path

    try:
        result = subprocess.run(["where", translated], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            found = result.stdout.strip().split("\n")[0]
            if _exists(found):
                _APP_CACHE[cache_key] = (found, time.time())
                return found
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    try:
        import winreg
        for hkey, subkey in [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        reg_name = winreg.EnumKey(key, i)
                        if translated.lower() in reg_name.lower():
                            with winreg.OpenKey(key, reg_name) as app_key:
                                app_path = winreg.QueryValue(app_key, "")
                                if _exists(app_path):
                                    _APP_CACHE[cache_key] = (app_path, time.time())
                                    return app_path
            except OSError:
                continue
    except ImportError:
        pass

    _APP_CACHE[cache_key] = (None, time.time())
    return None


def _resolve_app_path(alias: str) -> tuple[Optional[str], list[str]]:
    a = (alias or "").lower().strip()
    if not a:
        return None, []

    path_cfg = APP_ALIASES.get(a)
    if path_cfg:
        if path_cfg.startswith(("ms-settings:", "http:", "https:")):
            return path_cfg, []
        normalized = _normalize_path(path_cfg)
        if _exists(normalized):
            if a == "discord" and os.path.basename(normalized).lower() == "update.exe":
                return normalized, ["--processStart", "Discord.exe"]
            return normalized, []

    known: dict[str, str] = {
        "notepad": r"C:\Windows\System32\notepad.exe",
        "calc": r"C:\Windows\System32\calc.exe",
        "cmd": r"C:\Windows\System32\cmd.exe",
        "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "explorer": r"C:\Windows\explorer.exe",
        "settings": "ms-settings:",
        "paint": r"%LOCALAPPDATA%\Microsoft\WindowsApps\mspaint.exe",
        "photos": r"C:\Program Files\WindowsApps\Microsoft.Windows.Photos_*\Photos.exe",
        "calendar": r"C:\Program Files\WindowsApps\microsoft.windowscommunicationsapps_*\HxCalendar.exe",
        "mail": r"C:\Program Files\WindowsApps\microsoft.windowscommunicationsapps_*\HxMail.exe",
        "code": r"%USERPROFILE%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "telegram": r"%APPDATA%\Telegram Desktop\Telegram.exe",
        "spotify": r"%APPDATA%\Spotify\Spotify.exe",
        "steam": r"C:\Program Files (x86)\Steam\Steam.exe",
    }
    if a in known:
        path = known[a]
        if path.startswith("ms-settings:"):
            return path, []
        normalized = _normalize_path(path)
        if _exists(normalized):
            return normalized, []
        if "*" in normalized:
            matches = glob.glob(normalized)
            if matches and _exists(matches[0]):
                return matches[0], []

    found = _find_app_path(a)
    if found and _exists(found):
        return found, []

    if APP_ALIASES and a not in APP_ALIASES:
        guess = _best_fuzzy(a, list(APP_ALIASES.keys()), cutoff=0.8)
        if guess:
            path_guess = APP_ALIASES[guess]
            if path_guess.startswith(("ms-settings:", "http:", "https:")):
                return path_guess, []
            normalized = _normalize_path(path_guess)
            if _exists(normalized):
                return normalized, []

    found = shutil.which(a) or shutil.which(f"{a}.exe")
    if found and _exists(found):
        return found, []

    return None, []


def _auto_add_app_to_config(alias: str, path: str) -> None:
    try:
        config: dict = {}
        if _CONFIG_PATH.exists():
            with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                config = json.load(f)
        config.setdefault("app_aliases", {})[alias] = path
        with _CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        APP_ALIASES[alias] = path
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Не удалось сохранить приложение в конфиг: %s", exc)


def open_app(alias: str) -> None:
    _cleanup_old_locks()
    now = time.time()
    if alias in _LAUNCH_LOCK and now - _LAUNCH_LOCK[alias] < _LAUNCH_COOLDOWN:
        logger.info("Приложение %s уже запускается, cooldown", alias)
        return
    _LAUNCH_LOCK[alias] = now

    path, extra_args = _resolve_app_path(alias)
    if not path:
        _LAUNCH_LOCK.pop(alias, None)
        raise SkillError(f"Не знаю приложение: {alias}")

    if alias not in APP_ALIASES and path:
        _auto_add_app_to_config(alias, path)

    try:
        if path.startswith("ms-settings:"):
            os.startfile(path)
            return

        if _is_app_running(alias):
            logger.info("%s уже запущен", alias)
            return

        if alias.lower() in ["powershell", "пауршелл"]:
            subprocess.Popen([path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            return

        if not extra_args and path.lower().endswith((".lnk", ".exe")):
            os.startfile(path)
            return

        subprocess.Popen([path, *extra_args])
    except OSError as exc:
        _LAUNCH_LOCK.pop(alias, None)
        raise SkillError(f"Не получилось открыть {alias}: {exc}") from exc


def minimize_app(alias: str) -> None:
    try:
        import win32con
        import win32gui
    except ImportError as exc:
        raise SkillError("pywin32 не установлен") from exc

    keywords: dict[str, list[str]] = {
        "spotify": ["spotify", "музыка", "спотифай"], "chrome": ["chrome", "google chrome", "хром"],
        "telegram": ["telegram", "телеграм"], "discord": ["discord"], "steam": ["steam"],
        "code": ["visual studio code", "vs code"], "cursor": ["cursor"],
        "notepad": ["notepad", "блокнот"], "calc": ["calculator"],
        "explorer": ["explorer", "проводник"], "armoury": ["armoury crate", "armoury"],
        "settings": ["settings", "параметры"],
    }
    kws = keywords.get(alias.lower(), [alias])

    windows: list[tuple[int, str]] = []

    def _cb(hwnd: int, _data: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append((hwnd, title))
        return True

    win32gui.EnumWindows(_cb, None)
    matched = [(hwnd, title) for hwnd, title in windows if any(kw.lower() in title.lower() for kw in kws)]

    if matched:
        for hwnd, _ in matched:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        logger.info("Свернул %d окно(а) %s", len(matched), alias)
    else:
        raise SkillError(f"Не найдены окна приложения: {alias}")


def close_app(alias: str) -> None:
    app_processes: dict[str, list[str]] = {
        "spotify": ["spotify.exe"], "chrome": ["chrome.exe"], "telegram": ["telegram.exe"],
        "discord": ["discord.exe"], "steam": ["steam.exe"], "code": ["code.exe"],
        "cursor": ["cursor.exe"], "notepad": ["notepad.exe"], "calc": ["calc.exe"],
        "explorer": ["explorer.exe"], "armoury": ["armoury crate.exe"],
        "settings": ["systemsettings.exe"],
    }
    processes = app_processes.get(alias.lower(), [f"{alias}.exe"])

    protected = {p.lower() for p in processes} & PROTECTED_PROCESSES
    if protected:
        raise SkillError(f"Нельзя завершить защищённый процесс: {', '.join(protected)}")

    closed = 0
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"].lower() in [p.lower() for p in processes]:
                    proc.terminate()
                    closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except psutil.Error as exc:
        raise SkillError(f"Ошибка psutil при закрытии {alias}: {exc}") from exc

    if closed == 0:
        raise SkillError(f"Не найдены процессы: {alias}")
    logger.info("Закрыл %d процессов %s", closed, alias)


def _smart_search_with_context(app_name: str, user_context: str = "") -> Optional[str]:
    context_mappings: dict[str, list[str]] = {
        "фото редактор": ["paint"], "фотографии": ["photos"], "музыка": ["spotify"],
        "видео": ["vlc"], "браузер": ["chrome"], "текст": ["notepad", "code"],
        "календарь": ["calendar"], "почта": ["mail"],
    }
    for context, aliases in context_mappings.items():
        if context in app_name.lower() or context in user_context.lower():
            for a in aliases:
                if a in APP_ALIASES:
                    path = APP_ALIASES[a]
                    if path.startswith("ms-settings:"):
                        return path
                    normalized = _normalize_path(path)
                    if _exists(normalized):
                        return normalized
                    if "*" in normalized:
                        matches = glob.glob(normalized)
                        if matches and _exists(matches[0]):
                            return matches[0]
    return _find_app_path(app_name)
