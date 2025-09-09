# main.py
import json, logging, os, time
import keyboard

from assistant.recorder import record_push_to_talk
from assistant.asr import init_asr, transcribe
from assistant.nlu import nlu_rules
from assistant.runner import run_command
from assistant.skills import APP_ALIASES

AUDIO_PATH   = "last_cmd.wav"
LOG_FILE     = "assistant.log"
CONFIG_PATH  = "config.json"
DEBUG_PRINT  = False  # True — печать распознанных команд

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

CFG = {}
HOTKEY = "right shift"
CREATE_COMMAND_HOTKEY = "f9"
MIC_DEVICE = None
_LAST_TEXT = ""

ALLOWED_INTENTS = [
    "open_app",
    "open_browser_search",
    "system_volume",
    "screenshot",
    "smalltalk",
    "open_website",  # если такой скилл есть — ок; если нет, просто не используйте
]

def load_config():
    """Читает config.json, применяет настройки и обновляет алиасы и модель."""
    global CFG, HOTKEY, MIC_DEVICE, CREATE_COMMAND_HOTKEY
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                CFG = json.load(f)
        except Exception as e:
            print("Не удалось прочитать config.json:", e)
            CFG = {}
    else:
        CFG = {}

    HOTKEY = CFG.get("hotkey", "right shift")
    MIC_DEVICE = CFG.get("mic_device", None)
    CREATE_COMMAND_HOTKEY = CFG.get("create_command_hotkey", "f9")

    # алиасы приложений
    APP_ALIASES.clear()
    APP_ALIASES.update(CFG.get("app_aliases", {}))

    # модель для nlu через ENV (nlu.py берёт ENV сначала)
    model = CFG.get("ollama_model")
    if model:
        os.environ["OLLAMA_MODEL"] = str(model)

    return CFG

def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("✓ Конфиг сохранён.")
    except Exception as e:
        print("Не удалось сохранить config.json:", e)

def _load_cfg_raw():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def teach_interactive(last_text: str):
    """Интерактивное добавление правила в config.json -> custom_commands."""
    print("\n=== РЕЖИМ ОБУЧЕНИЯ ===")
    cfg = _load_cfg_raw()
    customs = list(cfg.get("custom_commands") or [])

    phrase = input(f"Фраза-триггер [{last_text}]: ").strip() or (last_text or "").strip()
    if not phrase:
        print("Пустая фраза, выхожу.")
        return

    print("Тип сопоставления: 1=equals  2=startswith  3=contains  4=regex")
    mt_choice = (input("Выбери (1-4) [1]: ").strip() or "1")
    match_type = {"1":"equals","2":"startswith","3":"contains","4":"regex"}.get(mt_choice,"equals")

    print("Доступные intents:", ", ".join(ALLOWED_INTENTS))
    intent = input("Intent: ").strip()
    if intent not in ALLOWED_INTENTS:
        print("Неизвестный intent.")
        return

    raw_args = input('Args (JSON) например {"alias":"notepad"} или {}: ').strip() or "{}"
    try:
        args = json.loads(raw_args)
        if not isinstance(args, dict):
            raise ValueError()
    except Exception:
        print("Неверный JSON для args.")
        return

    speak = input("Speak (короткий ответ; можно пусто): ").strip() or None

    rule = {
        "match_type": match_type,
        "pattern": phrase,
        "intent": intent,
        "args": args,
        "speak": speak
    }
    customs.append(rule)
    cfg["custom_commands"] = customs
    save_config(cfg)

    # сразу перечитываем и применяем (nlu.py сам подхватит по mtime)
    load_config()
    print(f"✓ Добавлено правило: [{match_type}] '{phrase}' → {intent} {args}\n")

def main():
    global _LAST_TEXT

    load_config()

    print("Гружу ASR...")
    asr_model = init_asr()
    print(
        f"Ассистент запущен. Удерживай {HOTKEY.upper()} чтобы говорить. "
        f"{CREATE_COMMAND_HOTKEY.upper()} — обучить, F5 — перечитать конфиг. Ctrl+C — выйти."
    )

    # --- регистрация хоткеев ---
    teach_flag = {"pending": False}
    reload_flag = {"pending": False}

    def _on_teach():
        teach_flag["pending"] = True

    def _on_reload():
        reload_flag["pending"] = True

    # глобальные хоткеи (работают даже без фокуса в терминале)
    keyboard.add_hotkey(CREATE_COMMAND_HOTKEY, _on_teach)  # например, "f4"
    keyboard.add_hotkey("f5", _on_reload)

    while True:
        # обработка хоткеев
        if teach_flag["pending"]:
            teach_flag["pending"] = False
            teach_interactive(_LAST_TEXT)
            time.sleep(0.2)

        if reload_flag["pending"]:
            reload_flag["pending"] = False
            load_config()
            print("✓ Конфиг перечитан.")
            time.sleep(0.2)

        # запись и распознавание
        path = record_push_to_talk(AUDIO_PATH, hotkey=HOTKEY, mic_device=MIC_DEVICE)
        if not path:
            time.sleep(0.01)
            continue

        text = transcribe(asr_model, path)
        if not text:
            print("Не разобрал речь.")
            time.sleep(0.01)
            continue

        _LAST_TEXT = text

        cmd = nlu_rules(text)
        if DEBUG_PRINT:
            try:
                print("DEBUG CMD:", json.dumps(cmd, ensure_ascii=False))
            except Exception:
                print("DEBUG CMD (raw):", cmd)
        run_command(cmd)

        time.sleep(0.01)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПока!")
