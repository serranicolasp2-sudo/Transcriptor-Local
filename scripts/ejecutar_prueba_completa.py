#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script para ejecutar una transcripción real corta, verificar la GUI y capturar las 4 pestañas."""

import os
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from PIL import Image

# Agregar raíz al sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.gui import TranscriptorApp
from src.config import INPUT_DIR, OUTPUT_DIR, obtener_duracion, formatear_tiempo

CAPTURAS_DIR = BASE_DIR / "recursos" / "capturas"
CAPTURAS_DIR.mkdir(parents=True, exist_ok=True)


def capturar_ventana(app: TranscriptorApp, ruta_salida: Path):
    """Captura el contenido de la ventana vía PrintWindow (PW_RENDERFULLCONTENT)."""
    app.update_idletasks()
    app.update()

    hwnd = ctypes.windll.user32.GetParent(app.winfo_id()) or app.winfo_id()
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    hwndDC = user32.GetWindowDC(hwnd)
    mfcDC = gdi32.CreateCompatibleDC(hwndDC)
    saveBitMap = gdi32.CreateCompatibleBitmap(hwndDC, w, h)
    gdi32.SelectObject(mfcDC, saveBitMap)
    user32.PrintWindow(hwnd, mfcDC, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mfcDC, saveBitMap, 0, h, buf, ctypes.byref(bmi), 0)

    im = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    im.save(str(ruta_salida))

    gdi32.DeleteObject(saveBitMap)
    gdi32.DeleteDC(mfcDC)
    user32.ReleaseDC(hwnd, hwndDC)
    print(f"[CAPTURA] Guardada: {ruta_salida.name} ({w}x{h})", flush=True)


def run():
    print("Iniciando TranscriptorApp en mainloop para prueba automatizada...", flush=True)
    app = TranscriptorApp()

    archivo_test = INPUT_DIR / "WhatsApp Video 2026-09-23 at 2.33.26 PM.mp4"
    if not archivo_test.exists():
        print(f"ERROR: No se encontró el archivo de prueba: {archivo_test}", flush=True)
        sys.exit(1)

    estado = {
        "progreso_capturado": False,
        "json_generado": None,
    }

    def driver_inicio():
        print(f"Archivo de prueba seleccionado: {archivo_test.name}", flush=True)
        app.archivo_seleccionado = archivo_test
        app.entry_archivo.delete(0, "end")
        app.entry_archivo.insert(0, str(archivo_test))

        dur = obtener_duracion(archivo_test)
        app.duracion_audio = dur
        app.lbl_duracion.configure(text=f"Duración: {formatear_tiempo(dur)} ({dur:.1f} s)")
        app.lbl_m_procesado.configure(text=f"00:00:00 / {formatear_tiempo(dur)}")

        capturar_ventana(app, CAPTURAS_DIR / "01_tab1_inicio.png")

        print("Lanzando _iniciar_transcripcion...", flush=True)
        app._iniciar_transcripcion()
        app.after(500, supervisar_progreso)

    def supervisar_progreso():
        if app.is_processing:
            frac = app.progressbar.get()
            if not estado["progreso_capturado"] and frac >= 0.20:
                print(f"[PROGRESO] Fracción alcanzada: {frac:.2f} ({int(frac * 100)}%)", flush=True)
                capturar_ventana(app, CAPTURAS_DIR / "02_tab1_progreso.png")
                estado["progreso_capturado"] = True
            app.after(500, supervisar_progreso)
        else:
            print("Transcripción finalizada en segundo plano.", flush=True)
            app.after(1000, capturar_completado)

    def capturar_completado():
        capturar_ventana(app, CAPTURAS_DIR / "03_tab1_completado.png")

        if app.ultimo_resultado and "archivos" in app.ultimo_resultado:
            json_str = app.ultimo_resultado["archivos"].get("json")
            if json_str:
                estado["json_generado"] = Path(json_str)

        if not estado["json_generado"] or not estado["json_generado"].exists():
            candidatos = list(OUTPUT_DIR.glob("*_completo.json"))
            if candidatos:
                estado["json_generado"] = candidatos[0]

        print(f"JSON detectado: {estado['json_generado']}", flush=True)
        app.after(500, cargar_tab2)

    def cargar_tab2():
        print("Cambiando a Pestaña 2: Visor y Editor...", flush=True)
        app.tabview.set("Visor y Editor")
        if estado["json_generado"] and estado["json_generado"].exists():
            app._cargar_archivo_en_editor(estado["json_generado"])
        app.after(1000, capturar_tab2)

    def capturar_tab2():
        capturar_ventana(app, CAPTURAS_DIR / "04_tab2_visor_editor.png")
        app.after(500, cargar_tab3)

    def cargar_tab3():
        print("Cambiando a Pestaña 3: Administrar Hablantes...", flush=True)
        app.tabview.set("Administrar Hablantes")
        if estado["json_generado"] and estado["json_generado"].exists():
            app.entry_admin_json.delete(0, "end")
            app.entry_admin_json.insert(0, str(estado["json_generado"]))
            try:
                import json as json_lib
                with open(estado["json_generado"], "r", encoding="utf-8") as f:
                    d = json_lib.load(f)
                    m = d.get("speaker_mapping", {})
                    app.entry_adm_spk1.delete(0, "end")
                    app.entry_adm_spk1.insert(0, m.get("SPEAKER 01", ""))
                    app.entry_adm_spk2.delete(0, "end")
                    app.entry_adm_spk2.insert(0, m.get("SPEAKER 02", ""))
                    app.entry_adm_spk3.delete(0, "end")
                    app.entry_adm_spk3.insert(0, m.get("SPEAKER 03", ""))
                    app.entry_adm_spk4.delete(0, "end")
                    app.entry_adm_spk4.insert(0, m.get("SPEAKER 04", ""))
            except Exception as e:
                print(f"Error cargando datos en tab 3: {e}", flush=True)
        app.after(1000, capturar_tab3)

    def capturar_tab3():
        capturar_ventana(app, CAPTURAS_DIR / "05_tab3_administrar_hablantes.png")
        app.after(500, cargar_tab4)

    def cargar_tab4():
        print("Cambiando a Pestaña 4: Configuración...", flush=True)
        app.tabview.set("Configuración")
        app.after(1000, capturar_tab4)

    def capturar_tab4():
        capturar_ventana(app, CAPTURAS_DIR / "06_tab4_configuracion.png")
        print("Prueba y capturas completadas con éxito total.", flush=True)
        app.quit()

    app.after(300, driver_inicio)
    app.mainloop()
    app.destroy()


if __name__ == "__main__":
    run()
