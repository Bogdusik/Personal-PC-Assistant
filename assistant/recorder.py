import time, numpy as np, sounddevice as sd, soundfile as sf, keyboard

SAMPLE_RATE = 16000
CHANNELS = 1

def record_push_to_talk(outfile: str, hotkey: str = "right shift", mic_device=None) -> str | None:
    try:
        while not keyboard.is_pressed(hotkey):
            time.sleep(0.01)
    except RuntimeError:
        print('Нужны права администратора. Запустите "От имени администратора".')
        return None

    frames = []
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', device=mic_device) as stream:
            while keyboard.is_pressed(hotkey):
                data, _ = stream.read(1024)
                frames.append(data.copy())
            
            for _ in range(int(SAMPLE_RATE * 0.1 / 1024) + 1):
                data, _ = stream.read(1024)
                frames.append(data.copy())
    except Exception as e:
        print(f"Ошибка записи: {e}")
        return None

    if not frames:
        return None

    audio = np.concatenate(frames, axis=0)
    dur = len(audio) / SAMPLE_RATE
    
    if dur < 0.5:
        return None
    
    sf.write(outfile, audio, SAMPLE_RATE)
    print(f"Записано: {dur:.1f}с")
    return outfile