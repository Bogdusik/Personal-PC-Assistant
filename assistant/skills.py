# assistant/skills.py
import os
import glob
import shutil
import urllib.parse
import webbrowser
import subprocess
import datetime
import logging
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import mss

# наполняется из main.py: APP_ALIASES.update(cfg["app_aliases"])
APP_ALIASES: dict[str, str] = {}

def open_browser_search(query: str) -> None:
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Не удалось открыть браузер: {e}")

def _normalize_path(p: str) -> str:
    return os.path.normpath(os.path.expandvars(p))

def _resolve_app_path(alias: str) -> tuple[str | None, list[str]]:
    """
    Возвращает (path, extra_args). extra_args может быть нужен, например, для Discord Update.exe.
    Порядок поиска:
      1) config.json (с разворачиванием %VARS%)
      2) PATH (shutil.which)
      3) известные пути, включая Discord app-*
    """
    a = alias.lower().strip()

    # 1) белый список (config.json)
    cfg_path = APP_ALIASES.get(a)
    if cfg_path:
        cfg_path = _normalize_path(cfg_path)
        if os.path.exists(cfg_path):
            # Особый случай: если это Discord Update.exe — добавим аргументы
            if a == "discord" and os.path.basename(cfg_path).lower() == "update.exe":
                return cfg_path, ["--processStart", "Discord.exe"]
            return cfg_path, []

    # 2) поиск в PATH
    exe_name = a if a.endswith(".exe") else f"{a}.exe"
    found = shutil.which(a) or shutil.which(exe_name)
    if found and os.path.exists(found):
        return found, []

    # 3) известные пути
    known = {
        # системные
        "notepad": r"C:\Windows\System32\notepad.exe",
        "блокнот": r"C:\Windows\System32\notepad.exe",
        "calc":    r"C:\Windows\System32\calc.exe",
        "калькулятор": r"C:\Windows\System32\calc.exe",
        "cmd":     r"C:\Windows\System32\cmd.exe",
        "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",

        # редакторы
        "code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",

        # браузер
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",

        # мессенджеры
        "telegram": r"C:\Users\%USERNAME%\AppData\Roaming\Telegram Desktop\Telegram.exe",
        # discord: попробуем сначала Update.exe с аргами; если нет — ищем Discord.exe в app-*
        "discord_update": r"C:\Users\%USERNAME%\AppData\Local\Discord\Update.exe",

        # игры/клиенты
        "steam": r"C:\Program Files (x86)\Steam\Steam.exe",
    }

    if a == "discord":
        # сначала попытаемся Update.exe с аргументами
        upd = _normalize_path(known["discord_update"])
        if os.path.exists(upd):
            return upd, ["--processStart", "Discord.exe"]
        # иначе ищем Discord.exe в app-*
        pattern = _normalize_path(r"C:\Users\%USERNAME%\AppData\Local\Discord\app-*\Discord.exe")
        candidates = sorted(glob.glob(pattern))
        if candidates:
            return candidates[-1], []  # последняя обычно самая свежая версия

    known_path = known.get(a)
    if known_path:
        known_path = _normalize_path(known_path)
        if os.path.exists(known_path):
            return known_path, []

    return None, []

def open_app(alias: str) -> None:
    path, extra_args = _resolve_app_path(alias)
    if not path:
        print(f"Не знаю приложение: {alias}")
        return
    try:
        # os.startfile хорошо открывает .exe/.lnk, но аргументы не передать → используем его только без extra_args
        if not extra_args and (path.lower().endswith(".lnk") or path.lower().endswith(".exe")):
            os.startfile(path)
            return
        # если нужны аргументы (или это не .lnk/.exe) — subprocess
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

SKILLS = {
    "open_browser_search": open_browser_search,
    "open_app": open_app,
    "system_volume": system_volume,
    "screenshot": screenshot,
}
