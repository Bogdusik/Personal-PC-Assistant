# Personal PC Assistant

A local Windows voice assistant. Hold a hotkey → speak → the assistant executes your command. Everything runs offline: speech recognition via Faster Whisper, intent detection via rule engine + Ollama fallback.

![Control Panel Screenshot](assets/gui-screenshot.png)

## Features

- Push-to-talk voice control (default: Right Shift)
- 15+ built-in skills: open/close apps, volume, brightness, screenshots, Wi-Fi toggle, shutdown, web search, clipboard
- Cyberpunk-themed PyQt6 GUI with animated waveform
- Teach custom voice commands without code — saved to `config.json`
- Fully local: Faster Whisper ASR + Ollama LLM, no cloud APIs

## Architecture

```
main_gui.py / main_fast.py
        │
        ├─ assistant/
        │   ├─ core/
        │   │   ├─ exceptions.py   (AssistantError hierarchy)
        │   │   └─ state.py        (AssistantState dataclass)
        │   ├─ nlu/
        │   │   ├─ normalizer.py   (text cleaning, lemmatization)
        │   │   ├─ ollama_client.py (OllamaClient — injectable base_url)
        │   │   └─ engine.py       (rules + Ollama fallback → intent)
        │   ├─ skills/
        │   │   ├─ app_control.py  (open/close/minimize apps)
        │   │   ├─ system_control.py (volume, brightness, shutdown …)
        │   │   ├─ browser.py      (search, open website)
        │   │   ├─ clipboard.py    (copy/paste)
        │   │   └─ registry.py     (SKILLS dict + Skill Protocol)
        │   ├─ asr.py              (Faster Whisper transcription)
        │   ├─ recorder.py         (push-to-talk audio capture)
        │   └─ runner.py           (skill dispatch + confirmation flow)
        └─ config.json             (hotkey, app aliases, custom commands)
```

## Entry points

| File | Use when |
|------|----------|
| `main_gui.py` | Daily use — cyberpunk control panel, visual feedback |
| `main_fast.py` | Debugging / scripting — console-only, lighter startup |

## Setup

### Requirements

- Windows 10/11
- Python 3.10+
- [Ollama](https://ollama.ai) installed and on PATH
- Microphone

### Quick start

```bat
:: 1. Clone
git clone https://github.com/Bogdusik/Personal-PC-Assistant.git
cd Personal-PC-Assistant

:: 2. Run setup (checks admin, copies config, installs deps)
setup.bat

:: 3. Pull an Ollama model (one-time)
ollama pull gemma3:12b

:: 4. Launch (as Administrator for hotkey support)
python main_gui.py
```

### Manual setup

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json
```

Edit `config.json`:
- `hotkey` — key to hold while speaking (default: `"right shift"`)
- `mic_device` — microphone device index or `null` for default
- `ollama_model` — model name (default: `"gemma3:12b"`)
- `app_aliases` — map your app names to full `.exe` paths

> **Run as Administrator** — required for keyboard hotkey hooks.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Override Ollama server URL |
| `OLLAMA_MODEL` | `gemma3:12b` | Override model (also settable in config.json) |

## Teaching custom commands

Say *"новая команда"* (new command) or press **Ctrl+4** while the assistant is running to add a custom voice trigger:
- Choose a match type: `equals`, `startswith`, `contains`, or `regex`
- Pick an intent and its arguments
- Commands are saved to `config.json` immediately

## Running tests

```bat
pip install pytest
pytest tests/ -v
```

## Development

```bat
pip install ruff mypy
ruff check .
mypy assistant --ignore-missing-imports
```
