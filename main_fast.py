import warnings
import os
import sys
import json
import logging
import time
import subprocess
import atexit

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

    # Гарантируем вывод в консоль в UTF-8 на Windows
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

class WarningFilter:
    """Фильтр для подавления шумных предупреждений от сторонних библиотек."""

    def __init__(self, original_stderr):
        self.original_stderr = original_stderr

    def write(self, message):
        if not message:
            return
        if "pkg_resources" in message or "DeprecationWarning" in message:
            return
        self.original_stderr.write(message)

    def flush(self):
        self.original_stderr.flush()

sys.stderr = WarningFilter(sys.stderr)

from assistant.recorder import record_push_to_talk
from assistant.asr import init_asr, transcribe
from assistant.nlu import nlu_rules
from assistant.runner import run_command
from assistant.skills import APP_ALIASES

AUDIO_PATH = "last_cmd.wav"
LOG_FILE = "assistant.log"
CONFIG_PATH = "config.json"

def setup_logging():
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    
    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
    
    for logger_name in ["faster_whisper", "requests", "urllib3", "sounddevice"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

setup_logging()


CFG = {}
HOTKEY = "right shift"
MIC_DEVICE = None
_LAST_TEXT = ""
ollama_process = None

def cleanup_on_exit():
    global ollama_process
    try:
        if hasattr(cleanup_on_exit, '_called'):
            return
        cleanup_on_exit._called = True
        print("\n" + "=" * 60)
        print("[INFO] Завершаю Ollama...")
        subprocess.run(["taskkill", "/f", "/im", "ollama.exe"], capture_output=True, timeout=5)
        print("[OK] Ollama завершен.")
        
        try:
            from assistant.asr import cleanup_asr
            cleanup_asr()
            print("[OK] ASR модель очищена из памяти.")
        except Exception as e:
            print(f"[WARNING] Ошибка очистки ASR: {e}")
        
        import gc
        gc.collect()
        print("[OK] Память очищена.")
        print("[INFO] До свидания!")
        print("=" * 60)
    except Exception as e:
        print(f"[ERROR] Ошибка завершения Ollama: {e}")


def load_config():
    global CFG, HOTKEY, MIC_DEVICE
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            CFG = json.load(f)
        logging.info("Конфигурация загружена успешно")
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        logging.error(f"Ошибка загрузки конфига: {e}")
        CFG = {}
    
    HOTKEY = CFG.get("hotkey", "right shift")
    if not isinstance(HOTKEY, str) or not HOTKEY.strip():
        HOTKEY = "right shift"
    
    MIC_DEVICE = CFG.get("mic_device", None)
    if MIC_DEVICE is not None and not isinstance(MIC_DEVICE, (int, str)):
        MIC_DEVICE = None
    
    app_aliases = CFG.get("app_aliases", {})
    if isinstance(app_aliases, dict):
        APP_ALIASES.clear()
        APP_ALIASES.update(app_aliases)
    
    model = CFG.get("ollama_model")
    if model and isinstance(model, str) and model.strip():
        os.environ["OLLAMA_MODEL"] = str(model)
        logging.info(f"Установлена модель Ollama: {model}")
    
    custom_commands = CFG.get("custom_commands", [])
    if isinstance(custom_commands, list):
        valid_commands = [cmd for cmd in custom_commands 
                         if isinstance(cmd, dict) and 
                         all(field in cmd for field in ["match_type", "pattern", "intent"])]
        if len(valid_commands) != len(custom_commands):
            logging.info(f"Загружено {len(valid_commands)} из {len(custom_commands)} команд")
    
    logging.info(f"Конфигурация загружена: hotkey={HOTKEY}, mic_device={MIC_DEVICE}")

def teach_interactive(last_text: str):
    print(f"\n=== ОБУЧЕНИЕ НОВОЙ КОМАНДЫ ===")
    commands = [
        "open_app - открыть приложение", "open_browser_search - поиск в браузере",
        "system_volume - управление громкостью", "screenshot - сделать скриншот",
        "open_website - открыть сайт", "minimize_app - свернуть приложение",
        "close_app - закрыть приложение", "system_shutdown - выключить ПК",
        "system_restart - перезагрузить ПК", "system_sleep - режим сна",
        "system_lock - заблокировать ПК", "wifi_toggle - переключить Wi-Fi",
        "brightness_set - установить яркость", "clipboard_copy - скопировать в буфер",
        "clipboard_paste - показать буфер"
    ]
    
    for i, cmd in enumerate(commands, 1):
        print(f"{i}. {cmd}")
    print()
    
    phrase = input(f"Фраза для команды [{last_text}]: ").strip() or last_text.strip()
    if not phrase:
        print("❌ Фраза не может быть пустой")
        return
    
    intent_choice = input("Номер команды (1-15): ").strip()
    intent_map = {str(i): cmd.split(" - ")[0] for i, cmd in enumerate(commands, 1)}
    
    intent = intent_map.get(intent_choice)
    if not intent:
        print("❌ Неверный номер команды")
        return
    
    print(f"\nВыбран тип: {intent}")
    
    args = {}
    
    if intent == "open_app":
        print("Доступные приложения:")
        for alias in APP_ALIASES.keys():
            print(f"  - {alias}")
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
                print("❌ Уровень должен быть от 0 до 100")
                return
        except ValueError:
            print("❌ Неверный формат числа")
            return
            
    elif intent == "open_website":
        url = input("URL сайта: ").strip()
        if not url:
            print("❌ URL не может быть пустым")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        args["url"] = url
        
    elif intent in ["minimize_app", "close_app"]:
        print("Доступные приложения:")
        for alias in APP_ALIASES.keys():
            print(f"  - {alias}")
        args["alias"] = input("Алиас приложения: ").strip()
        if not args["alias"]:
            print("❌ Алиас не может быть пустым")
            return
            
    elif intent == "brightness_set":
        try:
            level = input("Уровень яркости (0-100): ").strip()
            args["level"] = int(level) if level else 50
            if not 0 <= args["level"] <= 100:
                print("❌ Уровень должен быть от 0 до 100")
                return
        except ValueError:
            print("❌ Неверный формат числа")
            return
            
    elif intent == "clipboard_copy":
        text = input("Текст для копирования: ").strip()
        if not text:
            print("❌ Текст не может быть пустым")
            return
        args["text"] = text
    
    print(f"\nТип сопоставления:")
    print("1. equals - точное совпадение")
    print("2. startswith - начинается с")
    print("3. contains - содержит")
    print("4. regex - регулярное выражение")
    
    match_choice = input("Тип сопоставления (1-4): ").strip()
    match_map = {
        "1": "equals",
        "2": "startswith", 
        "3": "contains",
        "4": "regex"
    }
    match_type = match_map.get(match_choice, "equals")
    
    speak = input("Ответ ассистента (опционально): ").strip() or None
    
    new_command = {
        "match_type": match_type,
        "pattern": phrase,
        "intent": intent,
        "args": args,
        "speak": speak
    }
    
    existing_patterns = [cmd.get("pattern") for cmd in CFG.get("custom_commands", [])]
    if phrase in existing_patterns:
        print(f"⚠️  Команда с фразой '{phrase}' уже существует!")
        overwrite = input("Перезаписать? (да/нет): ").strip().lower()
        if overwrite not in ["да", "yes", "y", "д"]:
            print("❌ Команда не добавлена")
            return
        
        CFG["custom_commands"] = [cmd for cmd in CFG.get("custom_commands", []) if cmd.get("pattern") != phrase]
    
    if "custom_commands" not in CFG:
        CFG["custom_commands"] = []
    
    CFG["custom_commands"].append(new_command)
    
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CFG, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Команда успешно добавлена!")
        print(f"   Фраза: '{phrase}'")
        print(f"   Тип: {intent}")
        print(f"   Сопоставление: {match_type}")
        if speak:
            print(f"   Ответ: '{speak}'")
        
        load_config()
        print("✅ Конфигурация обновлена")
        
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        logging.error(f"Ошибка сохранения команды: {e}")

def list_commands():
    print(f"\n=== СПИСОК ПОЛЬЗОВАТЕЛЬСКИХ КОМАНД ===")
    commands = CFG.get("custom_commands", [])
    
    if not commands:
        print("❌ Пользовательские команды не найдены")
        return
    
    for i, cmd in enumerate(commands, 1):
        pattern = cmd.get("pattern", "N/A")
        intent = cmd.get("intent", "N/A")
        match_type = cmd.get("match_type", "equals")
        speak = cmd.get("speak", "")
        
        print(f"{i}. Фраза: '{pattern}'")
        print(f"   Тип: {intent}")
        print(f"   Сопоставление: {match_type}")
        if speak:
            print(f"   Ответ: '{speak}'")
        print()

def delete_command():
    print(f"\n=== УДАЛЕНИЕ КОМАНДЫ ===")
    commands = CFG.get("custom_commands", [])
    
    if not commands:
        print("❌ Пользовательские команды не найдены")
        return
    
    print("Доступные команды:")
    for i, cmd in enumerate(commands, 1):
        pattern = cmd.get("pattern", "N/A")
        intent = cmd.get("intent", "N/A")
        print(f"{i}. '{pattern}' → {intent}")
    
    try:
        choice = int(input("\nНомер команды для удаления: ").strip())
        if 1 <= choice <= len(commands):
            deleted_cmd = commands.pop(choice - 1)
            
            # Сохраняем изменения
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(CFG, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Команда '{deleted_cmd.get('pattern')}' удалена")
            load_config()
        else:
            print("❌ Неверный номер команды")
    except ValueError:
        print("❌ Неверный формат номера")
    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")

def chat_with_assistant(text: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            if requests.get("http://localhost:11434/api/tags", timeout=3).status_code == 200:
                break
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return "Ollama недоступен. Попробуйте позже."
        except:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return "Ollama не запущен. Перезапустите ассистента."
    
    prompt = f"Ты - персональный голосовой ассистент для ПК. Отвечай кратко и дружелюбно на русском языке.\n\nПользователь: {text}\nАссистент:"
    payload = {
        "model": CFG.get("ollama_model", "gemma3:12b"),
        "prompt": prompt,
        "stream": False,
        "temperature": 0.7,
        "options": {"num_predict": 100}
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=15)
            if response.status_code == 200:
                answer = response.json().get('response', '').strip()
                return answer if answer else "Не понял, повторите вопрос."
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return "Ошибка обработки запроса"
        except:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return "Ошибка подключения к Ollama."
    return "Не удалось получить ответ от ассистента."

def start_ollama():
    global ollama_process
    try:
        ollama_process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for i in range(10):
            try:
                if requests.get("http://localhost:11434/api/tags", timeout=2).status_code == 200:
                    return True
            except:
                pass
            time.sleep(1)
            if i % 3 == 0:
                print(f"⏳ Ожидание Ollama... {i+1}/10")
        print("⚠️  Ollama не отвечает, но процесс запущен.")
        return True
    except Exception as e:
        print(f"❌ Ошибка запуска Ollama: {e}")
        return False

def main():
    global _LAST_TEXT
    
    atexit.register(cleanup_on_exit)
    
    print("=" * 60)
    print("PERSONAL PC ASSISTANT - ГОЛОСОВОЙ АССИСТЕНТ")
    print("=" * 60)
    
    load_config()
    
    print("[INFO] Запускаю Ollama...")
    if not start_ollama():
        print("[WARNING] Ollama не запущен. Чат недоступен.")
    else:
        print("[OK] Ollama запущен и готов.")
    
    print("🎤 Загружаю ASR...", flush=True)
    try:
        asr_model = init_asr()
        print("✅ ASR загружен успешно!", flush=True)
    except Exception as e:
        print(f"❌ Ошибка загрузки ASR: {e}", flush=True)
        print("⚠️  Продолжаю без голосового распознавания...", flush=True)
        asr_model = None
    
    print("\n" + "=" * 60, flush=True)
    print("🎉 АССИСТЕНТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!", flush=True)
    print("=" * 60, flush=True)
    print(f"🎯 {HOTKEY.upper()} - голосовые команды и общение", flush=True)
    print(f"📚 Ctrl+4 - обучить новую команду (или скажите 'новая команда')", flush=True)
    print(f"🎤 Скажите 'статус' - показать статус системы", flush=True)
    print(f"🎤 Скажите 'команды' - показать все команды", flush=True)
    print(f"🎤 Скажите 'удали команду' - удалить команду", flush=True)
    print("❌ Ctrl+C - выход (Ollama будет завершен автоматически)", flush=True)
    print("=" * 60, flush=True)
    print("", flush=True)
    print(f"⏳ Жду нажатия {HOTKEY.upper()} для записи...", flush=True)
    
    teach_flag = False
    
    def on_teach():
        nonlocal teach_flag
        teach_flag = True
    
    try:
        if keyboard:
            keyboard.add_hotkey("ctrl+4", on_teach)
            print("✅ Горячая клавиша Ctrl+4 зарегистрирована")
        else:
            print("⚠️ Модуль keyboard не установлен. Горячие клавиши недоступны.")
            print("💡 Установите: pip install keyboard")
    except Exception as e:
        print(f"⚠️ Ошибка регистрации клавиши: {e}")
        print("💡 Попробуйте запустить от имени администратора")
    
    print("🔄 Вхожу в основной цикл...", flush=True)
    
    cycle_count = 0
    MEMORY_CLEANUP_INTERVAL = 50
    
    while True:
        if teach_flag:
            teach_flag = False
            teach_interactive(_LAST_TEXT)
            time.sleep(0.1)
            continue
        
        try:
            if asr_model is None:
                print("⚠️  ASR недоступен. Нажмите Ctrl+C для выхода")
                time.sleep(5)
                continue
                
            path = record_push_to_talk(AUDIO_PATH, hotkey=HOTKEY, mic_device=MIC_DEVICE)
            if not path:
                time.sleep(0.01)
                continue
            
            file_size = os.path.getsize(path)
            logging.info(f"Записан аудио файл: {path}, размер: {file_size} байт")
            
            if file_size < 1000:
                print("⚠️ Аудио файл слишком мал, пропускаю", flush=True)
                logging.info("Аудио файл слишком мал, пропускаю")
                continue
            
            text = transcribe(asr_model, path)
            if not text or len(text.strip()) < 2:
                print("⚠️ Речь не распознана или слишком короткая", flush=True)
                continue
            
            _LAST_TEXT = text
            print(f"🎤 Распознано: {text}", flush=True)
            logging.info(f"Распознанная речь: {text}")
            
            cmd = nlu_rules(text)
            if cmd and cmd.get("intent") != "smalltalk":
                # Проверяем специальные команды управления
                if cmd.get("intent") in ["confirm_action", "cancel_action"]:
                    print(f"⚡ Обрабатываю команду подтверждения: {cmd.get('intent', 'unknown')}", flush=True)
                    logging.info(f"Обрабатываю команду подтверждения: {cmd.get('intent', 'unknown')}")
                    run_command(cmd)
                    if cmd.get("speak"):
                        print(f"🔊 Ответ: {cmd.get('speak')}", flush=True)
                        logging.info(f"Ответ команды: {cmd.get('speak')}")
                elif cmd.get("intent") == "system_status":
                    print("⚡ Показываю статус системы...", flush=True)
                    print("\n" + "=" * 50)
                    print("📊 СТАТУС СИСТЕМЫ")
                    print("=" * 50)
                    
                    # Показываем статистику
                    custom_commands = CFG.get("custom_commands", [])
                    app_aliases = CFG.get("app_aliases", {})
                    print(f"📝 Пользовательских команд: {len(custom_commands)}")
                    print(f"📱 Настроенных приложений: {len(app_aliases)}")
                    print(f"🎯 Горячая клавиша: {HOTKEY}")
                    print(f"🎤 Микрофон: {'Настроен' if MIC_DEVICE else 'По умолчанию'}")
                    
                    # Проверяем Ollama
                    try:
                        response = requests.get("http://localhost:11434/api/tags", timeout=2)
                        if response.status_code == 200:
                            print("🤖 Ollama: ✅ Работает")
                        else:
                            print("🤖 Ollama: ⚠️ Не отвечает")
                    except:
                        print("🤖 Ollama: ❌ Не запущен")
                    
                    print("=" * 50)
                elif cmd.get("intent") == "list_commands":
                    print("⚡ Показываю список команд...", flush=True)
                    print(f"\n=== СПИСОК ПОЛЬЗОВАТЕЛЬСКИХ КОМАНД ===")
                    commands = CFG.get("custom_commands", [])
                    
                    if not commands:
                        print("❌ Пользовательские команды не найдены")
                    else:
                        for i, cmd in enumerate(commands, 1):
                            pattern = cmd.get("pattern", "N/A")
                            intent = cmd.get("intent", "N/A")
                            match_type = cmd.get("match_type", "equals")
                            speak = cmd.get("speak", "")
                            
                            print(f"{i}. Фраза: '{pattern}'")
                            print(f"   Тип: {intent}")
                            print(f"   Сопоставление: {match_type}")
                            if speak:
                                print(f"   Ответ: '{speak}'")
                            print()
                elif cmd.get("intent") == "delete_command":
                    print("⚡ Удаляю команду...", flush=True)
                    delete_command()
                elif cmd.get("intent") == "teach_command":
                    print("⚡ Создаю новую команду...", flush=True)
                    teach_interactive(_LAST_TEXT)
                elif cmd.get("intent") == "smart_search":
                    print("🧠 Запускаю умный поиск...", flush=True)
                    args = cmd.get("args", {})
                    app_name = args.get("app_name", "")
                    context = args.get("context", "")
                    
                    if app_name:
                        from assistant.skills.skills import _smart_search_with_context, _auto_add_app_to_config
                        found_path = _smart_search_with_context(app_name, context)
                        if found_path:
                            print(f"✅ Найдено: {found_path}", flush=True)
                            _auto_add_app_to_config(app_name, found_path)
                        else:
                            print(f"❌ Не найдено: {app_name}", flush=True)
                    else:
                        print("❌ Не указано название приложения", flush=True)
                else:
                    print(f"⚡ Выполняю команду: {cmd.get('intent', 'unknown')}", flush=True)
                    logging.info(f"Выполняю команду: {cmd.get('intent', 'unknown')} с аргументами: {cmd.get('args', {})}")
                    run_command(cmd)
                    if cmd.get("speak"):
                        print(f"🔊 Ответ: {cmd.get('speak')}", flush=True)
                        logging.info(f"Ответ команды: {cmd.get('speak')}")
            else:
                print("💬 Обрабатываю как общение...", flush=True)
                logging.info("Обрабатываю как общение с ассистентом")
                response = chat_with_assistant(text)
                print(f"🤖 Ассистент: {response}", flush=True)
                logging.info(f"Ответ ассистента: {response}")
            
            print("-" * 60, flush=True)
            
            cycle_count += 1
            if cycle_count >= MEMORY_CLEANUP_INTERVAL:
                cycle_count = 0
                import gc
                gc.collect()
                logging.debug("Выполнена периодическая очистка памяти")
            
        except Exception as e:
            logging.error(f"Ошибка обработки: {e}")
            time.sleep(0.1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Ошибка: {e}")
        logging.error(f"Fatal error: {e}")