# Backwards-compatibility shim — logic lives in the sub-modules.
# runner.py and any legacy code can still import from here.
from .registry import SKILLS
from .app_control import APP_ALIASES, _resolve_app_path, _auto_add_app_to_config, _smart_search_with_context
from .browser import open_browser_search, open_website
from .clipboard import clipboard_copy, clipboard_paste, confirm_action, cancel_action
from .system_control import (
    system_volume, screenshot, system_shutdown, system_restart,
    system_sleep, system_lock, wifi_toggle, brightness_set,
)
from .app_control import open_app, minimize_app, close_app

__all__ = [
    "SKILLS", "APP_ALIASES",
    "open_browser_search", "open_app", "system_volume", "screenshot", "open_website",
    "minimize_app", "close_app", "system_shutdown", "system_restart", "system_sleep",
    "system_lock", "wifi_toggle", "brightness_set", "clipboard_copy", "clipboard_paste",
    "confirm_action", "cancel_action", "_resolve_app_path", "_auto_add_app_to_config",
    "_smart_search_with_context",
]
