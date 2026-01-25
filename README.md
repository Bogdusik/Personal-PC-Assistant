# Personal PC Assistant

Voice-controlled assistant for Windows PC management with AI support.

## Features

- 🎙️ Speech recognition (Faster Whisper)
- 🤖 AI integration (Ollama) for app search and conversations
- 🚀 Application management (open/close/minimize)
- 🔊 System control (volume, brightness, Wi-Fi, screenshots)
- 🎯 Custom commands
- 🖥️ Premium sci-fi/cyberpunk GUI

## Requirements

- Python 3.8+
- Windows 10/11
- [Ollama](https://ollama.ai/) installed
- Microphone

## Installation

```bash
# Clone repository
git clone https://github.com/Bogdusik/Personal-PC-Assistant.git
cd Personal-PC-Assistant

# Install dependencies
pip install -r requirements.txt

# Pull Ollama model
ollama pull gemma3:12b
```

## Configuration

1. Copy `config.example.json` to `config.json`
2. Configure application paths in `app_aliases`
3. Set hotkey (default: `right shift`)

## Running

**⚠️ Important:** Run as Administrator for hotkey functionality!

### GUI version (recommended)
```bash
python main_gui.py
```

### Console version
```bash
python main_fast.py
```

## Usage

1. Press and hold `Right Shift` (or configured hotkey)
2. Speak your command (e.g., "открой браузер", "сделай скриншот")
3. Release the key to process

### Example Commands

| Command | Action |
|---------|--------|
| `открой браузер` | Open Chrome |
| `открой телеграм` | Open Telegram |
| `сделай скриншот` | Take screenshot |
| `установи громкость 50` | Set volume to 50% |
| `закрой спотифай` | Close Spotify |
| `статус` | Show system status |

## Project Structure

```
Personal-PC-Assistant/
├── main_gui.py              # GUI version (PyQt6)
├── main_fast.py             # Console version
├── config.example.json       # Configuration template
├── requirements.txt          # Dependencies
│
└── assistant/
    ├── asr.py               # Speech recognition
    ├── nlu.py               # Command understanding
    ├── recorder.py          # Audio recording
    ├── runner.py            # Command execution
    └── skills/
        └── skills.py        # Core functionality
```

## Technologies

- **Faster Whisper** - Speech recognition
- **Ollama** - AI models
- **PyQt6** - GUI interface
- **PyCaw** - Windows audio control
- **Keyboard** - Hotkey handling

## Troubleshooting

**Hotkeys don't work**  
→ Run as Administrator

**Ollama not starting**  
→ Ensure Ollama is installed and added to PATH

**Microphone not working**  
→ Check Windows settings and specify device ID in `config.json`

## License

For personal use and educational purposes.
