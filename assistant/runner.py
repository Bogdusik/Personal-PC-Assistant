import time, re
from .skills import SKILLS

_PENDING = None
CONFIRM_THRESHOLD = 0.65
CONFIRM_TIMEOUT_SEC = 25

_LAST_COMMAND = None
_COMMAND_COOLDOWN = 1.0

_YES_PATTERNS = (
    r"\bда\b", r"\bok\b", r"\bокей\b", r"\bугу\b", r"\бага\b",
    r"\bага\b", r"\bподтверждаю\b", r"\bдавай\b", r"\bконечно\b",
    r"\bпоехали\b", r"\bго\b", r"\byes\b", r"\bладно\b"
)
_NO_PATTERNS = (
    r"\bнет\b", r"\bотмена\b", r"\bотмени\b", r"\bне надо\b",
    r"\bстоп\b", r"\bне\b", r"\bno\b", r"\bне делай\b"
)

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
    import logging
    fn = SKILLS.get(intent)
    if not fn:
        print("Неизвестная команда:", intent)
        logging.error(f"Неизвестная команда: {intent}")
        return
    try:
        logging.info(f"Выполняю навык: {intent} с аргументами: {args}")
        fn(**args)
        logging.info(f"Навык {intent} выполнен успешно")
    except TypeError as e:
        print(f"Не удалось выполнить ({intent}): {e}")
        logging.error(f"Ошибка типа при выполнении {intent}: {e}")
        return
    except Exception as e:
        print(f"Ошибка при выполнении ({intent}): {e}")
        logging.error(f"Ошибка при выполнении {intent}: {e}")
        return
    if speak:
        print(f"[OK] {speak}", flush=True)
        logging.info(f"Озвучиваю результат: {speak}")

def run_command(cmd: dict):
    import logging
    global _PENDING, _LAST_COMMAND

    if not isinstance(cmd, dict) or "intent" not in cmd:
        logging.warning("Получена некорректная команда")
        return

    intent = cmd["intent"]
    args = cmd.get("args", {})
    speak = cmd.get("speak")
    conf = float(cmd.get("confidence", 1.0))
    
    logging.info(f"Получена команда: {intent}, уверенность: {conf:.2f}")
    
    current_time = time.time()
    command_key = f"{intent}:{str(args)}"
    
    if _LAST_COMMAND:
        last_time, last_key = _LAST_COMMAND
        if (command_key == last_key and 
            current_time - last_time < _COMMAND_COOLDOWN):
            print(f"[WAIT] Команда уже выполняется, подождите...")
            return
    
    _LAST_COMMAND = (current_time, command_key)

    if _PENDING and (time.time() - _PENDING.get("ts", 0) > CONFIRM_TIMEOUT_SEC):
        _PENDING = None

    if _PENDING:
        if intent == "smalltalk":
            user_reply = (args.get("text") or "").strip()
            if _is_yes(user_reply):
                real = _PENDING
                _PENDING = None
                _exec_skill(real["intent"], real["args"], real.get("speak"))
                return
            elif _is_no(user_reply):
                print("Отменено.")
                _PENDING = None
                return
            else:
                print("Не понял, отменяю.")
                _PENDING = None
                return
        else:
            _PENDING = None

    if intent == "smalltalk":
        if speak:
            print(speak)
        return

    # Всегда требуем подтверждения для критических команд
    if intent in ["system_shutdown", "system_restart"]:
        _PENDING = {"intent": intent, "args": args, "speak": speak, "ts": time.time()}
        print(f"⚠️  КРИТИЧЕСКАЯ КОМАНДА: {_pretty_cmd(cmd)}")
        print("Подтвердите выполнение: (да/нет)")
        return
    
    if conf < CONFIRM_THRESHOLD and intent in ["files.delete"]:
        _PENDING = {"intent": intent, "args": args, "speak": speak, "ts": time.time()}
        print(f"Подтвердить: {_pretty_cmd(cmd)}? (да/нет)")
        return

    _exec_skill(intent, args, speak)