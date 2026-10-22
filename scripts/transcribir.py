#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transcriptor Local con Diarización de Hablantes (CLI runner)
============================================================
Runner en lote basado en src.engine.ejecutar_pipeline_completo.
Procesa archivos individuales o el directorio input/ completo.
"""

import sys
import logging
import argparse
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import cargar_token_hf, modelos_diarizacion_locales
from src.engine import ejecutar_pipeline_completo

# Configurar logging con StreamHandler en UTF-8 y FileHandler a logs/transcripcion.log
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)),
        logging.FileHandler(LOG_DIR / "transcripcion.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def medir_recursos():
    """Mide uso actual de CPU y RAM."""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        return {
            "cpu_percent": cpu_percent,
            "ram_used_gb": ram.used / (1024**3),
            "ram_total_gb": ram.total / (1024**3),
            "ram_percent": ram.percent,
        }
    except ImportError:
        return {"note": "psutil no instalado"}


def _estado_computo(tiempo_total: float, tiempo_computo: float) -> str:
    """
    Clasifica la corrida comparando su reloj contra la suma de las etapas.
    No depende del texto de los mensajes de progreso.

    "sin_computo"    — no hay etapas medidas
    "fresco"         — se ejecutó todo en esta corrida
    "todo_cacheado"  — no se ejecutó nada nuevo
    "parcial"        — alguna etapa vino de checkpoint
    """
    if tiempo_computo <= 0:
        return "sin_computo"
    frac = tiempo_total / tiempo_computo
    if frac >= 0.9:
        return "fresco"
    if frac <= 0.1:
        return "todo_cacheado"
    return "parcial"


def crear_progress_callback():
    """Crea un callback que registra transiciones de etapas en el logger."""
    ultimo_stage = [None]

    def callback(stage="", fraction=0.0, is_estimated=False, processed_seconds=0.0, message=""):
        if stage != ultimo_stage[0]:
            ultimo_stage[0] = stage
            pct = int(fraction * 100)
            logger.info(f"[{pct:2d}%] {stage} {message}".strip())

    return callback


def parse_args():
    """Parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Transcriptor Local con Diarización (CLI runner)")
    parser.add_argument("audio", nargs="?", default=None, help="Archivo de audio a procesar (si se omite, procesa input/)")
    parser.add_argument("--idioma", default="es", help="Idioma de transcripción (default: es)")
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=4,
        help="Cantidad de hablantes (usar 0 para detección automática, default: 4)",
    )
    parser.add_argument(
        "--min-speakers",
        type=int,
        default=None,
        help="Mínimo de hablantes para detección automática (requiere --num-speakers 0)",
    )
    parser.add_argument(
        "--max-speakers",
        type=int,
        default=None,
        help="Máximo de hablantes para detección automática (requiere --num-speakers 0)",
    )
    parser.add_argument(
        "--sin-diarizar",
        action="store_true",
        help="Omitir diarización (pyannote). Mucho más rápido para un solo narrador",
    )
    parser.add_argument("--output", "-o", default=None, help="Directorio de salida (default: output/)")

    args = parser.parse_args()

    num_speakers = None if args.num_speakers == 0 else args.num_speakers

    if (args.min_speakers is not None or args.max_speakers is not None) and num_speakers is not None:
        parser.error(
            "--min-speakers/--max-speakers requieren detección automática.\n"
            "       Agregá --num-speakers 0."
        )

    return args, num_speakers


def main():
    args, num_speakers = parse_args()

    # Verificación temprana del token de Hugging Face si la diarización está activa
    # (no hace falta si el modelo de diarización ya está en models/)
    if not args.sin_diarizar and modelos_diarizacion_locales():
        logger.info("✅ Modelo de diarización disponible localmente (sin token)")
    elif not args.sin_diarizar:
        hf_token = cargar_token_hf()
        if not hf_token:
            logger.error(
                "❌ Token de Hugging Face no configurado.\n"
                "   Editá el archivo .env en la carpeta Transcriptor/\n"
                "   y reemplazá TU_TOKEN_AQUI por tu token."
            )
            sys.exit(1)
        logger.info("✅ Token de Hugging Face cargado correctamente")

    # Carpetas de trabajo
    input_dir = PROJECT_ROOT / "input"
    output_dir = Path(args.output).resolve() if args.output else PROJECT_ROOT / "output"

    # Determinar lista de audios a procesar
    if args.audio:
        archivos = [Path(args.audio)]
    else:
        extensiones = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".aac", ".wma", ".webm", ".opus"}
        archivos = sorted([f for f in input_dir.iterdir() if f.suffix.lower() in extensiones])
        if not archivos:
            logger.error(f"No se encontraron archivos de audio compatibles en {input_dir}")
            sys.exit(1)

    logger.info(f"Archivos a procesar ({len(archivos)}): {[f.name for f in archivos]}")

    for audio in archivos:
        if not audio.exists():
            logger.error(f"Archivo no encontrado: {audio}")
            continue

        try:
            logger.info("=" * 60)
            logger.info(f"PROCESANDO: {audio.name}")
            logger.info("=" * 60)
            logger.info(f"Recursos inicio: {medir_recursos()}")

            cb = crear_progress_callback()
            resultado = ejecutar_pipeline_completo(
                audio_path=audio,
                output_dir=output_dir,
                diarizar=not args.sin_diarizar,
                num_speakers=num_speakers,
                min_speakers=args.min_speakers,
                max_speakers=args.max_speakers,
                idioma=args.idioma,
                progress_callback=cb,
            )

            duracion = resultado.get("duracion_audio") or 0.0
            tiempo_transcripcion = resultado.get("tiempo_transcripcion") or 0.0
            tiempo_diarizacion = resultado.get("tiempo_diarizacion") or 0.0
            tiempo_total = resultado.get("tiempo_procesamiento") or 0.0
            tiempo_computo = tiempo_transcripcion + tiempo_diarizacion
            segmentos = resultado.get("segmentos") or []
            metadata = resultado.get("metadata") or {}
            modelo = metadata.get("modelo_transcripcion", "large-v3-turbo (CTranslate2 int8)")
            backend = metadata.get("backend", "CPU (AMD Ryzen)")
            speakers = sorted(set(s.get("speaker", "SPEAKER 01") for s in segmentos))

            logger.info("=" * 60)
            logger.info("RESUMEN DE PROCESAMIENTO")
            logger.info("=" * 60)
            logger.info(f"Archivo:                {audio.name}")
            logger.info(f"Duración del audio:     {duracion:.1f}s ({duracion/60:.1f} min)" if duracion else "Duración: N/A")
            logger.info(f"Modelo:                 {modelo}")
            logger.info(f"Backend:                {backend}")
            logger.info(f"Tiempo transcripción:   {tiempo_transcripcion:.1f}s")
            logger.info(f"Tiempo diarización:     {tiempo_diarizacion:.1f}s")
            logger.info(f"Tiempo de cómputo:      {tiempo_computo:.1f}s")

            estado = _estado_computo(tiempo_total, tiempo_computo)

            if estado == "fresco":
                logger.info(f"Tiempo de esta corrida: {tiempo_total:.1f}s ({tiempo_total/60:.1f} min)")
            elif estado == "parcial":
                logger.info(f"Tiempo de esta corrida: {tiempo_total:.1f}s (parcialmente desde checkpoint)")
            elif estado == "todo_cacheado":
                logger.info(f"Tiempo de esta corrida: {tiempo_total:.1f}s (recuperado totalmente de checkpoint)")
            else:  # sin_computo
                logger.info(f"Tiempo de esta corrida: {tiempo_total:.1f}s")

            logger.info(f"Segmentos transcritos:  {len(segmentos)}")
            logger.info(f"Hablantes detectados:   {len(speakers)} — {speakers}")

            if estado in ("todo_cacheado", "sin_computo"):
                logger.info("Sin medición nueva de procesamiento (todo recuperado de checkpoint)")
            elif duracion > 0:
                ratio = tiempo_computo / duracion
                logger.info(f"Ratio procesamiento:    {ratio:.2f}x (1x = tiempo real)")
                est_5h = ratio * 5 * 3600
                logger.info(f"Estimación para 5h:     {est_5h/3600:.1f} horas")

            logger.info(f"Recursos finales:       {medir_recursos()}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error procesando {audio.name}: {e}", exc_info=True)
            logger.info("Continuando con el siguiente archivo...")


if __name__ == "__main__":
    main()
