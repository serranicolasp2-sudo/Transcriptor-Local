#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Transcripción y Diarización de Hablantes.
Conserva estrictamente la pipeline validada:
- faster-whisper (large-v3-turbo en CPU con int8 por defecto; small / large-v3 y la placa NVIDIA
  si se instalaron desde Configuración, ver src/componentes.py) con VAD activo y timestamps
- pyannote.audio (speaker-diarization-community-1, CPU, 4 hablantes)
- Tolerancia a fallos mediante checkpoints
- Callback de progreso en tiempo real y soporte para cancelación
"""

import os
import gc
import re
import json
import time
import logging
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Tuple

import torch
import soundfile as sf

from src import componentes

# Las DLL de NVIDIA (si se instaló el paquete) se registran antes de cargar el motor de Whisper.
componentes.activar_aceleracion()

from faster_whisper import WhisperModel  # noqa: E402
from pyannote.audio import Pipeline

from src.config import (
    BASE_DIR,
    OUTPUT_DIR,
    MODELS_DIR,
    LOGS_DIR,
    cargar_token_hf,
    modelos_diarizacion_locales,
    DIARIZATION_MODEL_ID,
    obtener_duracion,
    formatear_tiempo,
)
from src.exporter import exportar_todo
from src.acelerador import resolver_dispositivo_computo

logger = logging.getLogger("TranscriptorEngine")
logger.setLevel(logging.INFO)

_whisper_model: Optional[WhisperModel] = None
_whisper_lock = threading.Lock()
_motor: Optional[componentes.Motor] = None


def motor_actual() -> componentes.Motor:
    """Modelo y dispositivo de este proceso. Se eligen una vez: los cambios de Configuración se aplican al reiniciar."""
    global _motor
    if _motor is None:
        _motor = componentes.elegir_motor()
    return _motor


def _crear_modelo(motor: componentes.Motor) -> WhisperModel:
    return WhisperModel(
        motor.ruta,
        device=motor.dispositivo,
        compute_type=motor.tipo_calculo,
        download_root=str(MODELS_DIR),
    )


def get_whisper_model() -> WhisperModel:
    """Carga el modelo elegido una sola vez por proceso. Seguro entre hilos. Si la placa falla, sigue en CPU."""
    global _whisper_model, _motor
    if _whisper_model is None:
        with _whisper_lock:
            if _whisper_model is None:       # revisá de nuevo con el lock tomado
                motor = motor_actual()
                try:
                    _whisper_model = _crear_modelo(motor)
                except Exception as e:
                    if motor.dispositivo != "cuda":
                        raise
                    logger.warning(f"No se pudo cargar Whisper en la placa NVIDIA ({e}). Se usa la CPU.")
                    _motor = componentes.motor_cpu(motor.modelo)
                    _whisper_model = _crear_modelo(_motor)
    return _whisper_model


def _pasar_a_cpu(error: Exception) -> None:
    """La placa falló en plena transcripción: se descarta el modelo de GPU y el próximo intento usa la CPU."""
    global _whisper_model, _motor
    with _whisper_lock:
        logger.warning(f"Falló la transcripción en la placa NVIDIA ({error}). Se reintenta con la CPU.")
        _motor = componentes.motor_cpu(motor_actual().modelo)
        _whisper_model = None
        gc.collect()


def convertir_a_wav_16k(
    audio_path: Path,
    output_dir: Path,
    duracion_total: Optional[float] = None,
    progress_callback: Optional[Callable[[str, float, bool, float, str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Path:
    """
    Convierte cualquier archivo de audio/video a WAV 16kHz mono mediante FFmpeg.
    Drena continuamente el stream stderr para evitar deadlocks de buffer del OS
    en audios largos y reporta el progreso real segundo a segundo.
    """
    audio_path = Path(audio_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    wav_path = output_dir / f"{audio_path.stem}_16khz.wav"
    if wav_path.exists() and wav_path.stat().st_size > 1024:
        return wav_path

    if cancel_event and cancel_event.is_set():
        raise InterruptedError("Proceso cancelado por el usuario.")

    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(wav_path),
    ]
    
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )

    time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
    dur_total = duracion_total or obtener_duracion(audio_path) or 0.0

    last_update_time = time.time()
    stderr_tail = []

    while True:
        if cancel_event and cancel_event.is_set():
            proc.terminate()
            raise InterruptedError("Conversión cancelada por el usuario.")

        line = proc.stderr.readline()
        if not line and proc.poll() is not None:
            break

        if line:
            stderr_tail.append(line)
            if len(stderr_tail) > 30:
                stderr_tail.pop(0)

            m = time_regex.search(line)
            if m and dur_total > 0:
                now = time.time()
                if now - last_update_time >= 0.4:
                    last_update_time = now
                    h, mn, s = m.groups()
                    conv_sec = int(h) * 3600 + int(mn) * 60 + float(s)
                    conv_frac = min(1.0, conv_sec / dur_total)
                    global_frac = conv_frac * 0.03
                    if progress_callback:
                        progress_callback(
                            "Preparando archivo de audio...",
                            global_frac,
                            False,
                            conv_sec,
                            f"Convirtiendo audio: {formatear_tiempo(conv_sec)} / {formatear_tiempo(dur_total)}"
                        )

    proc.communicate()
    if proc.returncode != 0:
        err_msg = "".join(stderr_tail[-10:])
        raise RuntimeError(f"FFmpeg falló al convertir el archivo:\n{err_msg}")

    return wav_path


def verificar_checkpoint(audio_path: Path, output_dir: Path) -> Dict[str, bool]:
    """Verifica si existen checkpoints previos de transcripción o diarización para este archivo."""
    audio_path = Path(audio_path)
    chk_dir = Path(output_dir) / f".checkpoint_{audio_path.stem}"
    return {
        "existe": chk_dir.exists(),
        "transcripcion": (chk_dir / "transcripcion.json").exists(),
        "diarizacion": (chk_dir / "diarizacion.json").exists(),
        "wav": (chk_dir / f"{audio_path.stem}_16khz.wav").exists(),
    }


def transcribir_whisper(
    wav_path: Path,
    duracion_total: float,
    progress_callback: Optional[Callable] = None,
    cancel_event: Optional[threading.Event] = None,
    idioma: str | None = "es",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Ejecuta la transcripción con faster-whisper con el motor elegido (ver motor_actual).
    Calcula el progreso real a partir de los timestamps de cada segmento generado.
    Si la placa NVIDIA falla en el medio, vuelve a empezar con la CPU en vez de cortar el proceso.
    """
    try:
        return _transcribir_con_motor(wav_path, duracion_total, progress_callback, cancel_event, idioma)
    except InterruptedError:
        raise
    except Exception as e:
        if motor_actual().dispositivo != "cuda":
            raise
        _pasar_a_cpu(e)
        if progress_callback:
            progress_callback(
                stage="La placa de video falló: sigo con el procesador...",
                fraction=0.05,
                is_estimated=False,
                processed_seconds=0.0,
                message=f"Error de la placa NVIDIA: {e}",
            )
        return _transcribir_con_motor(wav_path, duracion_total, progress_callback, cancel_event, idioma)


def _transcribir_con_motor(
    wav_path: Path,
    duracion_total: float,
    progress_callback: Optional[Callable],
    cancel_event: Optional[threading.Event],
    idioma: str | None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if progress_callback:
        progress_callback(
            stage=f"Cargando modelo Whisper ({motor_actual().descripcion})...",
            fraction=0.05,
            is_estimated=False,
            processed_seconds=0.0,
            message="Inicializando modelo de reconocimiento de voz...",
        )

    model = get_whisper_model()

    if cancel_event and cancel_event.is_set():
        raise InterruptedError("Cancelado antes de iniciar transcripción.")

    if progress_callback:
        progress_callback(
            stage="Transcribiendo audio (faster-whisper)...",
            fraction=0.10,
            is_estimated=False,
            processed_seconds=0.0,
            message="Reconociendo voz y filtrando silencios (VAD)...",
        )

    # Se le pasa el audio ya leído: si faster-whisper abre el archivo, usa PyAV, y algunas combinaciones de
    # versiones fallan (faster-whisper 1.2.1 con av 19: "unexpected keyword argument 'metadata_errors'").
    audio, _ = sf.read(str(wav_path), dtype="float32")
    segments_generator, info = model.transcribe(
        audio,
        language=idioma,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=400,
        ),
        word_timestamps=True,
    )

    segments = []
    duracion_audio = duracion_total if duracion_total > 0 else (info.duration or 1.0)

    for seg in segments_generator:
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Transcripción cancelada por el usuario.")

        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "words": [
                {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                for w in (seg.words or [])
            ],
        })

        # Progreso real de la etapa de transcripción: mapeado de 0.10 a 0.50 del total
        fraction_stage = min(1.0, seg.end / duracion_audio)
        fraction_total = 0.10 + (fraction_stage * 0.40)
        
        if progress_callback:
            progress_callback(
                stage=f"Transcribiendo audio (faster-whisper)...",
                fraction=fraction_total,
                is_estimated=False,
                processed_seconds=seg.end,
                message=f"Segmento {len(segments)} ({formatear_tiempo(seg.end)} / {formatear_tiempo(duracion_audio)})",
            )

    meta_info = {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
    }

    return segments, meta_info


def _spec_hablantes(
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
) -> Dict[str, int]:
    """
    Traduce los parámetros de hablantes a los kwargs de pyannote.
    Un dict vacío significa detección automática (pyannote decide solo).
    `num_speakers` tiene prioridad: si viene, se ignoran min/max.
    """
    if num_speakers is not None:
        return {"num_speakers": num_speakers}
    spec: Dict[str, int] = {}
    if min_speakers is not None:
        spec["min_speakers"] = min_speakers
    if max_speakers is not None:
        spec["max_speakers"] = max_speakers
    return spec


def _desc_hablantes(spec: Dict[str, int]) -> str:
    """Descripción legible de la configuración de hablantes, para mostrar y exportar."""
    if not spec:
        return "automático"
    if "num_speakers" in spec:
        return str(spec["num_speakers"])
    min_s, max_s = spec.get("min_speakers"), spec.get("max_speakers")
    if min_s is not None and max_s is not None:
        return f"{min_s}-{max_s}"
    if min_s is not None:
        return f"mín. {min_s}"
    return f"máx. {max_s}"


def diarizar_pyannote(
    wav_path: Path,
    duracion_total: float,
    num_speakers: int | None = 4,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    hf_token: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    cancel_event: Optional[threading.Event] = None,
) -> List[Dict[str, Any]]:
    """
    Ejecuta diarización con pyannote.audio configurado para exactamente 4 hablantes.
    Carga el audio en memoria con soundfile para máxima estabilidad en Windows.
    """
    if not hf_token:
        hf_token = cargar_token_hf()
    if not hf_token and not modelos_diarizacion_locales():
        raise ValueError("Token de Hugging Face no encontrado. Verifique el archivo .env.")

    spec = _spec_hablantes(num_speakers, min_speakers, max_speakers)
    desc_spk = _desc_hablantes(spec)
    spk_label = "automático" if desc_spk == "automático" else f"{desc_spk} hablantes"

    if progress_callback:
        progress_callback(
            stage="Cargando modelo de diarización (pyannote)...",
            fraction=0.52,
            is_estimated=False,
            processed_seconds=0.0,
            message="Cargando pipeline de separación de hablantes...",
        )

    model_id = DIARIZATION_MODEL_ID
    try:
        pipeline = Pipeline.from_pretrained(model_id, token=hf_token)
    except Exception as e:
        logger.warning(f"Fallo al cargar {model_id}: {e}. Intentando pyannote/speaker-diarization-3.1...")
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=hf_token)

    dev, _ = resolver_dispositivo_computo()
    target_device = torch.device(dev if dev == "cuda" else "cpu")
    try:
        pipeline.to(target_device)
        logger.info(f"Pipeline de diarización asignado a {target_device}.")
    except Exception as e:
        logger.warning(f"No se pudo asignar diarización a {target_device}: {e}. Fallback a CPU.")
        pipeline.to(torch.device("cpu"))

    if cancel_event and cancel_event.is_set():
        del pipeline
        gc.collect()
        raise InterruptedError("Cancelado antes de iniciar diarización.")

    # Cargar audio en memoria
    data, sr = sf.read(str(wav_path), dtype="float32")
    if data.ndim == 1:
        waveform = torch.from_numpy(data).unsqueeze(0)
    else:
        waveform = torch.from_numpy(data.T)
    audio_input = {"waveform": waveform, "sample_rate": sr}

    if progress_callback:
        progress_callback(
            stage=f"Diarizando hablantes (pyannote - {spk_label})...",
            fraction=0.55,
            is_estimated=True,
            processed_seconds=0.0,
            message="Segmentando acústicamente y agrupando voces en CPU...",
        )

    # Iniciar simulación de progreso estimado durante la inferencia de pyannote
    stop_progress_thread = threading.Event()
    
    def monitor_diarization():
        t0 = time.time()
        # Estimamos que pyannote tarda aproximadamente 0.5x la duración del audio en este CPU
        tiempo_estimado_diar = max(10.0, duracion_total * 0.52)
        while not stop_progress_thread.is_set():
            time.sleep(1.0)
            if stop_progress_thread.is_set():
                break
            elapsed = time.time() - t0
            progress_ratio = min(0.95, elapsed / tiempo_estimado_diar)
            # Mapear de 0.55 a 0.90 del total general
            current_total_frac = 0.55 + (progress_ratio * 0.35)
            proc_s = min(duracion_total, (progress_ratio * duracion_total))
            if progress_callback and not (cancel_event and cancel_event.is_set()):
                progress_callback(
                    stage=f"Diarizando hablantes (pyannote - {spk_label})...",
                    fraction=current_total_frac,
                    is_estimated=True,
                    processed_seconds=proc_s,
                    message=f"Diarizando en CPU ({int(progress_ratio * 100)}% estimado de la etapa)",
                )

    thread = threading.Thread(target=monitor_diarization, daemon=True)
    thread.start()

    def ejecutar_pipeline(kwargs: Dict[str, int]):
        try:
            return pipeline(audio_input, **kwargs)
        except TypeError:
            # Red de seguridad que ya existía: algunas versiones del pipeline no
            # aceptan num_speakers y sí el par min/max.
            if "num_speakers" in kwargs:
                return pipeline(
                    audio_input,
                    min_speakers=kwargs["num_speakers"],
                    max_speakers=kwargs["num_speakers"],
                )
            raise

    try:
        try:
            diarization = ejecutar_pipeline(spec)
        except ValueError as e:
            # Audio muy corto: hay menos fragmentos de voz que hablantes pedidos
            # ("n_samples=2 should be >= n_clusters=4"). Se reintenta en automático.
            if not spec or "n_clusters" not in str(e):
                raise
            logger.warning(
                f"Muy poca voz para {spk_label} ({e}). Reintentando diarización en modo automático."
            )
            if progress_callback:
                progress_callback(
                    stage="Diarizando hablantes (pyannote - automático)...",
                    fraction=0.6,
                    is_estimated=True,
                    processed_seconds=0.0,
                    message=f"Audio muy corto para {spk_label}: se detectan automáticamente.",
                )
            diarization = ejecutar_pipeline({})
    finally:
        stop_progress_thread.set()
        thread.join(timeout=1.0)

    if cancel_event and cancel_event.is_set():
        del pipeline, waveform, data
        gc.collect()
        raise InterruptedError("Diarización cancelada por el usuario.")

    diar_segments = []
    if hasattr(diarization, "itertracks"):
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            diar_segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker,
            })
    elif hasattr(diarization, "speaker_diarization"):
        for turn, speaker in diarization.speaker_diarization:
            diar_segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker,
            })

    del pipeline, waveform, data
    gc.collect()
    return diar_segments


def alinear_transcripcion_y_diarizacion(
    transcription_segments: List[Dict[str, Any]],
    diarization_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Asigna cada segmento de texto al hablante más coincidente temporalmente.
    Mapea las etiquetas crudas a 'SPEAKER 01', 'SPEAKER 02', 'SPEAKER 03', 'SPEAKER 04'.
    """
    speaker_raw_names = sorted(set(s["speaker"] for s in diarization_segments))
    speaker_map = {name: f"SPEAKER {i + 1:02d}" for i, name in enumerate(speaker_raw_names)}

    aligned_results = []
    for seg in transcription_segments:
        seg_start = seg["start"]
        seg_end = seg["end"]
        seg_mid = (seg_start + seg_end) / 2.0

        best_speaker = None
        best_overlap = 0.0

        for diar in diarization_segments:
            overlap_start = max(seg_start, diar["start"])
            overlap_end = min(seg_end, diar["end"])
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = diar["speaker"]

        if best_speaker is None:
            min_dist = float("inf")
            for diar in diarization_segments:
                diar_mid = (diar["start"] + diar["end"]) / 2.0
                dist = abs(seg_mid - diar_mid)
                if dist < min_dist:
                    min_dist = dist
                    best_speaker = diar["speaker"]

        speaker_label = speaker_map.get(best_speaker, "SPEAKER 01")
        aligned_results.append({
            "start": seg_start,
            "end": seg_end,
            "speaker": speaker_label,
            "text": seg["text"],
            "words": seg.get("words", []),
        })

    return aligned_results


def ejecutar_pipeline_completo(
    audio_path: str | Path,
    output_dir: Optional[str | Path] = None,
    speaker_mapping: Optional[Dict[str, str]] = None,
    progress_callback: Optional[Callable] = None,
    cancel_event: Optional[threading.Event] = None,
    reanudar_checkpoint: bool = True,
    diarizar: bool = True,
    num_speakers: int | None = 4,
    idioma: str | None = "es",
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> Dict[str, Any]:
    """
    Ejecuta el pipeline completo garantizando tolerancia a fallos, checkpoints y generación de archivos.
    Permite configurar diarización (activar/desactivar y cantidad de hablantes) e idioma de transcripción.
    """
    audio_path = Path(audio_path).resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {audio_path}")

    target_output_dir = Path(output_dir).resolve() if output_dir else OUTPUT_DIR
    target_output_dir.mkdir(parents=True, exist_ok=True)
    
    nombre_base = audio_path.stem
    checkpoint_dir = target_output_dir / f".checkpoint_{nombre_base}"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    chk_transcripcion = checkpoint_dir / "transcripcion.json"
    chk_diarizacion = checkpoint_dir / "diarizacion.json"
    
    t_global_inicio = time.time()
    duracion_total = obtener_duracion(audio_path) or 0.0

    if progress_callback:
        progress_callback(
            stage="Preparando archivo de audio...",
            fraction=0.02,
            is_estimated=False,
            processed_seconds=0.0,
            message="Convirtiendo a formato WAV 16kHz mono...",
        )

    # 1. Conversión de Audio
    wav_path = convertir_a_wav_16k(
        audio_path=audio_path,
        output_dir=checkpoint_dir,
        duracion_total=duracion_total,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
    )
    if duracion_total <= 0:
        duracion_total = obtener_duracion(wav_path) or 0.0

    # 2. Transcripción
    segments = None
    meta_info = {}
    tiempo_transcripcion = 0.0

    if reanudar_checkpoint and chk_transcripcion.exists():
        try:
            with open(chk_transcripcion, "r", encoding="utf-8") as f:
                data_chk = json.load(f)
            if data_chk.get("idioma", "es") != idioma:
                segments = None
            else:
                segments = data_chk.get("segments")
                meta_info = data_chk.get("meta_info", {})
                tiempo_transcripcion = data_chk.get("tiempo", 0.0)
                if progress_callback:
                    progress_callback(
                        stage="Transcripción recuperada de checkpoint",
                        fraction=0.50,
                        is_estimated=False,
                        processed_seconds=duracion_total,
                        message=f"Se cargaron {len(segments)} segmentos previos.",
                    )
        except Exception:
            segments = None

    if segments is None:
        t_start_t = time.time()
        segments, meta_info = transcribir_whisper(
            wav_path,
            duracion_total=duracion_total,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            idioma=idioma,
        )
        tiempo_transcripcion = time.time() - t_start_t
        with open(chk_transcripcion, "w", encoding="utf-8") as f:
            json.dump({
                "segments": segments,
                "meta_info": meta_info,
                "tiempo": tiempo_transcripcion,
                "idioma": idioma,
            }, f, ensure_ascii=False, indent=2)

    # 3. Diarización
    diar_segments = None
    tiempo_diarizacion = 0.0

    if not diarizar:
        diar_segments = []
    elif reanudar_checkpoint and chk_diarizacion.exists():
        try:
            with open(chk_diarizacion, "r", encoding="utf-8") as f:
                data_chk = json.load(f)
            spec_actual = _spec_hablantes(num_speakers, min_speakers, max_speakers)
            if data_chk.get("speaker_spec", {"num_speakers": 4}) != spec_actual:
                diar_segments = None
            else:
                diar_segments = data_chk.get("segments")
                tiempo_diarizacion = data_chk.get("tiempo", 0.0)
                if progress_callback:
                    progress_callback(
                        stage="Diarización recuperada de checkpoint",
                        fraction=0.92,
                        is_estimated=False,
                        processed_seconds=duracion_total,
                        message=f"Se cargaron {len(diar_segments)} intervenciones previas.",
                    )
        except Exception:
            diar_segments = None

    if diar_segments is None:
        t_start_d = time.time()
        diar_segments = diarizar_pyannote(
            wav_path,
            duracion_total=duracion_total,
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )
        tiempo_diarizacion = time.time() - t_start_d
        with open(chk_diarizacion, "w", encoding="utf-8") as f:
            json.dump({
                "segments": diar_segments,
                "tiempo": tiempo_diarizacion,
                "speaker_spec": _spec_hablantes(num_speakers, min_speakers, max_speakers),
            }, f, ensure_ascii=False, indent=2)

    # 4. Alineación
    if progress_callback:
        progress_callback(
            stage="Alineando transcripción y hablantes...",
            fraction=0.95,
            is_estimated=False,
            processed_seconds=duracion_total,
            message="Asignando cada frase a su respectivo hablante...",
        )

    aligned_segments = alinear_transcripcion_y_diarizacion(segments, diar_segments)

    # 5. Generación de Archivos
    if progress_callback:
        progress_callback(
            stage="Generando archivos de salida (TXT, SRT, DOCX, JSON)...",
            fraction=0.98,
            is_estimated=False,
            processed_seconds=duracion_total,
            message="Escribiendo archivos en el directorio de salida...",
        )

    metadata = {
        "archivo_original": str(audio_path),
        "duracion_audio_segundos": duracion_total,
        "modelo_transcripcion": f"{motor_actual().modelo} (CTranslate2 {motor_actual().tipo_calculo})",
        "modelo_diarizacion": "pyannote/speaker-diarization-community-1" if diarizar else "sin diarización",
        "backend": "Placa NVIDIA (CUDA)" if motor_actual().dispositivo == "cuda" else "CPU",
        "hablantes_configurados": _desc_hablantes(
            _spec_hablantes(num_speakers, min_speakers, max_speakers)
        ) if diarizar else "sin diarización",
        "tiempo_transcripcion_s": tiempo_transcripcion,
        "tiempo_diarizacion_s": tiempo_diarizacion,
        "tiempo_total_s": time.time() - t_global_inicio,
    }

    archivos_generados = exportar_todo(
        segments=aligned_segments,
        output_dir=target_output_dir,
        base_name=nombre_base,
        speaker_mapping=speaker_mapping,
        metadata=metadata,
    )

    tiempo_total = time.time() - t_global_inicio

    if progress_callback:
        progress_callback(
            stage="¡Transcripción Completada!",
            fraction=1.0,
            is_estimated=False,
            processed_seconds=duracion_total,
            message=f"Finalizado con éxito en {formatear_tiempo(tiempo_total)}.",
        )

    return {
        "archivo": str(audio_path),
        "base_name": nombre_base,
        "duracion_audio": duracion_total,
        "tiempo_procesamiento": tiempo_total,
        "tiempo_transcripcion": tiempo_transcripcion,
        "tiempo_diarizacion": tiempo_diarizacion,
        "archivos": archivos_generados,
        "segmentos": aligned_segments,
        "metadata": metadata,
    }
