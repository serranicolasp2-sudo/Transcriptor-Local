#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tema visual "Tu Tiendita IA" para la GUI del Transcriptor.

- Paleta de marca (Birome, Tinta, Malvón, Yema, Papel, Plata, Celeste).
- Tema JSON de CustomTkinter en recursos/tema_tutiendita.json.
- Ícono de ventana/barra de tareas, barra de título color Tinta y encabezado con ícono.
"""

import sys
import ctypes
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.config import BASE_DIR

# En el .exe (PyInstaller) los datos empaquetados viven en sys._MEIPASS
RECURSOS_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "recursos"
TEMA_JSON = RECURSOS_DIR / "tema_tutiendita.json"
ICONO_ICO = RECURSOS_DIR / "transcriptor.ico"
ICONO_PNG = RECURSOS_DIR / "transcriptor_256.png"

# --- Paleta oficial ---
BIROME = "#1E3C96"
BIROME_HOVER = "#2A4FC0"
BIROME_LIGHT = "#3A62DE"
TINTA = "#16205A"
MALVON = "#E0435C"
MALVON_SUAVE = "#FF7A90"   # Malvón legible como texto sobre fondo oscuro
YEMA = "#FFD23F"
YEMA_HOVER = "#FFDD66"
CINTA = "#1A1712"
PAPEL = "#F6F7FA"
PLATA = "#95A2C2"
CELESTE = "#AFC0FF"

# --- Superficies (modo oscuro) ---
BG_APP = "#0A1024"
CARD_BORDER = "#25336A"
CHIP_BG = "#17224A"
CHIP_BORDER = "#2E3F7C"
TEXT_DIM = "#56658F"

# Botón de peligro sobrio: no grita cuando está deshabilitado
PELIGRO_FG = "#2A1426"
PELIGRO_HOVER = "#3C1A31"
PELIGRO_BORDE = "#6A2540"

# Tarjeta de éxito (resultados)
EXITO_BG = "#1A2448"


def aplicar_tema_global():
    """Debe llamarse antes de crear la ventana."""
    ctk.set_appearance_mode("Dark")
    if TEMA_JSON.exists():
        ctk.set_default_color_theme(str(TEMA_JSON))
    else:
        ctk.set_default_color_theme("blue")
    try:
        # Ícono propio en la barra de tareas (en vez del de Python)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TuTienditaIA.Transcriptor")
    except Exception:
        pass


def _colorref(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return r | (g << 8) | (b << 16)


def estilizar_barra_titulo(ventana):
    """Barra de título en color Tinta (Windows 11). En Windows 10 queda oscura simple."""
    try:
        ventana.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(ventana.winfo_id())
        dwm = ctypes.windll.dwmapi
        for codigo, valor in ((20, 1), (35, _colorref(BG_APP)), (36, _colorref(PAPEL)), (34, _colorref(CARD_BORDER))):
            v = ctypes.c_int(valor)
            dwm.DwmSetWindowAttribute(hwnd, codigo, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


def aplicar_icono(ventana):
    """Ícono de ventana. Llamarlo en __init__ evita que CTk ponga su logo."""
    if ICONO_ICO.exists():
        try:
            ventana.iconbitmap(str(ICONO_ICO))
        except Exception:
            pass
    # CTk vuelve a pintar la barra de título al arrancar; reaplicamos el color después
    ventana.after(300, lambda: estilizar_barra_titulo(ventana))


def crear_encabezado(parent, titulo: str, subtitulo: str, chip: str = "") -> ctk.CTkFrame:
    """Encabezado con ícono, título, insignia IA, subtítulo y filete de marca."""
    contenedor = ctk.CTkFrame(parent, fg_color="transparent")
    contenedor.grid_columnconfigure(1, weight=1)

    if ICONO_PNG.exists():
        img = ctk.CTkImage(dark_image=Image.open(ICONO_PNG), light_image=Image.open(ICONO_PNG), size=(50, 50))
        ctk.CTkLabel(contenedor, image=img, text="").grid(row=0, column=0, rowspan=2, padx=(4, 14), pady=(2, 0))

    fila = ctk.CTkFrame(contenedor, fg_color="transparent")
    fila.grid(row=0, column=1, sticky="sw")
    ctk.CTkLabel(fila, text=titulo, font=ctk.CTkFont(family="Segoe UI Semibold", size=20), text_color=PAPEL).pack(side="left")
    ctk.CTkLabel(
        fila, text="IA", width=30, height=20, corner_radius=10, fg_color=YEMA, text_color=CINTA,
        font=ctk.CTkFont(size=11, weight="bold"),
    ).pack(side="left", padx=(10, 0), pady=(4, 0))

    ctk.CTkLabel(contenedor, text=subtitulo, font=ctk.CTkFont(size=12), text_color=PLATA).grid(row=1, column=1, sticky="nw")

    if chip:
        ctk.CTkLabel(
            contenedor, text=f"●  {chip}", height=24, corner_radius=12, fg_color=CHIP_BG, text_color=CELESTE,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=2, rowspan=2, padx=(10, 4), ipadx=10)

    # Filete Birome · Malvón · Yema
    filete = ctk.CTkFrame(contenedor, fg_color="transparent", height=3)
    filete.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
    filete.grid_columnconfigure(0, weight=62)
    filete.grid_columnconfigure(1, weight=24)
    filete.grid_columnconfigure(2, weight=14)
    for i, color in enumerate((BIROME_LIGHT, MALVON, YEMA)):
        ctk.CTkFrame(filete, fg_color=color, height=3, corner_radius=0).grid(row=0, column=i, sticky="ew")

    return contenedor
