#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuración y utilidades del Transcriptor Local.
Manejo seguro de rutas dinámicas (compatible con PyInstaller y ejecución directa).
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import timedelta


def get_base_dir() -> Path:
    """
    Retorna el directorio raíz del proyecto Transcriptor.
    Funciona tanto si se ejecuta como script .py como si se ejecuta como .exe congelado.
    """
    if getattr(sys, "frozen", False):
        # Ejecutándose como ejecutable compilado con PyInstaller
        return Path(sys.executable).parent
    else:
        # Ejecutándose como script de Python
        return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"
BIN_DIR = BASE_DIR / "bin"  # ffmpeg/ffprobe/ffplay incluidos en el instalador

# Crear carpetas si no existen
for d in [INPUT_DIR, OUTPUT_DIR, MODELS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DIARIZATION_MODEL_ID = "pyannote/speaker-diarization-community-1"


def modelos_diarizacion_locales() -> bool:
    """True si el modelo de diarización ya está en la carpeta models/ (no hace falta token ni internet)."""
    snapshots = MODELS_DIR / ("models--" + DIARIZATION_MODEL_ID.replace("/", "--")) / "snapshots"
    return any(snapshots.glob("*/config.yaml"))


# Todos los modelos de Hugging Face viven en models/. Si la diarización ya está
# descargada, se trabaja 100% offline (debe definirse antes de importar huggingface_hub).
os.environ.setdefault("HF_HUB_CACHE", str(MODELS_DIR))
if modelos_diarizacion_locales():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")


def cargar_token_hf() -> str | None:
    """
    Carga el token de Hugging Face de forma segura desde la variable de entorno
    o desde el archivo .env ubicado en la carpeta raíz.
    NUNCA expone el token en código fuente ni en el .exe.
    """
    # 1. Variable de entorno del sistema
    token = os.environ.get("HF_TOKEN")
    if token and token.strip() and token.strip() != "TU_TOKEN_AQUI":
        return token.strip()

    # 2. Archivo .env en la carpeta raíz del proyecto
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if line.startswith("HF_TOKEN="):
                        token_val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if token_val and token_val != "TU_TOKEN_AQUI":
                            return token_val
        except Exception:
            pass

    return None


def guardar_token_hf(token: str) -> bool:
    """Guarda el token en el archivo .env de forma segura."""
    env_path = BASE_DIR / ".env"
    try:
        content = (
            "# CONFIGURACION DEL TRANSCRIPTOR\n"
            "# Token de Hugging Face para modelos de diarizacion (pyannote)\n"
            f"HF_TOKEN={token.strip()}\n"
        )
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False


import shutil


def asegurar_ffmpeg_en_path():
    """Asegura que ffmpeg, ffprobe y ffplay estén en el PATH del sistema o los localiza."""
    if (BIN_DIR / "ffmpeg.exe").exists():
        os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
        return

    if shutil.which("ffmpeg"):
        return
    
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for f in winget_pkgs.glob("**/ffmpeg.exe"):
                bin_dir = str(f.parent)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                return

asegurar_ffmpeg_en_path()


def obtener_duracion(audio_path: str | Path) -> float | None:
    """Obtiene la duración del archivo de audio/video en segundos mediante ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries",
        "format=duration", "-of", "csv=p=0", str(audio_path),
    ]
    try:
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, creationflags=creationflags)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def formatear_tiempo(segundos: float) -> str:
    """Convierte segundos a formato HH:MM:SS."""
    if segundos is None or segundos < 0:
        return "00:00:00"
    total_sec = int(segundos)
    horas = total_sec // 3600
    minutos = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{horas:02d}:{minutos:02d}:{secs:02d}"


def formatear_tiempo_srt(segundos: float) -> str:
    """Convierte segundos a formato SRT: HH:MM:SS,mmm."""
    if segundos is None or segundos < 0:
        return "00:00:00,000"
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    secs = int(segundos % 60)
    milis = int((segundos % 1) * 1000)
    return f"{horas:02d}:{minutos:02d}:{secs:02d},{milis:03d}"

