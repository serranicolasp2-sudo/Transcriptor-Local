#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Punto de entrada principal para Transcriptor Local.
Ejecuta la interfaz gráfica o modo línea de comandos.
"""

import sys
from pathlib import Path

# Asegurar que el directorio raíz esté en el PYTHONPATH
BASE_PATH = Path(__file__).resolve().parent
if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

import src.config  # noqa: F401 — define HF_HUB_CACHE/OFFLINE y PATH de ffmpeg antes que el resto
from src.gui import main as gui_main
from src.engine import ejecutar_pipeline_completo


def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ["--gui", "-g"]:
        # Modo CLI si se pasa un archivo como argumento
        archivo = sys.argv[1]
        print(f"Ejecutando transcripción por consola para: {archivo}")
        ejecutar_pipeline_completo(archivo)
    else:
        # Modo Interfaz Gráfica por defecto
        gui_main()


if __name__ == "__main__":
    main()
