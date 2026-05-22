from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from .app_control import close_app, minimize_app, open_app
from .browser import open_browser_search, open_website
from .clipboard import cancel_action, clipboard_copy, clipboard_paste, confirm_action
from .system_control import (
    brightness_set,
    screenshot,
    system_lock,
    system_restart,
    system_shutdown,
    system_sleep,
    system_volume,
    wifi_toggle,
)


@runtime_checkable
class Skill(Protocol):
    def __call__(self, **kwargs: object) -> object:
        ...


SKILLS: dict[str, Callable[..., object]] = {
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
