from __future__ import annotations
import logging
import urllib.parse
import webbrowser

logger = logging.getLogger(__name__)


def open_browser_search(query: str) -> None:
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query or "")
    try:
        webbrowser.open(url)
    except OSError as exc:
        logger.error("Не удалось открыть браузер: %s", exc)


def open_website(url: str) -> None:
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
    except OSError as exc:
        logger.error("Не удалось открыть сайт: %s", exc)
