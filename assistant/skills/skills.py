from __future__ import annotations
import json, os, glob, shutil, difflib, urllib.parse, webbrowser, subprocess, datetime, logging, time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import mss
import psutil

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"

APP_ALIASES: dict[str, str] = {}
_LAUNCH_LOCK = {}
_LAUNCH_COOLDOWN = 2.0
_APP_CACHE: Dict[str, Tuple[Optional[str], float]] = {}
_CACHE_TIMEOUT = 300

def _cleanup_old_locks():
    current_time = time.time()
    for alias in list(_LAUNCH_LOCK.keys()):
        if current_time - _LAUNCH_LOCK[alias] > _LAUNCH_COOLDOWN * 2:
            _LAUNCH_LOCK.pop(alias, None)

def _is_app_running(alias: str) -> bool:
    try:
        process_names = {
            "powershell": ["powershell.exe", "pwsh.exe"],
            "cmd": ["cmd.exe"], "chrome": ["chrome.exe"], "telegram": ["telegram.exe"],
            "discord": ["discord.exe"], "steam": ["steam.exe"], "code": ["code.exe"],
            "cursor": ["cursor.exe"], "notepad": ["notepad.exe"], "calc": ["calc.exe"],
            "spotify": ["spotify.exe"], "explorer": ["explorer.exe"],
            "settings": ["systemsettings.exe", "ms-settings.exe"]
        }
        processes = process_names.get(alias.lower(), [f"{alias}.exe"])
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'].lower() in [p.lower() for p in processes]:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False
    except Exception:
        return False

def _normalize_path(p: str) -> str:
    return os.path.normpath(os.path.expandvars(str(p).strip()))

def _exists(p: str | None) -> bool:
    return bool(p) and os.path.exists(p)

def _best_fuzzy(key: str, candidates: List[str], cutoff: float = 0.8) -> str | None:
    if not key or not candidates:
        return None
    matches = difflib.get_close_matches(key.lower().strip(), [c.lower() for c in candidates], n=1, cutoff=cutoff)
    return matches[0] if matches else None

def open_browser_search(query: str) -> None:
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query or "")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Не удалось открыть браузер: {e}")

def _find_app_path(app_name: str) -> Optional[str]:
    """Универсальный поиск приложений с кэшированием"""
    cache_key = app_name.lower().strip()
    if cache_key in _APP_CACHE:
        cached_result, timestamp = _APP_CACHE[cache_key]
        if time.time() - timestamp < _CACHE_TIMEOUT:
            return cached_result

    translations = {
        "календарь": "calendar", "калькулятор": "calculator", "блокнот": "notepad",
        "проводник": "explorer", "файлы": "explorer", "музыка": "music",
        "фото": "photos", "почта": "mail", "настройки": "settings", "параметры": "settings",
        "obs studio": "obs64", "obs": "obs64", "discord": "discord", "steam": "steam",
        "spotify": "spotify", "telegram": "telegram", "chrome": "chrome", "code": "code", "cursor": "cursor"
    }
    translated = translations.get(app_name.lower(), app_name.lower())

    username = os.getenv('USERNAME', '')
    search_paths = [
        rf"C:\Windows\System32\{translated}.exe",
        rf"C:\Program Files\{translated.title()}\{translated.title()}.exe",
        rf"C:\Program Files (x86)\{translated.title()}\{translated.title()}.exe",
    ]

    special_paths = {
        "calendar": [r"C:\Program Files\Microsoft Office\root\Office16\outlook.exe"],
        "obs64": [r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"],
        "discord": [rf"C:\Users\{username}\AppData\Local\Discord\Update.exe"],
        "spotify": [rf"C:\Users\{username}\AppData\Roaming\Spotify\Spotify.exe"],
        "telegram": [rf"C:\Users\{username}\AppData\Roaming\Telegram Desktop\Telegram.exe"],
        "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
        "code": [rf"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
        "cursor": [rf"C:\Users\{username}\AppData\Local\Programs\cursor\Cursor.exe"]
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
        if result.returncode == 0 and result.stdout.strip():
            found = result.stdout.strip().split('\n')[0]
            if _exists(found):
                _APP_CACHE[cache_key] = (found, time.time())
                return found
    except Exception:
        pass

    try:
        import winreg
        for hkey, subkey in [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
                            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")]:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        app_name_reg = winreg.EnumKey(key, i)
                        if translated.lower() in app_name_reg.lower():
                            with winreg.OpenKey(key, app_name_reg) as app_key:
                                app_path = winreg.QueryValue(app_key, "")
                                if _exists(app_path):
                                    _APP_CACHE[cache_key] = (app_path, time.time())
                                    return app_path
            except Exception:
                continue
    except Exception:
        pass

    _APP_CACHE[cache_key] = (None, time.time())
    return None

def _resolve_app_path(alias: str) -> Tuple[Optional[str], List[str]]:
    a = (alias or "").lower().strip()
    if not a:
        return None, []

    path_cfg = APP_ALIASES.get(a)
    if path_cfg:
        if path_cfg.startswith(("ms-settings:", "http:", "https:")):
            return path_cfg, []
        path_cfg = _normalize_path(path_cfg)
        if _exists(path_cfg):
            if a == "discord" and os.path.basename(path_cfg).lower() == "update.exe":
                return path_cfg, ["--processStart", "Discord.exe"]
            return path_cfg, []

    known = {
        "notepad": r"C:\Windows\System32\notepad.exe", "calc": r"C:\Windows\System32\calc.exe",
        "cmd": r"C:\Windows\System32\cmd.exe", "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "explorer": r"C:\Windows\explorer.exe", "settings": "ms-settings:",
        "paint": r"%LOCALAPPDATA%\Microsoft\WindowsApps\mspaint.exe",
        "photos": r"C:\Program Files\WindowsApps\Microsoft.Windows.Photos_*\Photos.exe",
        "calendar": r"C:\Program Files\WindowsApps\microsoft.windowscommunicationsapps_*\HxCalendar.exe",
        "mail": r"C:\Program Files\WindowsApps\microsoft.windowscommunicationsapps_*\HxMail.exe",
        "code": r"%USERPROFILE%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "telegram": r"%APPDATA%\Telegram Desktop\Telegram.exe",
        "spotify": r"%APPDATA%\Spotify\Spotify.exe", "steam": r"C:\Program Files (x86)\Steam\Steam.exe"
    }

    if a in known:
        path = known[a]
        if path.startswith("ms-settings:"):
            return path, []
        normalized = _normalize_path(path)
        if _exists(normalized):
            return normalized, []
        elif '*' in normalized:
            matches = glob.glob(normalized)
            if matches and _exists(matches[0]):
                return matches[0], []

    found_path = _find_app_path(a)
    if found_path and _exists(found_path):
        return found_path, []

    if APP_ALIASES and a not in APP_ALIASES:
        guess = _best_fuzzy(a, list(APP_ALIASES.keys()), cutoff=0.8)
        if guess:
            path_guess = APP_ALIASES[guess]
            if path_guess.startswith(("ms-settings:", "http:", "https:")):
                return path_guess, []
            path_guess = _normalize_path(path_guess)
            if _exists(path_guess):
                return path_guess, []

    found = shutil.which(a) or shutil.which(f"{a}.exe")
    if found and _exists(found):
        return found, []

    return None, []

def _auto_add_app_to_config(alias: str, path: str) -> None:
    try:
        if _CONFIG_PATH.exists():
            with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
        if "app_aliases" not in config:
            config["app_aliases"] = {}
        config["app_aliases"][alias] = path
        with _CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        APP_ALIASES[alias] = path
    except Exception as e:
        logging.error(f"Не удалось сохранить приложение в конфигурацию: {e}")

def open_app(alias: str) -> None:
    _cleanup_old_locks()
    current_time = time.time()
    if alias in _LAUNCH_LOCK:
        if current_time - _LAUNCH_LOCK[alias] < _LAUNCH_COOLDOWN:
            print(f"⏳ Приложение {alias} уже запускается, подождите...")
            return
    _LAUNCH_LOCK[alias] = current_time

    path, extra_args = _resolve_app_path(alias)
    if not path:
        print(f"Не знаю приложение: {alias}")
        _LAUNCH_LOCK.pop(alias, None)
        return

    if alias not in APP_ALIASES and path:
        _auto_add_app_to_config(alias, path)

    try:
        if path.startswith("ms-settings:"):
            subprocess.Popen(["start", path], shell=True)
            return

        if _is_app_running(alias):
            print(f"✅ {alias} уже запущен")
            return

        if alias.lower() in ["powershell", "пауршелл"]:
            subprocess.Popen([path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            return

        if not extra_args and (path.lower().endswith(".lnk") or path.lower().endswith(".exe")):
            os.startfile(path)
            return

        subprocess.Popen([path, *extra_args])
    except Exception as e:
        print(f"Не получилось открыть {alias}: {e}")
        _LAUNCH_LOCK.pop(alias, None)

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
    except Exception as e:
        print(f"Не удалось сделать скриншот: {e}")

def open_website(url: str) -> None:
    try:
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
    except Exception as e:
        print(f"Не удалось открыть сайт: {e}")

def minimize_app(alias: str) -> None:
    try:
        import win32gui, win32con
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title:
                    windows.append((hwnd, window_title))
            return True

        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)

        app_keywords = {
            "spotify": ["spotify", "музыка", "спотифай"], "chrome": ["chrome", "google chrome", "хром"],
            "telegram": ["telegram", "телеграм"], "discord": ["discord"], "steam": ["steam"],
            "code": ["visual studio code", "vs code"], "cursor": ["cursor"],
            "notepad": ["notepad", "блокнот"], "calc": ["calculator"], "explorer": ["explorer", "проводник"],
            "armoury": ["armoury crate", "armoury"], "settings": ["settings", "параметры"]
        }

        keywords = app_keywords.get(alias.lower(), [alias])
        found_windows = [(hwnd, title) for hwnd, title in windows
                         if any(kw.lower() in title.lower() for kw in keywords)]

        if found_windows:
            for hwnd, _ in found_windows:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            print(f"Свернул {len(found_windows)} окна {alias}")
        else:
            print(f"Не найдены окна приложения: {alias}")
    except Exception as e:
        print(f"Не удалось свернуть {alias}: {e}")

def close_app(alias: str) -> None:
    try:
        app_processes = {
            "spotify": ["spotify.exe"], "chrome": ["chrome.exe"], "telegram": ["telegram.exe"],
            "discord": ["discord.exe"], "steam": ["steam.exe"], "code": ["code.exe"],
            "cursor": ["cursor.exe"], "notepad": ["notepad.exe"], "calc": ["calc.exe"],
            "explorer": ["explorer.exe"], "armoury": ["armoury crate.exe"], "settings": ["systemsettings.exe"]
        }
        processes = app_processes.get(alias.lower(), [f"{alias}.exe"])
        closed_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'].lower() in [p.lower() for p in processes]:
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if closed_count > 0:
            print(f"Закрыл {closed_count} процессов {alias}")
        else:
            print(f"Не найдены процессы: {alias}")
    except Exception as e:
        print(f"Не удалось закрыть {alias}: {e}")

def system_shutdown() -> None:
    try:
        subprocess.run(["shutdown", "/s", "/t", "10"], check=True)
        print("[SYSTEM] Система будет выключена через 10 секунд")
    except Exception as e:
        print(f"Ошибка выключения: {e}")

def system_restart() -> None:
    try:
        subprocess.run(["shutdown", "/r", "/t", "10"], check=True)
        print("[SYSTEM] Система будет перезагружена через 10 секунд")
    except Exception as e:
        print(f"Ошибка перезагрузки: {e}")

def system_sleep() -> None:
    try:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
        print("[SYSTEM] Система переходит в режим сна")
    except Exception as e:
        print(f"Ошибка перехода в сон: {e}")

def system_lock() -> None:
    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
        print("[SYSTEM] Система заблокирована")
    except Exception as e:
        print(f"Ошибка блокировки: {e}")

def wifi_toggle() -> None:
    try:
        result = subprocess.run(["netsh", "interface", "show", "interface"], capture_output=True, text=True)
        if "Wi-Fi" in result.stdout:
            subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "admin=disable"], check=True)
            print("[WIFI] Wi-Fi отключен")
        else:
            subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "admin=enable"], check=True)
            print("[WIFI] Wi-Fi включен")
    except Exception as e:
        print(f"Ошибка управления Wi-Fi: {e}")

def brightness_set(level: int) -> None:
    try:
        level = max(0, min(100, int(level)))
        subprocess.run(["powershell", "-Command", f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"], check=True)
        print(f"[BRIGHTNESS] Яркость установлена: {level}%")
    except Exception as e:
        print(f"Ошибка установки яркости: {e}")

def clipboard_copy(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
        print(f"[CLIPBOARD] Скопировано в буфер: {text[:50]}...")
    except Exception as e:
        print(f"Ошибка копирования: {e}")

def clipboard_paste() -> str:
    try:
        import pyperclip
        text = pyperclip.paste()
        print(f"[CLIPBOARD] Содержимое буфера: {text[:50]}...")
        return text
    except Exception as e:
        print(f"Ошибка вставки: {e}")
        return ""

def confirm_action() -> None:
    pass

def cancel_action() -> None:
    pass

def _smart_search_with_context(app_name: str, user_context: str = "") -> Optional[str]:
    """Умный поиск с учетом контекста"""
    context_mappings = {
        "фото редактор": ["paint"], "фотографии": ["photos"], "музыка": ["spotify"],
        "видео": ["vlc"], "браузер": ["chrome"], "текст": ["notepad", "code"],
        "календарь": ["calendar"], "почта": ["mail"]
    }

    for context, aliases in context_mappings.items():
        if context in app_name.lower() or context in user_context.lower():
            for alias in aliases:
                if alias in APP_ALIASES:
                    path = APP_ALIASES[alias]
                    if path.startswith("ms-settings:"):
                        return path
                    normalized = _normalize_path(path)
                    if _exists(normalized):
                        return normalized
                    elif '*' in normalized:
                        matches = glob.glob(normalized)
                        if matches and _exists(matches[0]):
                            return matches[0]

    return _find_app_path(app_name)

SKILLS = {
    "open_browser_search": open_browser_search,
    "open_app": open_app,
    "system_volume": system_volume,
    "screenshot": screenshot,
    "open_website": open_website,
    "minimize_app": minimize_app,
    "close_app": close_app,
    "system_shutdown": system_shutdown,
    "system_restart": system_restart,
    "system_sleep": system_sleep,
    "system_lock": system_lock,
    "wifi_toggle": wifi_toggle,
    "brightness_set": brightness_set,
    "clipboard_copy": clipboard_copy,
    "clipboard_paste": clipboard_paste,
    "confirm_action": confirm_action,
    "cancel_action": cancel_action,
}
