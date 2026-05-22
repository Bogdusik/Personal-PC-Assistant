from __future__ import annotations
import atexit
import gc
import json
import logging
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

import requests

try:
    import keyboard
except ImportError:
    keyboard = None

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["PYTHONIOENCODING"] = "utf-8"

if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())


class _WarningFilter:
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr

    def write(self, message: str) -> None:
        if message and ("pkg_resources" in message or "DeprecationWarning" in message):
            return
        self.original_stderr.write(message)

    def flush(self) -> None:
        self.original_stderr.flush()


sys.stderr = _WarningFilter(sys.stderr)

from assistant.core.state import AssistantState
from assistant.core.exceptions import AudioError, ConfigError
from assistant.recorder import record_push_to_talk
from assistant.asr import init_asr, transcribe, cleanup_asr
from assistant.nlu import nlu_rules
from assistant.runner import run_command
from assistant.skills import APP_ALIASES

_ROOT = Path(__file__).resolve().parent
AUDIO_PATH = str(_ROOT / "last_cmd.wav")
LOG_FILE = str(_ROOT / "assistant.log")
CONFIG_PATH = str(_ROOT / "config.json")


def setup_logging() -> None:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logging.basicConfig(level=logging.DEBUG, handlers=[fh, ch])
    for name in ["faster_whisper", "requests", "urllib3", "sounddevice"]:
        logging.getLogger(name).setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


def load_config(state: AssistantState) -> None:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            state.cfg = json.load(f)
        logger.info("Конфигурация загружена")
    except FileNotFoundError:
        logger.warning("config.json не найден, используем значения по умолчанию")
        state.cfg = {}
    except json.JSONDecodeError as exc:
        logger.error("Некорректный config.json: %s", exc)
        state.cfg = {}

    state.hotkey = state.cfg.get("hotkey", "right shift")
    if not isinstance(state.hotkey, str) or not state.hotkey.strip():
        state.hotkey = "right shift"

    state.mic_device = state.cfg.get("mic_device", None)
    if state.mic_device is not None and not isinstance(state.mic_device, (int, str)):
        state.mic_device = None

    app_aliases = state.cfg.get("app_aliases", {})
    if isinstance(app_aliases, dict):
        APP_ALIASES.clear()
        APP_ALIASES.update(app_aliases)

    model = state.cfg.get("ollama_model")
    if model and isinstance(model, str):
        os.environ["OLLAMA_MODEL"] = model

    logger.info("hotkey=%s mic_device=%s", state.hotkey, state.mic_device)


def cleanup_on_exit(state: AssistantState) -> None:
    if getattr(cleanup_on_exit, "_called", False):
        return
    cleanup_on_exit._called = True
    print("\n" + "=" * 60)
    print("[INFO] Завершаю Ollama...")
    try:
        subprocess.run(["taskkill", "/f", "/im", "ollama.exe"], capture_output=True, timeout=5)
        print("[OK] Ollama завершён.")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"[WARNING] Не удалось завершить Ollama: {exc}")
    try:
        cleanup_asr()
        print("[OK] ASR модель очищена.")
    except Exception as exc:
        print(f"[WARNING] Ошибка очистки ASR: {exc}")
    gc.collect()
    print("[INFO] До свидания!\n" + "=" * 60)


def teach_interactive(state: AssistantState, last_text: str) -> None:
    print("\n=== ОБУЧЕНИЕ НОВОЙ КОМАНДЫ ===")
    commands = [
        "open_app - открыть приложение", "open_browser_search - поиск в браузере",
        "system_volume - управление громкостью", "screenshot - сделать скриншот",
        "open_website - открыть сайт", "minimize_app - свернуть приложение",
        "close_app - закрыть приложение", "system_shutdown - выключить ПК",
        "system_restart - перезагрузить ПК", "system_sleep - режим сна",
        "system_lock - заблокировать ПК", "wifi_toggle - переключить Wi-Fi",
        "brightness_set - установить яркость", "clipboard_copy - скопировать в буфер",
        "clipboard_paste - показать буфер",
    ]
    for i, cmd in enumerate(commands, 1):
        print(f"{i}. {cmd}")

    phrase = input(f"\nФраза для команды [{last_text}]: ").strip() or last_text.strip()
    if not phrase:
        print("❌ Фраза не может быть пустой")
        return

    intent_choice = input("Номер команды (1-15): ").strip()
    intent_map = {str(i): c.split(" - ")[0] for i, c in enumerate(commands, 1)}
    intent = intent_map.get(intent_choice)
    if not intent:
        print("❌ Неверный номер команды")
        return

    args: dict = {}
    if intent == "open_app":
        args["alias"] = input("Алиас приложения: ").strip()
        if not args["alias"]:
            print("❌ Алиас не может быть пустым")
            return
    elif intent == "open_browser_search":
        args["query"] = input("Поисковый запрос: ").strip()
        if not args["query"]:
            print("❌ Запрос не может быть пустым")
            return
    elif intent == "system_volume":
        try:
            level = input("Уровень громкости (0-100): ").strip()
            args["level"] = int(level) if level else 50
            if not 0 <= args["level"] <= 100:
                print("❌ Уровень должен быть 0–100")
                return
        except ValueError:
            print("❌ Введите число")
            return
    elif intent == "open_website":
        url = input("URL сайта: ").strip()
        if not url:
            print("❌ URL не может быть пустым")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        args["url"] = url
    elif intent in ("minimize_app", "close_app"):
        args["alias"] = input("Алиас приложения: ").strip()
        if not args["alias"]:
            print("❌ Алиас не может быть пустым")
            return
    elif intent == "brightness_set":
        try:
            level = input("Уровень яркости (0-100): ").strip()
            args["level"] = int(level) if level else 50
            if not 0 <= args["level"] <= 100:
                print("❌ Уровень должен быть 0–100")
                return
        except ValueError:
            print("❌ Введите число")
            return
    elif intent == "clipboard_copy":
        text = input("Текст для копирования: ").strip()
        if not text:
            print("❌ Текст не может быть пустым")
            return
        args["text"] = text

    match_map = {"1": "equals", "2": "startswith", "3": "contains", "4": "regex"}
    print("\nТип сопоставления:\n1. equals\n2. startswith\n3. contains\n4. regex")
    match_type = match_map.get(input("Тип (1-4): ").strip(), "equals")
    speak = input("Ответ ассистента (опционально): ").strip() or None

    new_command = {"match_type": match_type, "pattern": phrase, "intent": intent, "args": args, "speak": speak}

    existing = [c.get("pattern") for c in state.cfg.get("custom_commands", [])]
    if phrase in existing:
        print(f"⚠️  Команда '{phrase}' уже существует!")
        if input("Перезаписать? (да/нет): ").strip().lower() not in ("да", "yes", "y", "д"):
            print("❌ Отменено")
            return
        state.cfg["custom_commands"] = [c for c in state.cfg.get("custom_commands", []) if c.get("pattern") != phrase]

    state.cfg.setdefault("custom_commands", []).append(new_command)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(state.cfg, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Команда добавлена: '{phrase}' → {intent}")
        load_config(state)
    except OSError as exc:
        print(f"❌ Ошибка сохранения: {exc}")
        logger.error("Ошибка сохранения команды: %s", exc)


def list_commands(state: AssistantState) -> None:
    print("\n=== ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ ===")
    commands = state.cfg.get("custom_commands", [])
    if not commands:
        print("Команды не настроены.")
        return
    for i, cmd in enumerate(commands, 1):
        speak = cmd.get("speak", "")
        print(f"{i}. '{cmd.get('pattern','?')}' → {cmd.get('intent','?')} [{cmd.get('match_type','equals')}]")
        if speak:
            print(f"   Ответ: '{speak}'")


def delete_command(state: AssistantState) -> None:
    print("\n=== УДАЛЕНИЕ КОМАНДЫ ===")
    commands = state.cfg.get("custom_commands", [])
    if not commands:
        print("Команды не настроены.")
        return
    for i, cmd in enumerate(commands, 1):
        print(f"{i}. '{cmd.get('pattern','?')}' → {cmd.get('intent','?')}")
    try:
        choice = int(input("\nНомер для удаления: ").strip())
        if 1 <= choice <= len(commands):
            deleted = commands.pop(choice - 1)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(state.cfg, f, ensure_ascii=False, indent=2)
            print(f"✅ Удалено: '{deleted.get('pattern')}'")
            load_config(state)
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Введите число")
    except OSError as exc:
        print(f"❌ Ошибка: {exc}")


def chat_with_assistant(text: str, state: AssistantState, max_retries: int = 3) -> str:
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    for attempt in range(max_retries):
        try:
            if requests.get(f"{ollama_url}/api/tags", timeout=3).status_code == 200:
                break
        except requests.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return "Ollama не запущен. Перезапустите ассистента."
    else:
        return "Ollama недоступен."

    prompt = f"Ты - персональный голосовой ассистент для ПК. Отвечай кратко и дружелюбно на русском языке.\n\nПользователь: {text}\nАссистент:"
    payload = {
        "model": state.cfg.get("ollama_model", "gemma3:12b"),
        "prompt": prompt,
        "stream": False,
        "temperature": 0.7,
        "options": {"num_predict": 100},
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=15)
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                return answer or "Не понял, повторите."
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    return "Ошибка подключения к Ollama."


def start_ollama(state: AssistantState) -> bool:
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        state.ollama_process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for i in range(10):
            try:
                if requests.get(f"{ollama_url}/api/tags", timeout=2).status_code == 200:
                    return True
            except requests.ConnectionError:
                pass
            time.sleep(1)
            if i % 3 == 0:
                print(f"⏳ Ожидание Ollama... {i+1}/10")
        print("⚠️  Ollama не отвечает, но процесс запущен.")
        return True
    except (FileNotFoundError, OSError) as exc:
        print(f"❌ Ollama не найден: {exc}")
        return False


def main() -> None:
    state = AssistantState()
    atexit.register(cleanup_on_exit, state)

    print("=" * 60)
    print("PERSONAL PC ASSISTANT — ГОЛОСОВОЙ АССИСТЕНТ")
    print("=" * 60)

    load_config(state)

    print("[INFO] Запускаю Ollama...")
    if not start_ollama(state):
        print("[WARNING] Ollama не запущен. Чат недоступен.")
    else:
        print("[OK] Ollama запущен.")

    print("🎤 Загружаю ASR...", flush=True)
    asr_model = None
    try:
        asr_model = init_asr()
        print("✅ ASR загружен!", flush=True)
    except AudioError as exc:
        print(f"❌ Ошибка загрузки ASR: {exc}", flush=True)
        print("⚠️  Продолжаю без голосового распознавания...", flush=True)

    print("\n" + "=" * 60, flush=True)
    print(f"🎯 {state.hotkey.upper()} — голосовые команды", flush=True)
    print(f"📚 Ctrl+4 — обучить команду", flush=True)
    print("❌ Ctrl+C — выход", flush=True)
    print("=" * 60, flush=True)

    teach_flag = False

    def on_teach() -> None:
        nonlocal teach_flag
        teach_flag = True

    if keyboard:
        try:
            keyboard.add_hotkey("ctrl+4", on_teach)
        except Exception as exc:
            logger.warning("Не удалось зарегистрировать Ctrl+4: %s", exc)

    cycle_count = 0
    MEMORY_CLEANUP_INTERVAL = 50

    while True:
        if teach_flag:
            teach_flag = False
            teach_interactive(state, state.last_text)
            time.sleep(0.1)
            continue

        try:
            if asr_model is None:
                print("⚠️  ASR недоступен. Нажмите Ctrl+C для выхода")
                time.sleep(5)
                continue

            path = record_push_to_talk(AUDIO_PATH, hotkey=state.hotkey, mic_device=state.mic_device)
            if not path:
                time.sleep(0.01)
                continue

            try:
                if os.path.getsize(path) < 1000:
                    print("⚠️ Аудио слишком короткое, пропускаю", flush=True)
                    continue

                text = transcribe(asr_model, path)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

            if not text or len(text.strip()) < 2:
                print("⚠️ Речь не распознана", flush=True)
                continue

            state.last_text = text
            print(f"🎤 Распознано: {text}", flush=True)

            cmd = nlu_rules(text)
            intent = cmd.get("intent", "")

            if intent and intent != "smalltalk":
                if intent == "system_status":
                    _show_status(state)
                elif intent == "list_commands":
                    list_commands(state)
                elif intent == "delete_command":
                    delete_command(state)
                elif intent == "teach_command":
                    teach_interactive(state, state.last_text)
                elif intent == "smart_search":
                    args = cmd.get("args", {})
                    app_name = args.get("app_name", "")
                    context = args.get("context", "")
                    if app_name:
                        from assistant.skills.app_control import _smart_search_with_context, _auto_add_app_to_config
                        found = _smart_search_with_context(app_name, context)
                        if found:
                            print(f"✅ Найдено: {found}", flush=True)
                            _auto_add_app_to_config(app_name, found)
                        else:
                            print(f"❌ Не найдено: {app_name}", flush=True)
                else:
                    print(f"⚡ {intent}", flush=True)
                    run_command(cmd)
                    if cmd.get("speak"):
                        print(f"🔊 {cmd['speak']}", flush=True)
            else:
                print("💬 Общение...", flush=True)
                response = chat_with_assistant(text, state)
                print(f"🤖 {response}", flush=True)

            print("-" * 60, flush=True)

            cycle_count += 1
            if cycle_count >= MEMORY_CLEANUP_INTERVAL:
                cycle_count = 0
                gc.collect()

        except AudioError as exc:
            logger.error("Ошибка аудио: %s", exc)
            time.sleep(0.1)
        except Exception as exc:
            logger.error("Ошибка обработки: %s", exc)
            time.sleep(0.1)


def _show_status(state: AssistantState) -> None:
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    print("\n" + "=" * 50)
    print("📊 СТАТУС СИСТЕМЫ")
    print("=" * 50)
    print(f"📝 Пользовательских команд: {len(state.cfg.get('custom_commands', []))}")
    print(f"📱 Настроенных приложений: {len(state.cfg.get('app_aliases', {}))}")
    print(f"🎯 Горячая клавиша: {state.hotkey}")
    print(f"🎤 Микрофон: {'Настроен' if state.mic_device else 'По умолчанию'}")
    try:
        if requests.get(f"{ollama_url}/api/tags", timeout=2).status_code == 200:
            print("🤖 Ollama: ✅ Работает")
        else:
            print("🤖 Ollama: ⚠️ Не отвечает")
    except requests.ConnectionError:
        print("🤖 Ollama: ❌ Не запущен")
    print("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Критическая ошибка: {exc}")
        logger.error("Fatal: %s", exc)
