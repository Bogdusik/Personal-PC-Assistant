import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""   # фикс: только CPU
os.environ["CT2_VERBOSE"] = "0"

from faster_whisper import WhisperModel

def init_asr():
    print("Гружу ASR-модель (faster-whisper, CPU int8)...", flush=True)
    try:
        return WhisperModel("small", device="cpu", compute_type="int8")
    except Exception:
        return WhisperModel("small", device="cpu")

def transcribe(model, path: str) -> str:
    try:
        segments, _ = model.transcribe(
            path,
            language="ru",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            beam_size=5,
            best_of=5,
            condition_on_previous_text=False
        )
        return "".join(seg.text for seg in segments).strip()
    except Exception as e:
        print(f"ASR ошибка: {e}")
        return ""
