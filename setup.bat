@echo off
setlocal

echo ============================================================
echo  Personal PC Assistant - Setup
echo ============================================================

:: Check admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] Not running as Administrator.
    echo          Hotkey support requires admin. Right-click setup.bat
    echo          and choose "Run as administrator".
    echo.
)

:: Copy config if missing
if not exist config.json (
    if exist config.example.json (
        copy config.example.json config.json >nul
        echo [OK] Created config.json from config.example.json
        echo      Edit config.json to set your app paths and hotkey.
    ) else (
        echo [ERROR] config.example.json not found. Check your repo.
        pause
        exit /b 1
    )
) else (
    echo [OK] config.json already exists
)

:: Check Python
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

:: Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt
if %errorLevel% neq 0 (
    echo [ERROR] pip install failed. Check requirements.txt and your Python env.
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: Check Ollama
ollama --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] Ollama not found.
    echo          Download from https://ollama.ai and install it.
    echo          Then run: ollama pull gemma3:12b
) else (
    echo [OK] Ollama found
)

echo.
echo ============================================================
echo  Setup complete!
echo  Run the assistant with:
echo    python main_gui.py     (GUI, recommended)
echo    python main_fast.py    (Console / debugging)
echo ============================================================
pause
