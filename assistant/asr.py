import os
import logging
import gc

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["CT2_VERBOSE"] = "0"

_cached_model = None
_model_name = None

def init_asr():
    global _cached_model, _model_name
    
    if _cached_model is not None:
        logging.info(f"Используем кэшированную модель: {_model_name}")
        return _cached_model
    
    print("Гружу ASR-модель (faster-whisper, CPU)...", flush=True)
    logging.info("Начинаю загрузку ASR модели")
    
    models_to_try = [
        ("tiny", "cpu", "int8"),
        ("tiny", "cpu", "float32"),
        ("base", "cpu", "int8"),
        ("base", "cpu", "float32"),
    ]
    
    for model_name, device, compute_type in models_to_try:
        try:
            print(f"Пробую модель: {model_name} ({compute_type})...", flush=True)
            logging.info(f"Попытка загрузки модели: {model_name} ({compute_type})")
            
            from faster_whisper import WhisperModel
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            
            _cached_model = model
            _model_name = f"{model_name}_{compute_type}"
            
            print(f"✅ Модель {model_name} загружена успешно!", flush=True)
            logging.info(f"ASR модель {model_name} загружена и кэширована")
            return model
            
        except ImportError as e:
            logging.error(f"Ошибка импорта faster-whisper: {e}")
            print(f"❌ Ошибка импорта: {e}", flush=True)
            break
        except Exception as e:
            error_msg = str(e)[:100]
            print(f"❌ Ошибка с {model_name}: {error_msg}...", flush=True)
            logging.warning(f"Ошибка загрузки {model_name}: {e}")
            continue
    
    try:
        print("Пробую базовую загрузку...", flush=True)
        logging.info("Попытка базовой загрузки модели")
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny")
        
        _cached_model = model
        _model_name = "tiny_default"
        
        print("✅ Базовая модель загружена!", flush=True)
        logging.info("Базовая ASR модель загружена успешно")
        return model
        
    except Exception as e:
        error_msg = f"Критическая ошибка загрузки ASR: {e}"
        print(f"❌ {error_msg}", flush=True)
        logging.error(error_msg)
        raise Exception(f"Не удалось загрузить ни одну модель Whisper: {e}")

def cleanup_asr():
    global _cached_model, _model_name
    if _cached_model is not None:
        logging.info("Очищаю память ASR модели")
        del _cached_model
        _cached_model = None
        _model_name = None
        gc.collect()

def transcribe(model, path: str) -> str:
    try:
        logging.info(f"Начинаю транскрипцию файла: {path}")
        segments, _ = model.transcribe(
            path,
            language="ru",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            # Максимально быстрый режим: жадный декодер без бима
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False
        )
        
        result = "".join(seg.text for seg in segments).strip()
        logging.info(f"Транскрипция завершена: '{result}'")
        return result
        
    except FileNotFoundError:
        logging.error(f"Аудио файл не найден: {path}")
        print(f"❌ Файл не найден: {path}")
        return ""
    except Exception as e:
        error_msg = f"ASR ошибка транскрипции: {e}"
        logging.error(error_msg)
        print(f"❌ {error_msg}")
        return ""