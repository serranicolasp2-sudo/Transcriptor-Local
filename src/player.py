#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Reproducción de Audio por Timestamp.
Permite reproducir fragmentos desde el timestamp seleccionado en el visor interactivo.
"""

import subprocess
import threading
from pathlib import Path
from typing import Optional


class AudioPlayer:
    """Reproductor de audio ligero y no bloqueante mediante ffplay."""
    
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def play_segment(self, audio_path: str | Path, start_seconds: float, duration_seconds: Optional[float] = None) -> bool:
        """
        Reproduce el audio a partir de start_seconds.
        Si se pasa duration_seconds, se detiene automáticamente al finalizar el segmento.
        Si ya había un audio reproduciéndose, lo detiene primero.
        """
        self.stop()
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return False

        cmd = [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-ss", f"{max(0.0, start_seconds):.2f}",
        ]
        
        if duration_seconds and duration_seconds > 0:
            cmd.extend(["-t", f"{duration_seconds:.2f}"])
            
        cmd.append(str(audio_path))

        with self._lock:
            try:
                # Ocultar ventana de consola de ffplay en Windows
                creationflags = 0
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    creationflags = subprocess.CREATE_NO_WINDOW
                
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
                return True
            except Exception:
                return False

    def stop(self):
        """Detiene la reproducción activa de forma segura."""
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=0.5)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                self._process = None

    def is_playing(self) -> bool:
        """Verifica si hay una reproducción en curso."""
        with self._lock:
            return self._process is not None and self._process.poll() is None
