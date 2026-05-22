from __future__ import annotations
import datetime
import logging
import os
import subprocess

from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import mss

from assistant.core.exceptions import SkillError

logger = logging.getLogger(__name__)


def system_volume(level: int) -> None:
    level = max(0, min(100, int(level)))
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        vmin, vmax, _ = volume.GetVolumeRange()
        target = vmin + (vmax - vmin) * (level / 100.0)
        volume.SetMasterVolumeLevel(target, None)
        logger.info("[VOLUME] Громкость: %d%%", level)
    except Exception as exc:
        raise SkillError(f"Не удалось установить громкость: {exc}") from exc


def screenshot() -> None:
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"screenshot_{ts}.png"
        with mss.mss() as sct:
            sct.shot(output=fn)
        logger.info("[SCREENSHOT] Сохранён: %s", fn)
        print(f"Скриншот: {fn}")
    except Exception as exc:
        raise SkillError(f"Не удалось сделать скриншот: {exc}") from exc


def system_shutdown() -> None:
    try:
        subprocess.run(["shutdown", "/s", "/t", "10"], check=True)
        logger.info("[SYSTEM] Выключение через 10 сек")
    except subprocess.CalledProcessError as exc:
        raise SkillError(f"Ошибка выключения: {exc}") from exc


def system_restart() -> None:
    try:
        subprocess.run(["shutdown", "/r", "/t", "10"], check=True)
        logger.info("[SYSTEM] Перезагрузка через 10 сек")
    except subprocess.CalledProcessError as exc:
        raise SkillError(f"Ошибка перезагрузки: {exc}") from exc


def system_sleep() -> None:
    try:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
        logger.info("[SYSTEM] Переход в сон")
    except subprocess.CalledProcessError as exc:
        raise SkillError(f"Ошибка перехода в сон: {exc}") from exc


def system_lock() -> None:
    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
        logger.info("[SYSTEM] Блокировка")
    except subprocess.CalledProcessError as exc:
        raise SkillError(f"Ошибка блокировки: {exc}") from exc


def wifi_toggle() -> None:
    try:
        result = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True, text=True,
        )
        if "Wi-Fi" in result.stdout:
            subprocess.run(
                ["netsh", "interface", "set", "interface", "Wi-Fi", "admin=disable"],
                check=True,
            )
            logger.info("[WIFI] Отключён")
        else:
            subprocess.run(
                ["netsh", "interface", "set", "interface", "Wi-Fi", "admin=enable"],
                check=True,
            )
            logger.info("[WIFI] Включён")
    except subprocess.CalledProcessError as exc:
        raise SkillError(f"Ошибка управления Wi-Fi: {exc}") from exc


def brightness_set(level: int) -> None:
    level = max(0, min(100, int(level)))
    try:
        import wmi as wmi_module
        conn = wmi_module.WMI(namespace="root/WMI")
        methods = conn.WmiMonitorBrightnessMethods()
        if not methods:
            raise SkillError("Монитор не поддерживает управление яркостью через WMI")
        methods[0].WmiSetBrightness(1, level)
        logger.info("[BRIGHTNESS] Яркость: %d%%", level)
    except ImportError:
        logger.warning("wmi не установлен — fallback на PowerShell")
        try:
            subprocess.run(
                ["powershell", "-Command",
                 f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{int(level)})"],
                check=True,
                capture_output=True,
            )
            logger.info("[BRIGHTNESS] Яркость (PS fallback): %d%%", level)
        except subprocess.CalledProcessError as exc:
            raise SkillError(f"Ошибка яркости (PowerShell): {exc}") from exc
    except Exception as exc:
        raise SkillError(f"Ошибка установки яркости: {exc}") from exc
