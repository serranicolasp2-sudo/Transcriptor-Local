#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reemplazar nombres de hablantes en archivos de transcripción.

Uso:
    python reemplazar_nombres.py --carpeta output/ --mapeo "SPEAKER 01=Nicolás" "SPEAKER 02=Juan" "SPEAKER 03=María" "SPEAKER 04=Pedro"

Esto reemplaza los nombres en TODOS los archivos TXT, SRT y DOCX
de la carpeta indicada, SIN necesidad de volver a procesar el audio.
"""

import argparse
import re
import sys
from pathlib import Path


def reemplazar_en_txt(filepath, mapeo):
    """Reemplaza nombres en archivo TXT."""
    with open(filepath, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    for original, nuevo in mapeo.items():
        contenido = contenido.replace(original, nuevo)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(contenido)
    
    print(f"  ✅ TXT actualizado: {filepath.name}")


def reemplazar_en_srt(filepath, mapeo):
    """Reemplaza nombres en archivo SRT."""
    with open(filepath, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    for original, nuevo in mapeo.items():
        contenido = contenido.replace(original, nuevo)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(contenido)
    
    print(f"  ✅ SRT actualizado: {filepath.name}")


def reemplazar_en_docx(filepath, mapeo):
    """Reemplaza nombres en archivo DOCX."""
    try:
        from docx import Document
    except ImportError:
        print(f"  ⚠️ python-docx no instalado. Omitiendo {filepath.name}")
        return
    
    doc = Document(str(filepath))
    
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            for original, nuevo in mapeo.items():
                if original in run.text:
                    run.text = run.text.replace(original, nuevo)
    
    doc.save(str(filepath))
    print(f"  ✅ DOCX actualizado: {filepath.name}")


def reemplazar_en_json(filepath, mapeo):
    """Reemplaza nombres en archivo JSON."""
    import json
    
    with open(filepath, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    for original, nuevo in mapeo.items():
        contenido = contenido.replace(original, nuevo)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(contenido)
    
    print(f"  ✅ JSON actualizado: {filepath.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Reemplazar nombres de hablantes en transcripciones"
    )
    parser.add_argument(
        "--carpeta", 
        default=str(Path(__file__).parent.parent / "output"),
        help="Carpeta con archivos de transcripción (default: output/)"
    )
    parser.add_argument(
        "--mapeo", 
        nargs="+", 
        required=True,
        help='Pares "SPEAKER 01=Nombre" separados por espacios'
    )
    args = parser.parse_args()
    
    # Parsear mapeo
    mapeo = {}
    for par in args.mapeo:
        if "=" not in par:
            print(f"❌ Formato incorrecto: {par}. Usá: \"SPEAKER 01=Nombre\"")
            sys.exit(1)
        original, nuevo = par.split("=", 1)
        mapeo[original.strip()] = nuevo.strip()
    
    print(f"Mapeo de nombres:")
    for original, nuevo in mapeo.items():
        print(f"  {original} → {nuevo}")
    print()
    
    carpeta = Path(args.carpeta)
    if not carpeta.exists():
        print(f"❌ La carpeta {carpeta} no existe.")
        sys.exit(1)
    
    # Procesar archivos
    archivos_procesados = 0
    
    for filepath in carpeta.iterdir():
        if filepath.suffix.lower() == ".txt":
            reemplazar_en_txt(filepath, mapeo)
            archivos_procesados += 1
        elif filepath.suffix.lower() == ".srt":
            reemplazar_en_srt(filepath, mapeo)
            archivos_procesados += 1
        elif filepath.suffix.lower() == ".docx":
            reemplazar_en_docx(filepath, mapeo)
            archivos_procesados += 1
        elif filepath.suffix.lower() == ".json":
            reemplazar_en_json(filepath, mapeo)
            archivos_procesados += 1
    
    if archivos_procesados == 0:
        print("⚠️ No se encontraron archivos para actualizar.")
    else:
        print(f"\n✅ {archivos_procesados} archivos actualizados.")


if __name__ == "__main__":
    main()
