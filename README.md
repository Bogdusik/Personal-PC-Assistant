# 🎤 Personal PC Assistant

<div align="center">

**A powerful voice-controlled assistant for Windows PC management**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*Control your computer with voice commands using AI-powered speech recognition*

</div>

---

## ✨ Features

- 🎙️ **Voice Recognition** - Powered by Faster Whisper for accurate speech-to-text
- 🤖 **AI Integration** - Uses Ollama for intelligent app search and natural conversations
- 🚀 **App Management** - Open, close, and minimize applications with voice commands
- 🔊 **System Control** - Adjust volume, brightness, Wi-Fi, and more
- 📸 **Screenshots** - Capture screenshots instantly
- 📋 **Clipboard** - Copy and paste text via voice
- 🎯 **Custom Commands** - Learn and create your own voice commands
- 🔍 **Smart App Search** - AI-powered application discovery
- 💬 **Natural Conversations** - Chat with your assistant using Ollama

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Windows 10/11
- [Ollama](https://ollama.ai/) installed
- Microphone

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Bogdusik/Personal-PC-Assistant.git
   cd Personal-PC-Assistant
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install and setup Ollama**
   - Download from [ollama.ai](https://ollama.ai/)
   - Pull the required model:
     ```bash
     ollama pull gemma3:12b
     ```
   - Or use another model by editing `config.json`

4. **Configure the assistant**
   - Edit `config.json` to customize:
     - Hotkey (default: `right shift`)
     - Microphone device
     - App aliases
     - Ollama model

### Running

**⚠️ Important:** Run as Administrator for hotkey functionality!

```bash
python main_fast.py
```

Or via PowerShell (as Administrator):
```powershell
python main_fast.py
```

## 📖 Usage

1. **Activate** - Press and hold `Right Shift` (or your configured hotkey)
2. **Speak** - Say your command (e.g., "открой браузер", "сделай скриншот")
3. **Release** - Let go of the key to process the command

### Example Commands

| Command (Russian) | English | Action |
|-----------------|---------|--------|
| `открой браузер` | Open browser | Opens Chrome |
| `открой телеграм` | Open Telegram | Launches Telegram |
| `сделай скриншот` | Take screenshot | Captures screen |
| `установи громкость 50` | Set volume 50 | Sets volume to 50% |
| `закрой спотифай` | Close Spotify | Closes Spotify |
| `статус` | Status | Shows system status |
| `команды` | Commands | Lists all custom commands |
| `новая команда` | New command | Learn a new command |

### Hotkeys

- **Right Shift** (default) - Activate voice recording
- **Ctrl+4** - Open command learning interface

## 🏗️ Project Structure

```
Personal-PC-Assistant/
├── main_fast.py              # Main entry point
├── config.json               # Configuration file
├── requirements.txt          # Python dependencies
├── README.md                 # This file
│
├── assistant/
│   ├── __init__.py
│   ├── asr.py                # Speech recognition (Whisper)
│   ├── nlu.py                 # Natural language understanding
│   ├── recorder.py            # Audio recording
│   ├── runner.py              # Command execution
│   │
│   └── skills/                # Assistant skills
│       ├── __init__.py
│       └── skills.py          # Core functionality
│
└── assistant.log             # Application logs
```

## 🛠️ Technologies

- **Python 3.8+** - Core language
- **Faster Whisper** - Speech recognition
- **Ollama** - AI model integration
- **PyAudio/SoundDevice** - Audio processing
- **Keyboard** - Hotkey detection
- **PyCaw** - Windows audio control
- **MSS** - Screenshot capture
- **PyMorphy2** - Russian language processing

## ⚙️ Configuration

Edit `config.json` to customize:

```json
{
  "hotkey": "right shift",           // Activation hotkey
  "mic_device": null,                // Microphone device ID
  "ollama_model": "gemma3:12b",     // Ollama model name
  "app_aliases": {                   // Application shortcuts
    "chrome": "C:\\Program Files\\...",
    "telegram": "C:\\Users\\...",
    ...
  },
  "custom_commands": [               // User-defined commands
    {
      "match_type": "equals",
      "pattern": "открой ютуб",
      "intent": "open_browser_search",
      "args": {"query": "youtube"},
      "speak": "Открываю поиск по YouTube."
    }
  ]
}
```

## 🎯 Features in Detail

### Voice Recognition
- Real-time speech-to-text using Faster Whisper
- Support for Russian language
- Push-to-talk activation
- Automatic silence detection

### AI-Powered Search
- Intelligent application discovery
- Context-aware search
- Automatic path resolution
- Learning from successful searches

### System Management
- Volume control (0-100%)
- Brightness adjustment
- Wi-Fi toggle
- Screenshot capture
- Clipboard operations
- System power management (shutdown, restart, sleep, lock)

### Custom Commands
- Create your own voice commands
- Multiple matching types (equals, contains, regex)
- Custom responses
- Easy management interface

## 🐛 Troubleshooting

### Administrator Rights Required
**Problem:** Hotkeys don't work  
**Solution:** Run PowerShell/CMD as Administrator

### Ollama Not Starting
**Problem:** "Ollama не запущен" error  
**Solution:** 
```bash
ollama serve
```
Verify Ollama is in your PATH

### Microphone Issues
**Problem:** No audio input detected  
**Solution:** 
- Check Windows microphone settings
- Specify device ID in `config.json`
- Test with Windows Sound settings

### ASR Model Loading
**Problem:** Model download fails  
**Solution:** 
- Check internet connection
- First run requires model download (~100MB)
- Try different model sizes (tiny, base, small)

## 📝 Development

### Code Structure
- **Modular design** - Each component in separate files
- **Optimized codebase** - 34% code reduction from original
- **Error handling** - Comprehensive exception management
- **Logging** - Detailed logs in `assistant.log`

### Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is for personal use and educational purposes.

## 🙏 Acknowledgments

- [Faster Whisper](https://github.com/guillaumekln/faster-whisper) - Speech recognition
- [Ollama](https://ollama.ai/) - AI model integration
- All open-source libraries used in this project

## 📧 Contact

For questions or suggestions, please open an issue on GitHub.

---

<div align="center">

**Made with ❤️ for efficient PC management**

⭐ Star this repo if you find it useful!

</div>
