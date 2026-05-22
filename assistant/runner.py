from __future__ import annotations

import logging
import re
import time
from typing import Optional

from .core.exceptions import SkillError
from .skills import SKILLS

logger = logging.getLogger(__name__)

_PENDING: Optional[dict] = None
CONFIRM_THRESHOLD = 0.65
CONFIRM_TIMEOUT_SEC = 25

_LAST_COMMAND: Optional[tuple[float, str]] = None
_COMMAND_COOLDOWN = 1.0

_YES_RE = re.compile(
    r"\bда\b|\bok\b|\bокей\b|\bугу\b|\bага\b|\bподтверждаю\b|\bдавай\b|\bконечно\b|\bпоехали\b|\bго\b|\byes\b|\bладно\b",
    re.IGNORECASE,
)
_NO_RE = re.compile(
    r"\bнет\b|\bотмена\b|\bотмени\b|\bне надо\b|\bстоп\b|\bне\b|\bno\b|\bне делай\b",
    re.IGNORECASE,
)


def _is_yes(text: str) -> bool:
    return bool(_YES_RE.search((text or "").strip()))


def _is_no(text: str) -> bool:
    return bool(_NO_RE.search((text or "").strip()))


def _pretty_cmd(cmd: dict) -> str:
    intent = cmd.get("intent")
    args = cmd.get("args", {})
    if intent == "open_app":
        return f"Запустить: {args.get('alias')}"
    if intent == "open_browser_search":
        q = args.get("query")
        return f"Открыть поиск: «{q}»" if q else "Открыть поиск"
    if intent == "system_volume":
        return f"Громкость: {args.get('level')}%"
    if intent == "screenshot":
        return "Скриншот"
    return intent or "команда"


def _exec_skill(intent: str, args: dict, speak: Optional[str]) -> None:
    fn = SKILLS.get(intent)
    if not fn:
        logger.error("Неизвестная команда: %s", intent)
        print(f"Неизвестная команда: {intent}")
        return
    try:
        logger.info("Выполняю навык: %s args=%s", intent, args)
        fn(**args)
        logger.info("Навык %s выполнен", intent)
    except SkillError as exc:
        print(f"[Ошибка] {exc}")
        logger.error("SkillError при %s: %s", intent, exc)
        return
    except TypeError as exc:
        print(f"Неверные аргументы для ({intent}): {exc}")
        logger.error("TypeError при %s: %s", intent, exc)
        return
    if speak:
        print(f"[OK] {speak}", flush=True)


def run_command(cmd: dict) -> None:
    global _PENDING, _LAST_COMMAND

    if not isinstance(cmd, dict) or "intent" not in cmd:
        logger.warning("Некорректная команда: %s", cmd)
        return

    intent: str = cmd["intent"]
    args: dict = cmd.get("args", {})
    speak: Optional[str] = cmd.get("speak")
    float(cmd.get("confidence", 1.0))

    now = time.time()
    command_key = f"{intent}:{args}"

    if _LAST_COMMAND:
        last_time, last_key = _LAST_COMMAND
        if command_key == last_key and now - last_time < _COMMAND_COOLDOWN:
            print("[WAIT] Команда уже выполняется, подождите...")
            return

    _LAST_COMMAND = (now, command_key)

    if _PENDING and (time.time() - _PENDING.get("ts", 0) > CONFIRM_TIMEOUT_SEC):
        _PENDING = None

    if _PENDING:
        if intent in ("confirm_action", "cancel_action", "smalltalk"):
            if intent == "confirm_action":
                confirmed = True
            elif intent == "cancel_action":
                confirmed = False
            else:
                user_reply = (args.get("text") or "").strip()
                if _is_yes(user_reply):
                    confirmed = True
                elif _is_no(user_reply):
                    confirmed = False
                else:
                    print("Не понял, отменяю.")
                    _PENDING = None
                    return

            if confirmed:
                real = _PENDING
                _PENDING = None
                _exec_skill(real["intent"], real["args"], real.get("speak"))
            else:
                print("Отменено.")
                _PENDING = None
            return
        else:
            _PENDING = None

    if intent in ("smalltalk", "confirm_action", "cancel_action"):
        if speak:
            print(speak)
        return

    if intent in ("system_shutdown", "system_restart"):
        _PENDING = {"intent": intent, "args": args, "speak": speak, "ts": time.time()}
        print(f"⚠️  КРИТИЧЕСКАЯ КОМАНДА: {_pretty_cmd(cmd)}")
        print("Подтвердите: (да/нет)")
        return

    _exec_skill(intent, args, speak)
