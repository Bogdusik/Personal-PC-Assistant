# assistant/runner.py
import time
from jsonschema import validate
from .nlu import INTENT_SCHEMA
from .skills import SKILLS

# pending confirmation
_PENDING = None                # dict | None: {"intent","args","speak","ts"}
CONFIRM_THRESHOLD = 0.65       # ниже — спрашиваем подтверждение
CONFIRM_TIMEOUT_SEC = 25       # сколько ждать "да/нет", потом сбрасывать

# словари подтверждений/отмен
_YES_PATTERNS = (
    r"\bда\b", r"\bok\b", r"\bокей\b", r"\bугу\b", r"\бага\b",
    r"\bага\b", r"\bподтверждаю\b", r"\bдавай\b", r"\bконечно\b",
    r"\bпоехали\b", r"\bго\b", r"\byes\b", r"\bладно\b"
)
_NO_PATTERNS = (
    r"\bнет\b", r"\bотмена\b", r"\bотмени\b", r"\bне надо\b",
    r"\bстоп\b", r"\bне\b", r"\bno\b", r"\bне делай\b"
)

import re
_YES_RE = re.compile("|".join(_YES_PATTERNS), re.IGNORECASE)
_NO_RE  = re.compile("|".join(_NO_PATTERNS),  re.IGNORECASE)

def _is_yes(text: str) -> bool:
    return bool(_YES_RE.search((text or "").strip()))

def _is_no(text: str) -> bool:
    return bool(_NO_RE.search((text or "").strip()))

def _pretty_cmd(cmd: dict) -> str:
    intent = cmd.get("intent")
    args = cmd.get("args", {})
    if intent == "open_app":
        return f"Запустить приложение: {args.get('alias')}"
    if intent == "open_browser_search":
        q = args.get("query")
        return f"Открыть поиск: «{q}»" if q else "Открыть поиск"
    if intent == "system_volume":
        lvl = args.get("level")
        return f"Поставить громкость: {lvl}%"
    if intent == "screenshot":
        return "Сделать скриншот"
    return intent or "команда"

def _exec_skill(intent: str, args: dict, speak: str | None):
    fn = SKILLS.get(intent)
    if not fn:
        print("Неизвестная команда:", intent)
        return
    try:
        fn(**args)
    except TypeError as e:
        # например, не те аргументы
        print(f"Не удалось выполнить ({intent}): {e}")
        return
    except Exception as e:
        print(f"Ошибка при выполнении ({intent}): {e}")
        return
    if speak:
        print(speak)

def run_command(cmd: dict):
    """
    Принимает JSON-команду от NLU, при необходимости спрашивает подтверждение и выполняет.
    Ожидает поля:
      - intent, args (по схеме)
      - speak (опционально)
      - confidence (0..1), normalized_text (опц.)
    """
    global _PENDING

    validate(cmd, INTENT_SCHEMA)

    intent = cmd["intent"]
    args = cmd["args"] or {}
    speak = cmd.get("speak")
    conf  = float(cmd.get("confidence", 1.0))
    # norm = cmd.get("normalized_text")  # если понадобится для логов/отладки

    # 0) если висит ожидание подтверждения — проверь таймаут
    if _PENDING and (time.time() - _PENDING.get("ts", 0) > CONFIRM_TIMEOUT_SEC):
        print("Подтверждение не получено. Отменяю.")
        _PENDING = None

    # 1) если ждём подтверждение — интерпретируем текущую реплику как «да/нет»
    if _PENDING:
        if intent == "smalltalk":
            user_reply = (args.get("text") or "").strip()
            if _is_yes(user_reply):
                real = _PENDING; _PENDING = None
                _exec_skill(real["intent"], real["args"], real.get("speak"))
                return
            if _is_no(user_reply):
                print("Ок, отменяю.")
                _PENDING = None
                return
            # ни «да», ни «нет»
            print("Не понял подтверждение, отменяю.")
            _PENDING = None
            return
        else:
            # пришла новая явная команда — отменяем ожидание и идём дальше
            _PENDING = None

    # 2) smalltalk — ничего исполнять не нужно
    if intent == "smalltalk":
        out = speak or args.get("text")
        if out:
            print(out)
        return

    # 3) при низкой уверенности — просим подтверждение
    if conf < CONFIRM_THRESHOLD:
        _PENDING = {"intent": intent, "args": args, "speak": speak, "ts": time.time()}
        print(f"Понял так: { _pretty_cmd(cmd) }. Подтвердить? (да/нет)")
        return

    # 4) выполнить сразу
    _exec_skill(intent, args, speak)
