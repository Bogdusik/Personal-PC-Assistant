# Personal PC Assistant

This app lets you talk to your computer and it actually listens. I built it because I got tired of clicking through menus when I could just say "open browser" or "take a screenshot" and have it happen instantly.

## How it looks

![GUI Screenshot](assets/gui-screenshot.png)

*(Video demo coming soon)*

## Why this isn't just code

• I didn't just copy-paste — built a premium sci-fi/cyberpunk GUI with animated waveform monitor and glassmorphism effects from scratch  
• It works even if Ollama isn't running — gracefully falls back and guides you through setup  
• Plus a tiny detail nobody expects: the waveform monitor reacts to your voice in real-time, and the whole interface "wakes up" with a smooth fade-in animation when you launch it

## How to run (even if you've never coded)

```bash
git clone https://github.com/Bogdusik/Personal-PC-Assistant.git
cd Personal-PC-Assistant
pip install -r requirements.txt
python main_gui.py
```

**Setup steps:**
- Run as Administrator (for hotkey functionality)
- Install [Ollama](https://ollama.ai/) and pull model: `ollama pull gemma3:12b`
- Enable microphone in Windows settings

**Important:** Works only on Windows 10/11. Hotkey is `Right Shift` by default (hold to speak, release to process).

## What's in my head after building this

• Learned how speech recognition actually works in practice, not just from lectures - Faster Whisper is incredible  
• Got comfortable with Windows API hell - PyCaw, win32gui, keyboard hooks, all the fun stuff  
• What's next: connect it to smart home devices, maybe add gesture control  
• Personal takeaway: my computer isn't just a machine anymore, it's like having a conversation. Yesterday I literally told it to open Spotify and it did. That's wild.
