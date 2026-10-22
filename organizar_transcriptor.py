#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para organizar Transcriptor en Instaladores/04_Transcriptor:
- Copia el instalador Inno Setup generado (Transcriptor_Instalador_1.0.exe).
- Prepara la versión Portable (carpeta con binarios, modelos y ejecutable).
- Genera el archivo .zip de la versión portable.
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Nicolás\Desktop\Proyectos\APPS")
TRANS_DIR = BASE_DIR / "Transcriptor"

SRC_INSTALLER = TRANS_DIR / "instalador" / "salida" / "Transcriptor_Instalador_1.0.exe"
SRC_DIST = TRANS_DIR / "build_instalador" / "dist" / "Transcriptor"
SRC_BIN = TRANS_DIR / "build_instalador" / "bin"
SRC_MODELS = TRANS_DIR / "models"

OUT_BASE = BASE_DIR / "Instaladores" / "04_Transcriptor"
OUT_INSTALLER_DIR = OUT_BASE / "Instalador"
OUT_PORTABLE_DIR = OUT_BASE / "Portable" / "Transcriptor_Portable"
OUT_PORTABLE_ZIP = OUT_BASE / "Portable" / "Transcriptor_Portable.zip"


def main():
    print("================================================================")
    print("   ORGANIZANDO: Transcriptor Local (Diarización de 4 Hablantes) ")
    print("================================================================")

    OUT_INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PORTABLE_DIR.parent.mkdir(parents=True, exist_ok=True)

    # 1. Copiar Instalador
    print("\n[1/3] Copiando instalador .exe...")
    if not SRC_INSTALLER.exists():
        print(f"ERROR: No se encontró el instalador en {SRC_INSTALLER}")
        sys.exit(1)
    
    target_installer = OUT_INSTALLER_DIR / "Transcriptor_Instalador_1.0.exe"
    shutil.copy2(SRC_INSTALLER, target_installer)
    print(f"   -> Instalador listo: {target_installer} ({target_installer.stat().st_size / (1024*1024):.1f} MB)")

    # 2. Preparar versión Portable
    print("\n[2/3] Preparando carpeta Portable completa (con modelos locales)...")
    if OUT_PORTABLE_DIR.exists():
        shutil.rmtree(OUT_PORTABLE_DIR)
    
    # Copiar runtime compilado (Transcriptor.exe + _internal)
    shutil.copytree(SRC_DIST, OUT_PORTABLE_DIR)
    
    # Copiar binarios (ffmpeg, ffprobe, ffplay)
    if SRC_BIN.exists():
        shutil.copytree(SRC_BIN, OUT_PORTABLE_DIR / "bin", dirs_exist_ok=True)
    
    # Copiar modelos Whisper + Pyannote para funcionamiento 100% offline
    if SRC_MODELS.exists():
        shutil.copytree(SRC_MODELS, OUT_PORTABLE_DIR / "models", dirs_exist_ok=True)

    # Carpetas input, output, logs
    (OUT_PORTABLE_DIR / "input").mkdir(exist_ok=True)
    (OUT_PORTABLE_DIR / "output").mkdir(exist_ok=True)
    (OUT_PORTABLE_DIR / "logs").mkdir(exist_ok=True)

    # Agregar LEEME_PORTABLE.txt
    leeme = """Transcriptor Local — Versión Portable (100% Offline)
===================================================

• Esta versión NO requiere instalación ni conexión a internet.
• Incluye los modelos de IA completos: Whisper large-v3-turbo y diarización Pyannote para 4 hablantes.
• Incluye ffmpeg, ffprobe y ffplay preconfigurados.
• Para iniciar: hacé doble clic en "Transcriptor.exe".

Carpetas de trabajo:
- input/  : Colocá aquí tus audios o videos.
- output/ : Aquí se guardan los archivos TXT, SRT, DOCX y JSON.
- logs/   : Registro de ejecuciones.
"""
    with open(OUT_PORTABLE_DIR / "LEEME_PORTABLE.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write(leeme)

    print(f"   -> Carpeta portable lista en: {OUT_PORTABLE_DIR}")

    # 3. Comprimir versión Portable a .zip
    print("\n[3/3] Comprimiendo versión Portable a .zip...")
    if OUT_PORTABLE_ZIP.exists():
        OUT_PORTABLE_ZIP.unlink()

    with zipfile.ZipFile(OUT_PORTABLE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUT_PORTABLE_DIR):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(OUT_PORTABLE_DIR.parent)
                zf.write(file_path, rel_path)

    print(f"   -> Archivo zip creado: {OUT_PORTABLE_ZIP} ({OUT_PORTABLE_ZIP.stat().st_size / (1024*1024):.1f} MB)")

    print("\n================================================================")
    print("   ¡ORGANIZACIÓN EXITOSA DE TRANSCRIPTOR!                       ")
    print(f"   1. Instalador .exe: {target_installer}")
    print(f"   2. Carpeta Portable: {OUT_PORTABLE_DIR}")
    print(f"   3. Portable .zip:   {OUT_PORTABLE_ZIP}")
    print("================================================================")


if __name__ == "__main__":
    main()
