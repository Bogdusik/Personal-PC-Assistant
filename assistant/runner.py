import json
from jsonschema import validate
from .nlu import INTENT_SCHEMA
from .skills import SKILLS

def run_command(cmd: dict):
    validate(cmd, INTENT_SCHEMA)
    intent = cmd["intent"]
    args = cmd["args"]
    speak = cmd.get("speak")

    if intent == "smalltalk":
        print(speak or args.get("text"))
        return

    fn = SKILLS.get(intent)
    if not fn:
        print("Неизвестная команда:", intent)
        return

    fn(**args)
    if speak:
        print(speak)
