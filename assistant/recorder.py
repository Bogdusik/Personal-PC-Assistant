import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import keyboard

SAMPLE_RATE = 16000
CHANNELS = 1

def record_push_to_talk(outfile: str, hotkey: str = "right shift", mic_device=None) -> str | None:
    print(f"Зажми и держи {hotkey.upper()}, говори. Отпустишь — запись завершится.")
    try:
        while not keyboard.is_pressed(hotkey):
            time.sleep(0.02)
    except RuntimeError:
        print('Нужны права администратора для глобальных клавиш. Запусти терминал "От имени администратора".')
        return None

    frames = []
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', device=mic_device) as stream:
            while keyboard.is_pressed(hotkey):
                data, _ = stream.read(1024)
                frames.append(data.copy())
            # хвост ~200 мс
            for _ in range(int(SAMPLE_RATE * 0.2 / 1024) + 1):
                data, _ = stream.read(1024)
                frames.append(data.copy())
    except Exception as e:
        print(f"Audio record error: {e}")
        return None

    if not frames:
        print("Пустая запись.")
        return None

    audio = np.concatenate(frames, axis=0)
    sf.write(outfile, audio, SAMPLE_RATE)
    dur = len(audio) / SAMPLE_RATE
    print(f"Готово: {outfile} ({dur:.2f} с)")
    return outfile

def list_input_devices():
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            print(f"{i}: {dev['name']}")
