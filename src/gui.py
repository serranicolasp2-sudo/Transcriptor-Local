#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interfaz Gráfica de Usuario (GUI) del Transcriptor Local.
Desarrollada con CustomTkinter (Estilo Windows 11 Fluent).
Multi-hilo, tolerante a fallos, soporte para checkpoints y visor/editor interactivo.
"""

import os
import sys
import time
import json
import psutil
import platform
import queue
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

import customtkinter as ctk
from tkinter import filedialog, messagebox

from src.config import (
    BASE_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    MODELS_DIR,
    LOGS_DIR,
    cargar_token_hf,
    guardar_token_hf,
    modelos_diarizacion_locales,
    obtener_duracion,
    formatear_tiempo,
)
from src.engine import (
    ejecutar_pipeline_completo,
    verificar_checkpoint,
    motor_actual,
)
from src import componentes
from src.exporter import (
    exportar_todo,
    reexportar_desde_json,
)
from src.player import AudioPlayer
from src import tema

# Configuración visual: paleta "Tu Tiendita IA" (src/tema.py + recursos/tema_tutiendita.json)
tema.aplicar_tema_global()


def _detectar_hardware_sistema() -> tuple:
    """Detecta dinámicamente el procesador y la memoria RAM del equipo actual."""
    import platform
    cpu_name = platform.processor() or "Procesador x64"
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except Exception:
            pass

    cores_fisicos = psutil.cpu_count(logical=False)
    cores_logicos = psutil.cpu_count(logical=True)
    if cores_fisicos and cores_logicos:
        cpu_desc = f"{cpu_name} ({cores_fisicos} núcleos / {cores_logicos} hilos)"
    elif cores_logicos:
        cpu_desc = f"{cpu_name} ({cores_logicos} hilos)"
    else:
        cpu_desc = cpu_name

    try:
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024 ** 3)
        disp_gb = mem.available / (1024 ** 3)
        ram_desc = f"{total_gb:.1f} GB (Disponible: {disp_gb:.1f} GB | Consumo estimado: ~11 GB)"
    except Exception:
        ram_desc = "No detectada (Recomendado: 16 GB)"

    return cpu_desc, ram_desc


class TranscriptorApp(ctk.CTk):
    """Ventana principal de la aplicación Transcriptor Local."""

    def __init__(self):
        super().__init__()

        self.title("Transcriptor Local — Diarización de 4 Hablantes")
        self.geometry("1000x870")
        self.minsize(880, 720)
        tema.aplicar_icono(self)

        # Variables de estado
        self.archivo_seleccionado: Optional[Path] = None
        self.duracion_audio: float = 0.0
        self.is_processing: bool = False
        self.cancel_event: Optional[threading.Event] = None
        self.tiempo_inicio_proceso: float = 0.0
        self.ultimo_resultado: Optional[Dict[str, Any]] = None
        self.player = AudioPlayer()
        self.descarga_cancelar: Optional[threading.Event] = None  # descarga de componente en curso
        self.eventos_descarga: "queue.Queue[tuple]" = queue.Queue()  # el hilo de descarga avisa por acá
        self.filas_componentes: Dict[str, Dict[str, Any]] = {}
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        # Configurar grid principal
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Encabezado con ícono y filete de marca
        tema.crear_encabezado(
            self,
            titulo="Transcriptor",
            subtitulo=f"Transcripción local con Whisper {motor_actual().modelo} y diarización de 4 hablantes.",
            chip="100% LOCAL",
        ).grid(row=0, column=0, padx=22, pady=(16, 4), sticky="ew")

        # Crear Tabs
        self.tabview = ctk.CTkTabview(
            self, corner_radius=14, border_width=1, border_color=tema.CARD_BORDER,
            segmented_button_fg_color=tema.CHIP_BG, segmented_button_unselected_color=tema.CHIP_BG,
        )
        self.tabview.grid(row=1, column=0, padx=15, pady=(4, 15), sticky="nsew")
        self.tabview._segmented_button.configure(font=ctk.CTkFont(family="Segoe UI Semibold", size=13), height=34)

        self.tab_transcribir = self.tabview.add("Transcripción")
        self.tab_editor = self.tabview.add("Visor y Editor")
        self.tab_hablantes = self.tabview.add("Administrar Hablantes")
        self.tab_config = self.tabview.add("Configuración")

        # Construir cada pestaña
        self._setup_tab_transcribir()
        self._setup_tab_editor()
        self._setup_tab_hablantes()
        self._setup_tab_config()

        # Iniciar monitor de recursos en segundo plano
        self._iniciar_monitor_recursos()

    # =========================================================================
    # PESTAÑA 1: TRANSCRIPCIÓN (PRINCIPAL)
    # =========================================================================
    def _setup_tab_transcribir(self):
        tab = self.tab_transcribir
        tab.grid_columnconfigure(0, weight=1)

        # --- Card 1: Selección de Archivo ---
        frame_file = ctk.CTkFrame(tab, corner_radius=12, border_width=1)
        frame_file.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        frame_file.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_file, text="Archivo:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=(15, 10), pady=8, sticky="w")
        
        self.entry_archivo = ctk.CTkEntry(frame_file, placeholder_text="Seleccioná un archivo de audio o video (.mp3, .wav, .m4a, .mp4, .flac, etc.)", height=34)
        self.entry_archivo.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        btn_examinar = ctk.CTkButton(frame_file, text="Examinar...", width=110, height=34, command=self._seleccionar_archivo)
        btn_examinar.grid(row=0, column=2, padx=(5, 15), pady=8)

        self.lbl_duracion = ctk.CTkLabel(frame_file, text="Duración: --:--:--", font=ctk.CTkFont(size=12), text_color=tema.PLATA)
        self.lbl_duracion.grid(row=1, column=1, padx=5, pady=(0, 6), sticky="w")

        # --- Card 2: Configuración de los 4 Hablantes ---
        frame_speakers = ctk.CTkFrame(tab, corner_radius=12, border_width=1)
        frame_speakers.grid(row=1, column=0, padx=10, pady=4, sticky="ew")
        frame_speakers.grid_columnconfigure((1, 3), weight=1)

        lbl_spk_title = ctk.CTkLabel(
            frame_speakers,
            text="Hablantes Configurados: Exactamente 4 personas (Capa de presentación modificable)",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        lbl_spk_title.grid(row=0, column=0, columnspan=4, padx=15, pady=(8, 6), sticky="w")

        ctk.CTkLabel(frame_speakers, text="SPEAKER 01 →").grid(row=1, column=0, padx=(15, 5), pady=4, sticky="e")
        self.entry_spk1 = ctk.CTkEntry(frame_speakers, placeholder_text="Nombre 1 (ej. Nicolás)")
        self.entry_spk1.grid(row=1, column=1, padx=5, pady=4, sticky="ew")

        ctk.CTkLabel(frame_speakers, text="SPEAKER 02 →").grid(row=1, column=2, padx=(15, 5), pady=4, sticky="e")
        self.entry_spk2 = ctk.CTkEntry(frame_speakers, placeholder_text="Nombre 2 (ej. Juan)")
        self.entry_spk2.grid(row=1, column=3, padx=(5, 15), pady=4, sticky="ew")

        ctk.CTkLabel(frame_speakers, text="SPEAKER 03 →").grid(row=2, column=0, padx=(15, 5), pady=(4, 8), sticky="e")
        self.entry_spk3 = ctk.CTkEntry(frame_speakers, placeholder_text="Nombre 3 (ej. María)")
        self.entry_spk3.grid(row=2, column=1, padx=5, pady=(4, 8), sticky="ew")

        ctk.CTkLabel(frame_speakers, text="SPEAKER 04 →").grid(row=2, column=2, padx=(15, 5), pady=(4, 8), sticky="e")
        self.entry_spk4 = ctk.CTkEntry(frame_speakers, placeholder_text="Nombre 4 (ej. Pedro)")
        self.entry_spk4.grid(row=2, column=3, padx=(5, 15), pady=(4, 8), sticky="ew")

        # --- Card 3: Carpeta de Salida y Acciones ---
        frame_actions = ctk.CTkFrame(tab, corner_radius=12, border_width=1)
        frame_actions.grid(row=2, column=0, padx=10, pady=4, sticky="ew")
        frame_actions.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_actions, text="Carpeta de salida:").grid(row=0, column=0, padx=(15, 10), pady=8, sticky="w")
        self.entry_output = ctk.CTkEntry(frame_actions, height=32)
        self.entry_output.insert(0, str(OUTPUT_DIR))
        self.entry_output.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        btn_output = ctk.CTkButton(frame_actions, text="Elegir...", width=90, height=32, command=self._seleccionar_carpeta_salida)
        btn_output.grid(row=0, column=2, padx=(5, 15), pady=8)

        frame_buttons = ctk.CTkFrame(frame_actions, fg_color="transparent")
        frame_buttons.grid(row=1, column=0, columnspan=3, padx=15, pady=(2, 8), sticky="ew")
        frame_buttons.grid_columnconfigure((0, 1), weight=1)

        self.btn_iniciar = ctk.CTkButton(
            frame_buttons,
            text="▶ INICIAR TRANSCRIPCIÓN",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            command=self._iniciar_transcripcion,
        )
        self.btn_iniciar.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.btn_cancelar = ctk.CTkButton(
            frame_buttons,
            text="⏹ CANCELAR",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=tema.PELIGRO_FG,
            hover_color=tema.PELIGRO_HOVER,
            border_width=1,
            border_color=tema.PELIGRO_BORDE,
            text_color=tema.MALVON_SUAVE,
            height=42,
            state="disabled",
            command=self._cancelar_transcripcion,
        )
        self.btn_cancelar.grid(row=0, column=1, padx=(10, 0), sticky="ew")

        # --- Card 4: Progreso y Métricas en Tiempo Real ---
        frame_progress = ctk.CTkFrame(tab, corner_radius=12, border_width=1)
        frame_progress.grid(row=3, column=0, padx=10, pady=4, sticky="ew")
        frame_progress.grid_columnconfigure(0, weight=1)

        self.lbl_estado = ctk.CTkLabel(
            frame_progress,
            text="ESTADO: Listo para iniciar",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.lbl_estado.grid(row=0, column=0, padx=15, pady=(10, 4), sticky="w")

        self.progressbar = ctk.CTkProgressBar(frame_progress, height=10)
        self.progressbar.grid(row=1, column=0, padx=15, pady=6, sticky="ew")
        self.progressbar.set(0.0)

        self.lbl_detalle_progreso = ctk.CTkLabel(
            frame_progress,
            text="Esperando inicio del proceso...",
            font=ctk.CTkFont(size=11),
            text_color=tema.PLATA,
            anchor="w",
        )
        self.lbl_detalle_progreso.grid(row=2, column=0, padx=15, pady=(2, 8), sticky="w")

        # Fila de métricas (stat tiles)
        frame_metrics = ctk.CTkFrame(frame_progress, fg_color="transparent")
        frame_metrics.grid(row=3, column=0, padx=15, pady=(4, 12), sticky="ew")
        frame_metrics.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def _crear_tile(col: int, titulo: str, valor_inicial: str) -> ctk.CTkLabel:
            tile = ctk.CTkFrame(
                frame_metrics,
                corner_radius=8,
                border_width=1,
                border_color=tema.CARD_BORDER,
                fg_color=tema.CHIP_BG,
            )
            tile.grid(row=0, column=col, padx=4, pady=2, sticky="ew")
            tile.grid_columnconfigure(0, weight=1)
            lbl_title = ctk.CTkLabel(
                tile,
                text=titulo.upper(),
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=tema.PLATA,
            )
            lbl_title.grid(row=0, column=0, padx=10, pady=(6, 1), sticky="w")
            lbl_val = ctk.CTkLabel(
                tile,
                text=valor_inicial,
                font=ctk.CTkFont(family="Segoe UI Semibold", size=13),
                text_color=tema.PAPEL,
            )
            lbl_val.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="w")
            return lbl_val

        self.lbl_m_procesado = _crear_tile(0, "Audio Procesado", "00:00:00 / 00:00:00")
        self.lbl_m_transcurrido = _crear_tile(1, "Tiempo Transcurrido", "00:00:00")
        self.lbl_m_restante = _crear_tile(2, "Tiempo Restante", "--:--:--")
        self.lbl_m_ram = _crear_tile(3, "Memoria RAM", "-- GB / 32 GB")

        # --- Card 5: Resultados (Oculto inicialmente) ---
        self.frame_results = ctk.CTkFrame(tab, corner_radius=12, border_width=1, border_color=tema.YEMA, fg_color=tema.EXITO_BG)
        self.frame_results.grid(row=4, column=0, padx=10, pady=(4, 6), sticky="ew")
        self.frame_results.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.frame_results.grid_remove()  # Ocultar hasta finalizar

        self.lbl_results_title = ctk.CTkLabel(
            self.frame_results,
            text="✅ TRANSCRIPCIÓN COMPLETADA",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=tema.YEMA,
        )
        self.lbl_results_title.grid(row=0, column=0, columnspan=4, padx=15, pady=(10, 4), sticky="w")

        self.lbl_results_info = ctk.CTkLabel(
            self.frame_results,
            text="Archivos generados: TXT, SRT, DOCX, JSON",
            font=ctk.CTkFont(size=12),
        )
        self.lbl_results_info.grid(row=1, column=0, columnspan=4, padx=15, pady=(0, 8), sticky="w")

        btn_open_folder = ctk.CTkButton(self.frame_results, text="📂 Abrir Carpeta", height=32, command=self._abrir_carpeta_salida)
        btn_open_folder.grid(row=2, column=0, padx=5, pady=(0, 12), sticky="ew")

        btn_open_txt = ctk.CTkButton(self.frame_results, text="📄 Abrir TXT", height=32, command=self._abrir_archivo_txt)
        btn_open_txt.grid(row=2, column=1, padx=5, pady=(0, 12), sticky="ew")

        btn_open_docx = ctk.CTkButton(self.frame_results, text="📑 Abrir DOCX", height=32, command=self._abrir_archivo_docx)
        btn_open_docx.grid(row=2, column=2, padx=5, pady=(0, 12), sticky="ew")

        btn_view_editor = ctk.CTkButton(self.frame_results, text="📝 Abrir en Visor", height=32, fg_color=tema.YEMA, hover_color=tema.YEMA_HOVER, text_color=tema.CINTA, command=self._cargar_en_visor_actual)
        btn_view_editor.grid(row=2, column=3, padx=(5, 10), pady=(0, 12), sticky="ew")

    def _seleccionar_archivo(self):
        """Abre diálogo para seleccionar archivo de audio/video."""
        tipos_archivo = [
            ("Archivos de Audio/Video", "*.mp3 *.wav *.m4a *.mp4 *.aac *.flac *.ogg *.wma *.webm *.opus *.mkv"),
            ("Archivos de Audio", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.wma *.opus"),
            ("Archivos de Video", "*.mp4 *.webm *.mkv *.avi *.mov"),
            ("Todos los archivos", "*.*"),
        ]
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo para transcribir",
            initialdir=str(INPUT_DIR if INPUT_DIR.exists() else BASE_DIR),
            filetypes=tipos_archivo,
        )
        if ruta:
            self.archivo_seleccionado = Path(ruta)
            self.entry_archivo.delete(0, "end")
            self.entry_archivo.insert(0, str(self.archivo_seleccionado))

            # Obtener duración
            dur = obtener_duracion(self.archivo_seleccionado)
            if dur and dur > 0:
                self.duracion_audio = dur
                self.lbl_duracion.configure(text=f"Duración: {formatear_tiempo(dur)} ({dur:.1f} s)")
                self.lbl_m_procesado.configure(text=f"00:00:00 / {formatear_tiempo(dur)}")
            else:
                self.duracion_audio = 0.0
                self.lbl_duracion.configure(text="Duración: Detectando al procesar...")

            self.frame_results.grid_remove()

    def _seleccionar_carpeta_salida(self):
        """Selecciona la carpeta de destino de las transcripciones."""
        ruta = filedialog.askdirectory(
            title="Seleccionar carpeta de salida",
            initialdir=self.entry_output.get() or str(OUTPUT_DIR),
        )
        if ruta:
            self.entry_output.delete(0, "end")
            self.entry_output.insert(0, str(Path(ruta)))

    def _obtener_speaker_mapping(self) -> Dict[str, str]:
        """Obtiene el mapeo de nombres de los 4 hablantes."""
        return {
            "SPEAKER 01": self.entry_spk1.get().strip() or "SPEAKER 01",
            "SPEAKER 02": self.entry_spk2.get().strip() or "SPEAKER 02",
            "SPEAKER 03": self.entry_spk3.get().strip() or "SPEAKER 03",
            "SPEAKER 04": self.entry_spk4.get().strip() or "SPEAKER 04",
        }

    def _iniciar_transcripcion(self):
        """Inicia el proceso de transcripción en un hilo secundario."""
        if not self.archivo_seleccionado or not self.archivo_seleccionado.exists():
            messagebox.showerror("Error", "Por favor seleccioná un archivo de audio o video válido.")
            return

        # Verificar token HF
        if not cargar_token_hf() and not modelos_diarizacion_locales():
            messagebox.showerror(
                "Token Hugging Face Requerido",
                "No se encontró el token de Hugging Face en el archivo .env.\n"
                "Por favor configuralo en la pestaña 'Configuración'.",
            )
            self.tabview.set("Configuración")
            return

        out_dir = Path(self.entry_output.get().strip() or OUTPUT_DIR)
        
        # Verificar si hay checkpoint previo
        chk_info = verificar_checkpoint(self.archivo_seleccionado, out_dir)
        reanudar = True
        if chk_info["transcripcion"] or chk_info["diarizacion"]:
            msg = (
                f"Se encontró un procesamiento previo para '{self.archivo_seleccionado.name}'.\n\n"
                f"- Transcripción guardada: {'Sí' if chk_info['transcripcion'] else 'No'}\n"
                f"- Diarización guardada: {'Sí' if chk_info['diarizacion'] else 'No'}\n\n"
                "¿Deseás CONTINUAR desde el último checkpoint?\n"
                "(Elegí 'No' para empezar desde cero)"
            )
            resp = messagebox.askyesno("Checkpoint detectado", msg)
            reanudar = resp

        # Configurar estado de UI
        self.is_processing = True
        self.cancel_event = threading.Event()
        self.tiempo_inicio_proceso = time.time()
        self.btn_iniciar.configure(state="disabled")
        self.btn_cancelar.configure(state="normal")
        self.frame_results.grid_remove()

        spk_mapping = self._obtener_speaker_mapping()

        # Iniciar reloj continuo en vivo de 1 segundo
        self.after(1000, self._tick_live_timer)

        # Lanzar hilo de procesamiento
        thread = threading.Thread(
            target=self._worker_transcripcion,
            args=(self.archivo_seleccionado, out_dir, spk_mapping, reanudar),
            daemon=True,
        )
        thread.start()

    def _tick_live_timer(self):
        """Actualiza el reloj de tiempo transcurrido y RAM cada 1 segundo mientras esté procesando."""
        if not self.is_processing:
            return
        elapsed = time.time() - self.tiempo_inicio_proceso
        self.lbl_m_transcurrido.configure(text=formatear_tiempo(elapsed))
        try:
            mem = psutil.virtual_memory()
            self.lbl_m_ram.configure(text=f"{mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.0f} GB")
        except Exception:
            pass
        self.after(1000, self._tick_live_timer)

    def _worker_transcripcion(self, audio_path: Path, out_dir: Path, spk_mapping: Dict[str, str], reanudar: bool):
        """Worker en segundo plano para ejecutar la pipeline sin congelar la GUI."""
        try:
            resultado = ejecutar_pipeline_completo(
                audio_path=audio_path,
                output_dir=out_dir,
                speaker_mapping=spk_mapping,
                progress_callback=self._on_progress_update,
                cancel_event=self.cancel_event,
                reanudar_checkpoint=reanudar,
            )
            self.after(0, self._on_proceso_completado, resultado)
        except InterruptedError as e:
            self.after(0, self._on_proceso_cancelado, str(e))
        except Exception as e:
            self.after(0, self._on_proceso_error, str(e))

    def _on_progress_update(self, stage: str, fraction: float, is_estimated: bool, processed_seconds: float, message: str):
        """Actualiza la barra de progreso y métricas en el hilo principal."""
        self.after(0, self._actualizar_gui_progreso, stage, fraction, is_estimated, processed_seconds, message)

    def _actualizar_gui_progreso(self, stage: str, fraction: float, is_estimated: bool, processed_seconds: float, message: str):
        if not self.is_processing:
            return

        pct = int(min(1.0, max(0.0, fraction)) * 100)
        est_tag = " (Estimado)" if is_estimated else ""
        self.lbl_estado.configure(text=f"ESTADO: {stage}")
        self.progressbar.set(fraction)
        self.lbl_detalle_progreso.configure(text=f"{message} — {pct}%{est_tag}")

        # Tiempos
        elapsed = time.time() - self.tiempo_inicio_proceso
        self.lbl_m_transcurrido.configure(text=formatear_tiempo(elapsed))

        dur_total = self.duracion_audio
        if dur_total > 0:
            self.lbl_m_procesado.configure(text=f"{formatear_tiempo(processed_seconds)} / {formatear_tiempo(dur_total)}")
            
            # Estimación restante basada en ratio medido (~0.96x)
            if fraction > 0.05:
                # Estimamos tiempo total esperado = elapsed / fraction
                total_est = elapsed / fraction
                remaining = max(0.0, total_est - elapsed)
                self.lbl_m_restante.configure(text=formatear_tiempo(remaining))
            else:
                est_5h_factor = 0.96
                remaining_init = max(0.0, (dur_total * est_5h_factor) - elapsed)
                self.lbl_m_restante.configure(text=formatear_tiempo(remaining_init))

    def _cancelar_transcripcion(self):
        """Señala al motor que cancele la ejecución conservando checkpoints."""
        if self.cancel_event and not self.cancel_event.is_set():
            self.cancel_event.set()
            self.lbl_estado.configure(text="ESTADO: Cancelando y guardando checkpoint...")
            self.btn_cancelar.configure(state="disabled")

    def _on_proceso_completado(self, resultado: Dict[str, Any]):
        """Callback cuando la transcripción finaliza exitosamente."""
        self.is_processing = False
        self.ultimo_resultado = resultado
        self.btn_iniciar.configure(state="normal")
        self.btn_cancelar.configure(state="disabled")
        self.progressbar.set(1.0)
        self.lbl_estado.configure(text="ESTADO: ¡Completado con éxito!")
        self.lbl_detalle_progreso.configure(text="Archivos TXT, SRT, DOCX y JSON generados correctamente.")

        t_total = resultado.get("tiempo_procesamiento", 0.0)
        dur = resultado.get("duracion_audio", 0.0)
        self.lbl_results_info.configure(
            text=f"Audio: {Path(resultado['archivo']).name} ({formatear_tiempo(dur)}) | Tiempo de cómputo: {formatear_tiempo(t_total)} | Hablantes: 4",
        )
        self.frame_results.grid()

    def _on_proceso_cancelado(self, motivo: str):
        """Callback cuando el proceso es cancelado."""
        self.is_processing = False
        self.btn_iniciar.configure(state="normal")
        self.btn_cancelar.configure(state="disabled")
        self.lbl_estado.configure(text="ESTADO: Proceso cancelado.")
        self.lbl_detalle_progreso.configure(text=f"Se conservaron los checkpoints válidos. Podés reanudar en cualquier momento.")
        messagebox.showinfo("Proceso Cancelado", "El procesamiento fue detenido.\nLos checkpoints se conservaron para que puedas reanudar luego.")

    def _on_proceso_error(self, error_msg: str):
        """Callback en caso de error durante la ejecución."""
        self.is_processing = False
        self.btn_iniciar.configure(state="normal")
        self.btn_cancelar.configure(state="disabled")
        self.lbl_estado.configure(text="ESTADO: Error en el procesamiento.")
        self.lbl_detalle_progreso.configure(text=f"Error: {error_msg}")
        messagebox.showerror("Error de Procesamiento", f"Ocurrió un error:\n{error_msg}")

    def _abrir_carpeta_salida(self):
        """Abre la carpeta de salida en el Explorador de Windows."""
        out = Path(self.entry_output.get().strip() or OUTPUT_DIR)
        if out.exists():
            os.startfile(str(out))

    def _abrir_archivo_txt(self):
        """Abre el archivo TXT generado con el visor predeterminado."""
        if self.ultimo_resultado and "archivos" in self.ultimo_resultado:
            txt = self.ultimo_resultado["archivos"].get("txt")
            if txt and Path(txt).exists():
                os.startfile(str(txt))

    def _abrir_archivo_docx(self):
        """Abre el archivo DOCX generado."""
        if self.ultimo_resultado and "archivos" in self.ultimo_resultado:
            docx = self.ultimo_resultado["archivos"].get("docx")
            if docx and Path(docx).exists():
                os.startfile(str(docx))

    def _cargar_en_visor_actual(self):
        """Carga el resultado recién procesado en la pestaña Visor y cambia de tab."""
        if self.ultimo_resultado and "archivos" in self.ultimo_resultado:
            json_file = self.ultimo_resultado["archivos"].get("json")
            if json_file and Path(json_file).exists():
                self._cargar_archivo_en_editor(Path(json_file))
                self.tabview.set("Visor y Editor")

    # =========================================================================
    # PESTAÑA 2: VISOR Y EDITOR DE TRANSCRIPCIÓN CON REPRODUCCIÓN POR TIMESTAMP
    # =========================================================================
    def _setup_tab_editor(self):
        tab = self.tab_editor
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Header: Selector de JSON
        frame_top = ctk.CTkFrame(tab, corner_radius=12, border_width=1)
        frame_top.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="ew")
        frame_top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_top, text="Cargar Transcripción (.JSON):", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(15, 10), pady=10, sticky="w")
        
        self.entry_json_editor = ctk.CTkEntry(frame_top, placeholder_text="Seleccioná un archivo *_completo.json generado en output/")
        self.entry_json_editor.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        btn_examinar_json = ctk.CTkButton(frame_top, text="Examinar...", width=100, command=self._seleccionar_json_editor)
        btn_examinar_json.grid(row=0, column=2, padx=(5, 10), pady=10)

        btn_cargar = ctk.CTkButton(frame_top, text="Cargar", width=80, fg_color=tema.YEMA, hover_color=tema.YEMA_HOVER, text_color=tema.CINTA, command=self._cargar_json_click)
        btn_cargar.grid(row=0, column=3, padx=(0, 15), pady=10)

        # Contenedor Scrollable para los segmentos
        self.scroll_editor = ctk.CTkScrollableFrame(tab, corner_radius=12, border_width=1)
        self.scroll_editor.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.scroll_editor.grid_columnconfigure(0, weight=1)

        # Barra inferior de guardado
        frame_bottom = ctk.CTkFrame(tab, corner_radius=12, border_width=1)
        frame_bottom.grid(row=2, column=0, padx=10, pady=(8, 10), sticky="ew")
        frame_bottom.grid_columnconfigure(0, weight=1)

        self.lbl_editor_status = ctk.CTkLabel(frame_bottom, text="Cargá un archivo .json para ver y editar los segmentos con audio.", text_color=tema.PLATA)
        self.lbl_editor_status.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        btn_guardar_editor = ctk.CTkButton(
            frame_bottom,
            text="💾 Guardar Cambios y Re-exportar (TXT/SRT/DOCX)",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
            command=self._guardar_cambios_editor,
        )
        btn_guardar_editor.grid(row=0, column=1, padx=15, pady=10, sticky="e")

        self.segment_widgets: List[Dict[str, Any]] = []
        self.current_editor_json: Optional[Path] = None
        self.current_editor_audio: Optional[Path] = None

    def _seleccionar_json_editor(self):
        """Selecciona un archivo JSON desde el explorador."""
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo JSON de transcripción",
            initialdir=str(OUTPUT_DIR),
            filetypes=[("Archivos JSON", "*.json")],
        )
        if ruta:
            self.entry_json_editor.delete(0, "end")
            self.entry_json_editor.insert(0, str(Path(ruta)))
            self._cargar_archivo_en_editor(Path(ruta))

    def _cargar_json_click(self):
        ruta = self.entry_json_editor.get().strip()
        if ruta and Path(ruta).exists():
            self._cargar_archivo_en_editor(Path(ruta))

    def _cargar_archivo_en_editor(self, json_path: Path):
        """Carga y renderiza los segmentos del JSON en el visor."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error al leer JSON", f"No se pudo abrir el archivo:\n{e}")
            return

        self.current_editor_json = json_path
        self.entry_json_editor.delete(0, "end")
        self.entry_json_editor.insert(0, str(json_path))

        # Detectar ruta del audio original para reproducción
        metadata = data.get("metadata", {})
        audio_orig = metadata.get("archivo_original")
        if audio_orig and Path(audio_orig).exists():
            self.current_editor_audio = Path(audio_orig)
        else:
            # Buscar en input/ o checkpoints
            base = json_path.stem.replace("_completo", "")
            chk_wav = json_path.parent / f".checkpoint_{base}" / f"{base}_16khz.wav"
            if chk_wav.exists():
                self.current_editor_audio = chk_wav
            else:
                self.current_editor_audio = None

        # Limpiar widgets previos
        for w in self.scroll_editor.winfo_children():
            w.destroy()
        self.segment_widgets.clear()

        segments = data.get("segments") or data.get("segmentos") or []
        spk_mapping = data.get("speaker_mapping", {})

        for i, seg in enumerate(segments):
            seg_start = seg.get("start", 0.0)
            seg_end = seg.get("end", 0.0)
            seg_dur = max(0.5, seg_end - seg_start)
            raw_spk = seg.get("speaker", "SPEAKER 01")
            display_spk = spk_mapping.get(raw_spk, raw_spk)
            text = seg.get("text", "")

            frame_seg = ctk.CTkFrame(
                self.scroll_editor,
                corner_radius=8,
                border_width=1,
                border_color=tema.CARD_BORDER,
                fg_color=tema.CHIP_BG,
            )
            frame_seg.grid(row=i, column=0, padx=5, pady=3, sticky="ew")
            frame_seg.grid_columnconfigure(2, weight=1)

            # Timestamp badge
            lbl_ts = ctk.CTkLabel(
                frame_seg,
                text=f"[{formatear_tiempo(seg_start)}]",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=tema.CELESTE,
                width=65,
            )
            lbl_ts.grid(row=0, column=0, padx=(8, 4), pady=6)

            # Hablante Entry / Dropdown
            entry_spk = ctk.CTkEntry(frame_seg, width=120, height=28)
            entry_spk.insert(0, display_spk)
            entry_spk.grid(row=0, column=1, padx=4, pady=6)

            # Texto editable
            entry_text = ctk.CTkEntry(frame_seg, height=28)
            entry_text.insert(0, text)
            entry_text.grid(row=0, column=2, padx=4, pady=6, sticky="ew")

            # Botón Play (Birome sobrio para no saturar con decenas de filas en Yema)
            btn_play = ctk.CTkButton(
                frame_seg,
                text="▶",
                width=32,
                height=28,
                fg_color=tema.BIROME,
                hover_color=tema.BIROME_HOVER,
                text_color=tema.PAPEL,
                command=lambda s=seg_start, d=seg_dur: self._reproducir_segmento(s, d),
            )
            btn_play.grid(row=0, column=3, padx=(4, 8), pady=6)

            self.segment_widgets.append({
                "start": seg_start,
                "end": seg_end,
                "raw_speaker": raw_spk,
                "entry_speaker": entry_spk,
                "entry_text": entry_text,
                "words": seg.get("words", []),
            })

        self.lbl_editor_status.configure(
            text=f"Cargados {len(segments)} segmentos. Audio: {'Disponible para reproducción' if self.current_editor_audio else 'No encontrado'}",
        )

    def _reproducir_segmento(self, start_seconds: float, duration_seconds: float):
        """Reproduce el audio correspondiente al segmento."""
        if not self.current_editor_audio or not self.current_editor_audio.exists():
            messagebox.showwarning("Audio no disponible", "No se encontró el archivo de audio correspondiente para reproducir.")
            return
        self.player.play_segment(self.current_editor_audio, start_seconds, duration_seconds + 0.5)

    def _guardar_cambios_editor(self):
        """Guarda las ediciones de texto y hablantes y re-exporta TXT, SRT, DOCX, JSON en <1s."""
        if not self.current_editor_json or not self.segment_widgets:
            messagebox.showwarning("Aviso", "No hay ninguna transcripción cargada en el editor.")
            return

        nuevos_segmentos = []
        speaker_mapping = {}

        for item in self.segment_widgets:
            spk_val = item["entry_speaker"].get().strip()
            text_val = item["entry_text"].get().strip()
            raw_spk = item["raw_speaker"]
            
            if spk_val:
                speaker_mapping[raw_spk] = spk_val

            nuevos_segmentos.append({
                "start": item["start"],
                "end": item["end"],
                "speaker": raw_spk,
                "text": text_val,
                "words": item.get("words", []),
            })

        base_name = self.current_editor_json.stem.replace("_completo", "")
        out_dir = self.current_editor_json.parent

        # Cargar metadata previa si existe
        try:
            with open(self.current_editor_json, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                meta = old_data.get("metadata", {})
        except Exception:
            meta = {}

        exportar_todo(
            segments=nuevos_segmentos,
            output_dir=out_dir,
            base_name=base_name,
            speaker_mapping=speaker_mapping,
            metadata=meta,
        )

        self.lbl_editor_status.configure(text=f"✅ Guardado con éxito. TXT, SRT, DOCX y JSON actualizados ({time.strftime('%H:%M:%S')})")
        messagebox.showinfo("Guardado Exitoso", "Todos los archivos (TXT, SRT, DOCX, JSON) fueron actualizados correctamente.")

    # =========================================================================
    # PESTAÑA 3: ADMINISTRAR / RENOMBRAR HABLANTES
    # =========================================================================
    def _setup_tab_hablantes(self):
        tab = self.tab_hablantes
        tab.grid_columnconfigure(0, weight=1)

        card_admin = ctk.CTkFrame(tab, corner_radius=12, border_width=1)
        card_admin.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        card_admin.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_admin,
            text="Renombrado Global de Hablantes (Sin Reprocesar Audio)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 8), sticky="w")

        ctk.CTkLabel(
            card_admin,
            text="Permite reemplazar 'SPEAKER 01..04' por nombres reales en todos los archivos generados en menos de 1 segundo.",
            font=ctk.CTkFont(size=12),
            text_color=tema.PLATA,
        ).grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 15), sticky="w")

        # Seleccionar transcripción
        ctk.CTkLabel(card_admin, text="Transcripción (.json):").grid(row=2, column=0, padx=(15, 10), pady=10, sticky="w")
        self.entry_admin_json = ctk.CTkEntry(card_admin, placeholder_text="Elegí el archivo *_completo.json de la transcripción")
        self.entry_admin_json.grid(row=2, column=1, padx=5, pady=10, sticky="ew")

        btn_admin_browse = ctk.CTkButton(card_admin, text="Examinar...", width=100, command=self._seleccionar_json_admin)
        btn_admin_browse.grid(row=2, column=2, padx=(5, 15), pady=10)

        # Campos de nombres
        frame_names = ctk.CTkFrame(card_admin, fg_color="transparent")
        frame_names.grid(row=3, column=0, columnspan=3, padx=15, pady=10, sticky="ew")
        frame_names.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(frame_names, text="SPEAKER 01 =").grid(row=0, column=0, padx=5, pady=8, sticky="e")
        self.entry_adm_spk1 = ctk.CTkEntry(frame_names, placeholder_text="Nuevo nombre 1")
        self.entry_adm_spk1.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        ctk.CTkLabel(frame_names, text="SPEAKER 02 =").grid(row=0, column=2, padx=5, pady=8, sticky="e")
        self.entry_adm_spk2 = ctk.CTkEntry(frame_names, placeholder_text="Nuevo nombre 2")
        self.entry_adm_spk2.grid(row=0, column=3, padx=5, pady=8, sticky="ew")

        ctk.CTkLabel(frame_names, text="SPEAKER 03 =").grid(row=1, column=0, padx=5, pady=8, sticky="e")
        self.entry_adm_spk3 = ctk.CTkEntry(frame_names, placeholder_text="Nuevo nombre 3")
        self.entry_adm_spk3.grid(row=1, column=1, padx=5, pady=8, sticky="ew")

        ctk.CTkLabel(frame_names, text="SPEAKER 04 =").grid(row=1, column=2, padx=5, pady=8, sticky="e")
        self.entry_adm_spk4 = ctk.CTkEntry(frame_names, placeholder_text="Nuevo nombre 4")
        self.entry_adm_spk4.grid(row=1, column=3, padx=5, pady=8, sticky="ew")

        btn_aplicar_nombres = ctk.CTkButton(
            card_admin,
            text="⚡ Aplicar Nuevos Nombres a TXT, SRT, DOCX y JSON",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            command=self._aplicar_nombres_admin,
        )
        btn_aplicar_nombres.grid(row=4, column=0, columnspan=3, padx=15, pady=(15, 15), sticky="ew")

        self.lbl_admin_status = ctk.CTkLabel(card_admin, text="", font=ctk.CTkFont(size=12), text_color=tema.YEMA)
        self.lbl_admin_status.grid(row=5, column=0, columnspan=3, padx=15, pady=(0, 15))

    def _seleccionar_json_admin(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar transcripción JSON",
            initialdir=str(OUTPUT_DIR),
            filetypes=[("Archivos JSON", "*.json")],
        )
        if ruta:
            p = Path(ruta)
            self.entry_admin_json.delete(0, "end")
            self.entry_admin_json.insert(0, str(p))
            # Cargar nombres actuales si existen
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    m = d.get("speaker_mapping", {})
                    self.entry_adm_spk1.delete(0, "end")
                    self.entry_adm_spk1.insert(0, m.get("SPEAKER 01", ""))
                    self.entry_adm_spk2.delete(0, "end")
                    self.entry_adm_spk2.insert(0, m.get("SPEAKER 02", ""))
                    self.entry_adm_spk3.delete(0, "end")
                    self.entry_adm_spk3.insert(0, m.get("SPEAKER 03", ""))
                    self.entry_adm_spk4.delete(0, "end")
                    self.entry_adm_spk4.insert(0, m.get("SPEAKER 04", ""))
            except Exception:
                pass

    def _aplicar_nombres_admin(self):
        ruta = self.entry_admin_json.get().strip()
        if not ruta or not Path(ruta).exists():
            messagebox.showerror("Error", "Por favor seleccioná un archivo JSON válido.")
            return

        mapeo = {
            "SPEAKER 01": self.entry_adm_spk1.get().strip() or "SPEAKER 01",
            "SPEAKER 02": self.entry_adm_spk2.get().strip() or "SPEAKER 02",
            "SPEAKER 03": self.entry_adm_spk3.get().strip() or "SPEAKER 03",
            "SPEAKER 04": self.entry_adm_spk4.get().strip() or "SPEAKER 04",
        }

        try:
            res = reexportar_desde_json(Path(ruta), mapeo)
            self.lbl_admin_status.configure(text=f"✅ Nombres aplicados instantáneamente a: TXT, SRT, DOCX, JSON ({time.strftime('%H:%M:%S')})")
            messagebox.showinfo("Éxito", "Archivos actualizados correctamente con los nuevos nombres de los hablantes.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar archivos:\n{e}")

    # =========================================================================
    # PESTAÑA 4: CONFIGURACIÓN & SISTEMA
    # =========================================================================
    def _setup_tab_config(self):
        tab = self.tab_config
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        # Desplazable: con la tarjeta de modelos no entra entera en la altura mínima de la ventana.
        cont = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        cont.grid(row=0, column=0, sticky="nsew")
        cont.grid_columnconfigure(0, weight=1)

        # Card 1: Motor y Hardware (detectado en esta PC)
        card_sys = ctk.CTkFrame(cont, corner_radius=12, border_width=1)
        card_sys.grid(row=0, column=0, padx=15, pady=10, sticky="ew")
        card_sys.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(card_sys, text="Motor y Hardware de esta PC", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=(12, 8), sticky="w")
        ctk.CTkLabel(card_sys, text=self._texto_motor_y_hardware(), justify="left", font=ctk.CTkFont(size=12)).grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 12), sticky="w")

        # Card 2: Modelos y aceleración (descargas desde la app)
        self._crear_card_componentes(cont).grid(row=1, column=0, padx=15, pady=10, sticky="ew")

        # Card 3: Hugging Face Token
        card_token = ctk.CTkFrame(cont, corner_radius=12, border_width=1)
        card_token.grid(row=2, column=0, padx=15, pady=10, sticky="ew")
        card_token.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_token, text="Token de Hugging Face (Seguro, local en .env)", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=3, padx=15, pady=(12, 6), sticky="w")

        token_actual = cargar_token_hf()
        token_masked = f"{token_actual[:8]}...{token_actual[-4:]}" if token_actual else "No configurado"

        self.lbl_token_status = ctk.CTkLabel(
            card_token,
            text=f"Estado: {'✅ Configurado (' + token_masked + ')' if token_actual else '❌ No configurado'}",
            font=ctk.CTkFont(size=12),
            text_color=tema.YEMA if token_actual else tema.MALVON_SUAVE,
        )
        self.lbl_token_status.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 8), sticky="w")

        ctk.CTkLabel(card_token, text="Nuevo Token:").grid(row=2, column=0, padx=(15, 10), pady=(0, 12), sticky="w")
        self.entry_new_token = ctk.CTkEntry(card_token, placeholder_text="Pegá tu token hf_... aquí para actualizar", show="*")
        self.entry_new_token.grid(row=2, column=1, padx=5, pady=(0, 12), sticky="ew")

        btn_save_token = ctk.CTkButton(card_token, text="Guardar en .env", width=120, command=self._guardar_nuevo_token)
        btn_save_token.grid(row=2, column=2, padx=(5, 15), pady=(0, 12))

        # Card 4: Carpetas de Trabajo
        card_dirs = ctk.CTkFrame(cont, corner_radius=12, border_width=1)
        card_dirs.grid(row=3, column=0, padx=15, pady=10, sticky="ew")
        card_dirs.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(card_dirs, text="Carpetas del Proyecto", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=4, padx=15, pady=(12, 10), sticky="w")

        ctk.CTkButton(card_dirs, text="📂 Carpeta Input", height=32, command=lambda: os.startfile(str(INPUT_DIR))).grid(row=1, column=0, padx=8, pady=(0, 14), sticky="ew")
        ctk.CTkButton(card_dirs, text="📂 Carpeta Output", height=32, command=lambda: os.startfile(str(OUTPUT_DIR))).grid(row=1, column=1, padx=8, pady=(0, 14), sticky="ew")
        ctk.CTkButton(card_dirs, text="📂 Carpeta Modelos", height=32, command=lambda: os.startfile(str(MODELS_DIR))).grid(row=1, column=2, padx=8, pady=(0, 14), sticky="ew")
        ctk.CTkButton(card_dirs, text="📂 Carpeta Logs", height=32, command=lambda: os.startfile(str(LOGS_DIR))).grid(row=1, column=3, padx=8, pady=(0, 14), sticky="ew")

    def _texto_motor_y_hardware(self) -> str:
        nucleos = psutil.cpu_count(logical=False) or "?"
        hilos = psutil.cpu_count(logical=True) or "?"
        ram = psutil.virtual_memory().total / (1024**3)
        placa = _nombre_placa_nvidia() if componentes.placas_nvidia() else "no detectada"
        return (
            f"• En uso: Whisper {motor_actual().descripcion} (VAD activo)\n"
            "• Diarización: pyannote/speaker-diarization-community-1 en CPU (hasta 4 hablantes)\n"
            f"• Procesador: {_nombre_procesador()} ({nucleos} núcleos / {hilos} hilos)\n"
            f"• Memoria RAM: {ram:.0f} GB\n"
            f"• Placa NVIDIA: {placa}\n"
            "• Referencia medida: en un Ryzen 7 5700X3D con 32 GB, large-v3-turbo en CPU tarda ~0,96× la\n"
            "   duración del audio y usa ~11 GB de RAM.\n"
            "• Diseño y Tema Visual: Tu Tiendita IA (Sitio web oficial: tutiendita-ia.store)"
        )

    def _guardar_nuevo_token(self):
        t = self.entry_new_token.get().strip()
        if not t:
            messagebox.showwarning("Aviso", "Por favor ingresá un token de Hugging Face.")
            return
        if guardar_token_hf(t):
            self.lbl_token_status.configure(
                text=f"Estado: ✅ Configurado ({t[:8]}...{t[-4:]})",
                text_color=tema.YEMA,
            )
            self.entry_new_token.delete(0, "end")
            messagebox.showinfo("Token Guardado", "El token se guardó correctamente en el archivo .env.")
        else:
            messagebox.showerror("Error", "No se pudo guardar el archivo .env.")

    # =========================================================================
    # MODELOS Y ACELERACIÓN (descargas desde la app, ver src/componentes.py)
    # =========================================================================
    def _crear_card_componentes(self, padre) -> ctk.CTkFrame:
        card = ctk.CTkFrame(padre, corner_radius=12, border_width=1)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Modelos y Aceleración", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=3, padx=15, pady=(12, 0), sticky="w")
        ctk.CTkLabel(
            card,
            text="La versión estándar ya viene instalada. Lo demás se descarga gratis desde acá (Hugging Face y PyPI),\n"
                 "se verifica que llegue sano y se usa después de reiniciar. Si se corta, sigue desde donde quedó.",
            justify="left", font=ctk.CTkFont(size=12), text_color=tema.PLATA,
        ).grid(row=1, column=0, columnspan=3, padx=15, pady=(2, 10), sticky="w")

        fila = 2
        self._fila_componente(card, fila, None)
        for c in componentes.CATALOGO:
            fila += 1
            self._fila_componente(card, fila, c)

        # Qué usar al abrir la app
        opciones = ctk.CTkFrame(card, fg_color="transparent")
        opciones.grid(row=fila + 1, column=0, columnspan=3, padx=15, pady=(10, 4), sticky="ew")
        ctk.CTkLabel(opciones, text="Modelo a usar:").pack(side="left")
        self.menu_modelo = ctk.CTkOptionMenu(opciones, values=componentes.modelos_disponibles(), width=170, command=self._elegir_modelo)
        self.menu_modelo.pack(side="left", padx=(8, 24))
        self.switch_gpu = ctk.CTkSwitch(opciones, text="Usar la placa NVIDIA", command=self._elegir_gpu)
        self.switch_gpu.pack(side="left")
        self.lbl_motivo_gpu = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=11), text_color=tema.PLATA, justify="left")
        self.lbl_motivo_gpu.grid(row=fila + 2, column=0, columnspan=3, padx=15, pady=(0, 2), sticky="w")
        ctk.CTkLabel(
            card,
            text="Placas AMD Radeon: en evaluación. El motor ya tiene una versión para ROCm, pero todavía da errores en algunas placas.",
            font=ctk.CTkFont(size=11), text_color=tema.TEXT_DIM, justify="left",
        ).grid(row=fila + 3, column=0, columnspan=3, padx=15, pady=(0, 8), sticky="w")

        # Aviso de reinicio (aparece cuando hay un cambio pendiente)
        self.frame_reinicio = ctk.CTkFrame(card, corner_radius=10, border_width=1, border_color=tema.YEMA, fg_color=tema.EXITO_BG)
        self.frame_reinicio.grid_columnconfigure(0, weight=1)
        self.lbl_reinicio = ctk.CTkLabel(self.frame_reinicio, text="", text_color=tema.YEMA, font=ctk.CTkFont(size=12, weight="bold"), justify="left")
        self.lbl_reinicio.grid(row=0, column=0, padx=12, pady=10, sticky="w")
        ctk.CTkButton(
            self.frame_reinicio, text="Reiniciar ahora", width=130, height=32,
            fg_color=tema.YEMA, hover_color=tema.YEMA_HOVER, text_color=tema.CINTA, command=self._reiniciar,
        ).grid(row=0, column=1, padx=12, pady=10)
        self._fila_reinicio = fila + 4

        self._refrescar_componentes()
        return card

    def _fila_componente(self, card, fila: int, c: Optional[componentes.Componente]):
        marco = ctk.CTkFrame(card, corner_radius=10, fg_color=tema.CHIP_BG)
        marco.grid(row=fila, column=0, columnspan=3, padx=15, pady=4, sticky="ew")
        marco.grid_columnconfigure(0, weight=1)
        if c is None:
            titulo, descripcion = "Whisper large-v3-turbo · Estándar", "Equilibrio entre velocidad y precisión. Viene con la aplicación."
        else:
            titulo, descripcion = f"{c.nombre} · {_tamano(c.tamano_descarga)}", c.descripcion
        ctk.CTkLabel(marco, text=titulo, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=12, pady=(8, 0), sticky="w")
        ctk.CTkLabel(marco, text=descripcion, font=ctk.CTkFont(size=11), text_color=tema.PLATA).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")
        estado = ctk.CTkLabel(marco, text="", font=ctk.CTkFont(size=11), text_color=tema.YEMA)
        estado.grid(row=0, column=1, rowspan=2, padx=8)
        if c is None:
            en_uso = motor_actual().modelo == componentes.MODELO_ESTANDAR
            estado.configure(text="Incluido · En uso" if en_uso else "Incluido")
            return
        boton = ctk.CTkButton(marco, text="", width=110, height=30, command=lambda c=c: self._accion_componente(c))
        boton.grid(row=0, column=2, rowspan=2, padx=(4, 12), pady=8)
        barra = ctk.CTkProgressBar(marco, height=8, progress_color=tema.YEMA)
        barra.set(0)
        detalle = ctk.CTkLabel(marco, text="", font=ctk.CTkFont(size=11), text_color=tema.PLATA)
        self.filas_componentes[c.id] = {"estado": estado, "boton": boton, "barra": barra, "detalle": detalle, "inicio": 0.0}

    def _refrescar_componentes(self):
        descargando = self.descarga_cancelar is not None
        sin_gpu = componentes.motivo_sin_gpu()
        for c in componentes.CATALOGO:
            f = self.filas_componentes[c.id]
            instalado = componentes.esta_instalado(c)
            if instalado:
                en_uso = (c.tipo == "modelo" and motor_actual().modelo == c.modelo) or (
                    c.tipo == "aceleracion" and motor_actual().dispositivo == "cuda")
                f["estado"].configure(text="En uso" if en_uso else "Instalado", text_color=tema.YEMA)
                f["boton"].configure(text="Eliminar", fg_color=tema.PELIGRO_FG, hover_color=tema.PELIGRO_HOVER,
                                     text_color=tema.MALVON_SUAVE, state="disabled" if descargando else "normal")
            else:
                no_aplica = c.tipo == "aceleracion" and bool(sin_gpu) and componentes.placas_nvidia() == 0
                a_medias = componentes.bajado_a_medias(c)
                if no_aplica:
                    texto_estado = "No compatible"
                elif a_medias:
                    texto_estado = f"En pausa · {_tamano(a_medias)} bajados"
                else:
                    texto_estado = ""
                f["estado"].configure(text=texto_estado, text_color=tema.PLATA)
                f["boton"].configure(text="Seguir" if a_medias else "Descargar", fg_color=tema.BIROME, hover_color=tema.BIROME_HOVER,
                                     text_color=tema.PAPEL, state="disabled" if (descargando or no_aplica) else "normal")
        self.menu_modelo.configure(values=componentes.modelos_disponibles())
        ajustes = componentes.leer_ajustes()
        self.menu_modelo.set(ajustes["modelo_whisper"] if ajustes["modelo_whisper"] in componentes.modelos_disponibles() else componentes.MODELO_ESTANDAR)
        if componentes.esta_instalado(componentes.NVIDIA) and not sin_gpu:
            self.switch_gpu.configure(state="normal")
            self.switch_gpu.select() if ajustes["usar_gpu"] else self.switch_gpu.deselect()
            self.lbl_motivo_gpu.configure(text="")
        else:
            self.switch_gpu.deselect()
            self.switch_gpu.configure(state="disabled")
            self.lbl_motivo_gpu.configure(text=sin_gpu or "Descargá la Aceleración NVIDIA para activarla.")
        self._actualizar_aviso_reinicio()

    def _cambios_pendientes(self) -> list:
        """Qué cambia al reiniciar: lo elegido en Configuración contra lo que está usando este proceso."""
        proximo = componentes.elegir_motor()
        actual = motor_actual()
        cambios = []
        if proximo.modelo != actual.modelo:
            cambios.append(f"modelo {proximo.modelo}")
        if proximo.dispositivo != actual.dispositivo:
            cambios.append("placa NVIDIA" if proximo.dispositivo == "cuda" else "procesador (CPU)")
        return cambios

    def _actualizar_aviso_reinicio(self):
        cambios = self._cambios_pendientes()
        if cambios:
            self.lbl_reinicio.configure(text=f"Al reiniciar se va a usar: {', '.join(cambios)}.")
            self.frame_reinicio.grid(row=self._fila_reinicio, column=0, columnspan=3, padx=15, pady=(4, 14), sticky="ew")
        else:
            self.frame_reinicio.grid_remove()

    def _elegir_modelo(self, modelo: str):
        componentes.guardar_ajustes(modelo_whisper=modelo)
        self._refrescar_componentes()

    def _elegir_gpu(self):
        componentes.guardar_ajustes(usar_gpu=bool(self.switch_gpu.get()))
        self._refrescar_componentes()

    def _accion_componente(self, c: componentes.Componente):
        if self.descarga_cancelar is not None:
            self.descarga_cancelar.set()  # el botón de la fila en curso funciona como "Cancelar"
            return
        if componentes.esta_instalado(c):
            self._eliminar_componente(c)
        else:
            self._descargar_componente(c)

    def _descargar_componente(self, c: componentes.Componente):
        self.descarga_cancelar = threading.Event()
        self._refrescar_componentes()
        f = self.filas_componentes[c.id]
        f["boton"].configure(text="Cancelar", state="normal", fg_color=tema.PELIGRO_FG, hover_color=tema.PELIGRO_HOVER, text_color=tema.MALVON_SUAVE)
        f["estado"].configure(text="Descargando…", text_color=tema.YEMA)
        f["barra"].set(0)
        f["barra"].grid(row=2, column=0, columnspan=3, padx=12, pady=(0, 2), sticky="ew")
        f["detalle"].configure(text="Conectando…")
        f["detalle"].grid(row=3, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="w")
        f["inicio"] = time.monotonic()
        cancelar = self.descarga_cancelar
        eventos = self.eventos_descarga

        def trabajo():
            # Este hilo no toca la ventana: deja avisos en la cola y _atender_descarga los muestra.
            try:
                componentes.instalar(c, lambda hecho, total: eventos.put(("progreso", c.id, hecho, total)), cancelar)
                eventos.put(("fin", c, None))
            except componentes.DescargaCancelada:
                eventos.put(("fin", c, "cancelada"))
            except Exception as e:
                eventos.put(("fin", c, str(e)))

        threading.Thread(target=trabajo, daemon=True).start()
        self.after(100, self._atender_descarga)

    def _atender_descarga(self):
        try:
            while True:
                evento = self.eventos_descarga.get_nowait()
                if evento[0] == "progreso":
                    self._mostrar_progreso_descarga(*evento[1:])
                else:
                    self._descarga_terminada(*evento[1:])
                    return
        except queue.Empty:
            pass
        self.after(100, self._atender_descarga)

    def _mostrar_progreso_descarga(self, id_componente: str, hecho: int, total: int):
        f = self.filas_componentes[id_componente]
        f["barra"].set(hecho / total if total else 0)
        transcurrido = max(time.monotonic() - f["inicio"], 0.1)
        velocidad = hecho / transcurrido
        texto = f"{_tamano(hecho)} de {_tamano(total)} · {velocidad / 1e6:.1f} MB/s".replace(".", ",")
        if velocidad > 0 and hecho < total:
            texto += f" · quedan ~{formatear_tiempo((total - hecho) / velocidad)}"
        f["detalle"].configure(text=texto)

    def _descarga_terminada(self, c: componentes.Componente, error: Optional[str]):
        self.descarga_cancelar = None
        f = self.filas_componentes[c.id]
        f["barra"].grid_remove()
        f["detalle"].grid_remove()
        if error is None:
            # Se descargó para usarlo: queda elegido para el próximo inicio.
            if c.tipo == "modelo":
                componentes.guardar_ajustes(modelo_whisper=c.modelo)
            else:
                componentes.guardar_ajustes(usar_gpu=True)
            self._refrescar_componentes()
            if messagebox.askyesno(
                "Descarga completa",
                f"{c.nombre} quedó instalado.\n\nPara usarlo hay que reiniciar la aplicación. ¿Reiniciar ahora?",
            ):
                self._reiniciar()
            return
        self._refrescar_componentes()
        if error != "cancelada":  # la pausa ya la muestra _refrescar_componentes, con lo bajado
            f["estado"].configure(text="Error", text_color=tema.MALVON_SUAVE)
            messagebox.showerror("No se pudo descargar", error)

    def _eliminar_componente(self, c: componentes.Componente):
        if not messagebox.askyesno("Eliminar", f"¿Eliminar {c.nombre}? Libera {_tamano(c.tamano_descarga)} y se puede volver a descargar."):
            return
        componentes.eliminar(c)
        if c.tipo == "modelo" and componentes.leer_ajustes()["modelo_whisper"] == c.modelo:
            componentes.guardar_ajustes(modelo_whisper=componentes.MODELO_ESTANDAR)
        self._refrescar_componentes()

    def _reiniciar(self):
        if self.is_processing:
            messagebox.showwarning("Transcripción en curso", "Esperá a que termine (o cancelala) y reiniciá desde Configuración.")
            return
        if self.descarga_cancelar is not None:
            if not messagebox.askyesno("Descarga en curso", "Hay una descarga en curso: se pausa y sigue la próxima vez. ¿Reiniciar igual?"):
                return
            self.descarga_cancelar.set()
        try:
            flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            subprocess.Popen(componentes.comando_reinicio(), cwd=str(BASE_DIR), env=componentes.entorno_reinicio(), creationflags=flags)
        except OSError as e:
            messagebox.showerror("No se pudo reiniciar", f"Cerrá y volvé a abrir la aplicación a mano.\n\n{e}")
            return
        self.destroy()

    def _al_cerrar(self):
        if self.descarga_cancelar is not None:
            if not messagebox.askyesno("Descarga en curso", "Si cerrás, la descarga se pausa y sigue desde donde quedó la próxima vez. ¿Cerrar?"):
                return
            self.descarga_cancelar.set()
        self.destroy()

    # =========================================================================
    # MONITOR DE RECURSOS EN VIVO
    # =========================================================================
    def _iniciar_monitor_recursos(self):
        def loop():
            while True:
                try:
                    ram = psutil.virtual_memory()
                    used_gb = ram.used / (1024**3)
                    total_gb = ram.total / (1024**3)
                    self.after(0, self._actualizar_ram_label, used_gb, total_gb)
                except Exception:
                    pass
                time.sleep(3.0)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _actualizar_ram_label(self, used_gb: float, total_gb: float):
        try:
            self.lbl_m_ram.configure(text=f"{used_gb:.1f} GB / {total_gb:.0f} GB")
        except Exception:
            pass


def _tamano(n: int) -> str:
    return f"{n / 1e9:.1f} GB".replace(".", ",") if n >= 1e9 else f"{n / 1e6:.0f} MB"


def _nombre_procesador() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    return platform.processor() or "desconocido"


def _nombre_placa_nvidia() -> str:
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5, creationflags=flags,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return "detectada"


def main():
    app = TranscriptorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
