import json, logging, os
from assistant.recorder import record_push_to_talk
from assistant.asr import init_asr, transcribe
from assistant.nlu import nlu_rules
from assistant.runner import run_command
from assistant.skills import APP_ALIASES

AUDIO_PATH = "last_cmd.wav"
LOG_FILE = "assistant.log"
CONFIG_PATH = "config.json"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

CFG = load_config()
HOTKEY = CFG.get("hotkey", "right shift")
MIC_DEVICE = CFG.get("mic_device", None)
APP_ALIASES.update(CFG.get("app_aliases", {}))

def main():
    print("Гружу ASR...")
    asr_model = init_asr()
    print(f"Ассистент запущен. Удерживай {HOTKEY.upper()} чтобы говорить. Ctrl+C — выйти.")
    while True:
        path = record_push_to_talk(AUDIO_PATH, hotkey=HOTKEY, mic_device=MIC_DEVICE)
        if not path:
            continue
        text = transcribe(asr_model, path)
        if not text:
            print("Не разобрал речь.")
            continue
        cmd = nlu_rules(text)
        run_command(cmd)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПока!")
