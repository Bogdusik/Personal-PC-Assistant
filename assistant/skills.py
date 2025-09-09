# assistant/skills.py
import os
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

# Заполняется из config.json в main.py: APP_ALIASES.update(...)
APP_ALIASES: dict[str, str] = {}

def open_browser_search(query: str) -> None:
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Не удалось открыть браузер: {e}")

def _resolve_app_path(alias: str) -> str | None:
    """Находим путь к приложению:
       1) белый список (config.json)
       2) поиск в PATH (shutil.which)
       3) дефолтные известные пути (например, notepad)
    """
    a = alias.lower().strip()

    # 1) белый список
    path = APP_ALIASES.get(a)
    if path and os.path.exists(path):
        return path

    # 2) поиск в PATH (notepad, calc и т.п.)
    exe_name = a if a.endswith(".exe") else f"{a}.exe"
    found = shutil.which(a) or shutil.which(exe_name)
    if found:
        return found

    # 3) дефолтные fallback'и
    known = {
        "notepad": r"C:\Windows\System32\notepad.exe",
        "блокнот": r"C:\Windows\System32\notepad.exe",
        "calc":    r"C:\Windows\System32\calc.exe",
        "калькулятор": r"C:\Windows\System32\calc.exe",
        "cmd":     r"C:\Windows\System32\cmd.exe",
        "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    }
    path = known.get(a)
    if path and os.path.exists(path):
        return path

    return None

def open_app(alias: str) -> None:
    path = _resolve_app_path(alias)
    if not path:
        print(f"Не знаю приложение: {alias}")
        return
    try:
        # os.startfile корректно открывает .exe, .lnk и ассоциированные файлы
        os.startfile(path)
    except Exception:
        # запасной вариант — прямой запуск процесса
        try:
            subprocess.Popen([path])
        except Exception as e:
            print(f"Не получилось открыть {alias}: {e}")

def system_volume(level: int) -> None:
    level = max(0, min(100, int(level)))
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        vmin, vmax, _ = volume.GetVolumeRange()  # dB
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
