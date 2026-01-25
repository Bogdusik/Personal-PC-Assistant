# Personal PC Assistant

A voice assistant for Windows that **actually listens** and executes commands in natural language.  
Say "open browser", "take a screenshot", "play Spotify" or "talk to me" — and it happens instantly, without mouse clicks or menus.  
Built it because I got tired of digging through settings and wanted my computer to feel like a living conversation partner.

## How it looks

![Control Panel Screenshot](assets/gui-screenshot.png)

*(Short video demo coming soon — voice → reaction → execution)*

## Why this isn't just "another assistant"

- Fully custom sci-fi/cyberpunk GUI built from scratch: glassmorphism, neon accents, animated waveform microphone monitor, smooth fade-in on launch  
- Works even if Ollama crashes — graceful fallback with helpful prompts "let's start the model"  
- Reactive interface: waveform pulses from voice in real-time, buttons with ripple effects, hover-glow  
- Hotkey support (default Right Shift) — hold to speak, release to process  
- Full system control: volume, brightness, Wi-Fi, launch apps by aliases, screenshots, media control  
- Local AI: Faster Whisper + Ollama (gemma3:12b) — nothing goes to the cloud  

## Quick start (even if you're a beginner)

```bash
git clone https://github.com/Bogdusik/Personal-PC-Assistant.git
cd Personal-PC-Assistant
# (optional) create virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
# Install Ollama and pull model (if not already)
ollama pull gemma3:12b
# Run (must be Administrator for hotkey!)
python main_gui.py
```

**Important:** Run as Administrator for hotkey functionality. Works only on Windows 10/11.

## What's in my head after building this

• Learned how speech recognition actually works in practice, not just from lectures - Faster Whisper is incredible  
• Got comfortable with Windows API hell - PyCaw, win32gui, keyboard hooks, all the fun stuff  
• What's next: connect it to smart home devices, maybe add gesture control  
• Personal takeaway: my computer isn't just a machine anymore, it's like having a conversation. Yesterday I literally told it to open Spotify and it did. That's wild.
