from __future__ import annotations
import gc
import logging
import os

from assistant.core.exceptions import AudioError

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["CT2_VERBOSE"] = "0"

logger = logging.getLogger(__name__)

_cached_model = None
_model_name: str | None = None


def init_asr():
    global _cached_model, _model_name

    if _cached_model is not None:
        logger.info("Используем кэшированную модель: %s", _model_name)
        return _cached_model

    print("Гружу ASR-модель (faster-whisper, CPU)...", flush=True)

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AudioError(f"faster-whisper не установлен: {exc}") from exc

    for model_name, device, compute_type in [
        ("tiny", "cpu", "int8"),
        ("tiny", "cpu", "float32"),
        ("base", "cpu", "int8"),
        ("base", "cpu", "float32"),
    ]:
        try:
            print(f"Пробую модель: {model_name} ({compute_type})...", flush=True)
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            _cached_model = model
            _model_name = f"{model_name}_{compute_type}"
            print(f"✅ Модель {model_name} загружена!", flush=True)
            logger.info("ASR модель %s загружена", _model_name)
            return model
        except Exception as exc:
            logger.warning("Ошибка загрузки %s/%s: %s", model_name, compute_type, exc)
            continue

    try:
        model = WhisperModel("tiny")
        _cached_model = model
        _model_name = "tiny_default"
        print("✅ Базовая модель загружена!", flush=True)
        logger.info("Базовая ASR модель загружена")
        return model
    except Exception as exc:
        raise AudioError(f"Не удалось загрузить ни одну модель Whisper: {exc}") from exc


def cleanup_asr() -> None:
    global _cached_model, _model_name
    if _cached_model is not None:
        logger.info("Очищаю память ASR модели")
        del _cached_model
        _cached_model = None
        _model_name = None
        gc.collect()


def transcribe(model, path: str) -> str:
    try:
        segments, _ = model.transcribe(
            path,
            language="ru",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
        )
        result = "".join(seg.text for seg in segments).strip()
        logger.info("Транскрипция завершена: '%s'", result)
        return result
    except FileNotFoundError as exc:
        logger.error("Аудио файл не найден: %s", path)
        raise AudioError(f"Файл не найден: {path}") from exc
    except Exception as exc:
        logger.error("ASR ошибка транскрипции: %s", exc)
        raise AudioError(f"Ошибка транскрипции: {exc}") from exc
