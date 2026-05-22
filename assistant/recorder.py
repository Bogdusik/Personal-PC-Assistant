from __future__ import annotations

import logging
import time
from typing import Optional

import keyboard
import numpy as np
import sounddevice as sd
import soundfile as sf

from assistant.core.exceptions import AudioError

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1


def record_push_to_talk(
    outfile: str,
    hotkey: str = "right shift",
    mic_device: Optional[int | str] = None,
) -> Optional[str]:
    try:
        while not keyboard.is_pressed(hotkey):
            time.sleep(0.01)
    except RuntimeError as exc:
        raise AudioError('Нужны права администратора для hotkey-хука') from exc

    frames: list[np.ndarray] = []
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            device=mic_device,
        ) as stream:
            while keyboard.is_pressed(hotkey):
                data, _ = stream.read(1024)
                frames.append(data.copy())
            for _ in range(int(SAMPLE_RATE * 0.1 / 1024) + 1):
                data, _ = stream.read(1024)
                frames.append(data.copy())
    except sd.PortAudioError as exc:
        raise AudioError(f"Ошибка записи с микрофона: {exc}") from exc

    if not frames:
        return None

    audio = np.concatenate(frames, axis=0)
    dur = len(audio) / SAMPLE_RATE

    if dur < 0.5:
        return None

    sf.write(outfile, audio, SAMPLE_RATE)
    logger.info("Записано: %.1fс → %s", dur, outfile)
    return outfile
