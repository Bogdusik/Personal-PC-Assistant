from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def clipboard_copy(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
        logger.info("[CLIPBOARD] Скопировано: %s", text[:50])
    except ImportError:
        logger.error("pyperclip не установлен — clipboard_copy недоступен")
    except Exception as exc:
        logger.error("Ошибка копирования в буфер: %s", exc)


def clipboard_paste() -> str:
    try:
        import pyperclip
        text = pyperclip.paste()
        logger.info("[CLIPBOARD] Получено из буфера: %s", text[:50])
        return text
    except ImportError:
        logger.error("pyperclip не установлен — clipboard_paste недоступен")
        return ""
    except Exception as exc:
        logger.error("Ошибка чтения буфера: %s", exc)
        return ""


def confirm_action() -> None:
    pass


def cancel_action() -> None:
    pass
