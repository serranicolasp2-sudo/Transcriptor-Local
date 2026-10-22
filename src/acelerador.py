#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Gestión de Aceleración por Hardware y Add-ons Opcionales.
Permite:
- Detectar GPUs físicas instaladas en el sistema (NVIDIA, AMD Radeon, Intel).
- Administrar el modo de procesamiento (CPU INT8 predeterminado, GPU NVIDIA CUDA, DirectML).
- Descargar e instalar en segundo plano los paquetes de aceleración opcionales desde GitHub Releases.
- Realizar fallback automático a CPU ante cualquier fallo de GPU/VRAM.
"""

import os
import sys
import json
import zipfile
import threading
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable

from src.config import BASE_DIR, LOGS_DIR

CONFIG_ACEL_PATH = BASE_DIR / "config_aceleracion.json"
ADDONS_DIR = BASE_DIR / "addons"
CUDA_ADDON_DIR = ADDONS_DIR / "cuda"
DIRECTML_ADDON_DIR = ADDONS_DIR / "directml"

# URLs de descarga de los paquetes de aceleración en GitHub Releases
# Repositorio oficial del proyecto
RELEASE_BASE_URL = "https://github.com/serranicolasp2-sudo/Transcriptor-Local/releases/download/v1.0.0-addons"
URLS_ADDONS = {
    "nvidia": f"{RELEASE_BASE_URL}/transcriptor-addon-nvidia-cuda.zip",
    "amd": f"{RELEASE_BASE_URL}/transcriptor-addon-amd-directml.zip",
}

# Configuración de DLLs y directorios al importar
def inicializar_rutas_addons():
    """Añade los directorios de addons al PATH y al cargador de DLLs si existen."""
    for addon_dir in [CUDA_ADDON_DIR, DIRECTML_ADDON_DIR]:
        if addon_dir.exists():
            str_dir = str(addon_dir)
            if str_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = str_dir + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str_dir)
                except Exception:
                    pass

inicializar_rutas_addons()


def detectar_gpus_fisicas() -> List[Dict[str, Any]]:
    """
    Detecta todas las placas gráficas físicas instaladas en el equipo mediante PowerShell / WMI.
    Retorna una lista de diccionarios: [{'nombre': str, 'tipo': 'nvidia'|'amd'|'intel'|'otra', 'vram_gb': float}]
    """
    gpus = []
    if sys.platform != "win32":
        return gpus

    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                nombre = (item.get("Name") or "").strip()
                if not nombre:
                    continue
                ram_bytes = item.get("AdapterRAM") or 0
                vram_gb = round(ram_bytes / (1024 ** 3), 1) if ram_bytes else 0.0
                tipo = "otra"
                nombre_low = nombre.lower()
                if any(k in nombre_low for k in ["nvidia", "geforce", "quadro", "rtx", "gtx"]):
                    tipo = "nvidia"
                elif any(k in nombre_low for k in ["amd", "radeon"]):
                    tipo = "amd"
                elif any(k in nombre_low for k in ["intel", "arc", "iris", "uhd"]):
                    tipo = "intel"
                gpus.append({"nombre": nombre, "tipo": tipo, "vram_gb": vram_gb})
    except Exception:
        pass

    return gpus


def hay_cuda_disponible() -> bool:
    """Verifica si PyTorch y CTranslate2 tienen aceleración CUDA activa y utilizable."""
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            return True
    except Exception:
        pass
    # Verificar si existen las DLLs de CUDA en el directorio de addons
    if (CUDA_ADDON_DIR / "cublas64_12.dll").exists() or (CUDA_ADDON_DIR / "cublas64_11.dll").exists():
        return True
    return False


def hay_directml_disponible() -> bool:
    """Verifica si el entorno cuenta con soporte DirectML para AMD Radeon / Intel."""
    try:
        import torch_directml
        if hasattr(torch_directml, "is_available") and torch_directml.is_available():
            return True
    except Exception:
        pass
    if DIRECTML_ADDON_DIR.exists() and any(DIRECTML_ADDON_DIR.glob("*.dll")):
        return True
    return False


def obtener_modo_guardado() -> str:
    """
    Retorna el modo de aceleración preferido guardado: 'cpu', 'cuda' o 'directml'.
    Si no existe o no es válido, retorna 'cpu'.
    """
    if CONFIG_ACEL_PATH.exists():
        try:
            with open(CONFIG_ACEL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                modo = data.get("modo", "cpu").lower()
                if modo in ["cpu", "cuda", "directml"]:
                    return modo
        except Exception:
            pass
    return "cpu"


def guardar_modo_guardado(modo: str) -> bool:
    """Guarda la preferencia del usuario en config_aceleracion.json."""
    if modo not in ["cpu", "cuda", "directml"]:
        return False
    try:
        data = {"modo": modo}
        with open(CONFIG_ACEL_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def resolver_dispositivo_computo() -> Tuple[str, str]:
    """
    Resuelve el dispositivo y tipo de cómputo para Whisper y Pyannote.
    Retorna: (dispositivo, compute_type)
    Ejemplos:
      - ('cuda', 'float16') si se eligió CUDA y está disponible.
      - ('cpu', 'int8') por defecto y fallback ante cualquier inconsistencia.
    """
    modo = obtener_modo_guardado()

    if modo == "cuda" and hay_cuda_disponible():
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", "float16"
        except Exception:
            pass

    # Modo predeterminado estándar universal
    return "cpu", "int8"


def descargar_e_instalar_addon(
    tipo: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    cancel_event: Optional[threading.Event] = None
) -> Tuple[bool, str]:
    """
    Descarga el paquete ZIP de aceleración desde GitHub Releases en segundo plano,
    lo descomprime en la carpeta addons/ y actualiza la configuración.
    
    Args:
        tipo: 'nvidia' o 'amd'
        progress_callback: función callback que recibe (progreso_0_a_1: float, mensaje: str)
        cancel_event: evento para cancelar la descarga
        
    Returns:
        (exito: bool, mensaje_resultado: str)
    """
    url = URLS_ADDONS.get(tipo)
    if not url:
        return False, f"Tipo de addon desconocido: '{tipo}'"

    nombre_addon = "NVIDIA CUDA" if tipo == "nvidia" else "AMD Radeon DirectML"
    target_dir = CUDA_ADDON_DIR if tipo == "nvidia" else DIRECTML_ADDON_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    zip_tmp = BASE_DIR / f"tmp_addon_{tipo}.zip"

    def notificar(pct: float, msg: str):
        if progress_callback:
            try:
                progress_callback(pct, msg)
            except Exception:
                pass

    try:
        notificar(0.05, f"Conectando con el servidor para descargar {nombre_addon}...")

        # Petición HTTP con User-Agent
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "TranscriptorLocal-Updater/1.0"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = resp.getheader("Content-Length")
            total_bytes = int(total_size) if total_size and total_size.isdigit() else 0

            bytes_descargados = 0
            chunk_size = 64 * 1024  # 64 KB por bloque

            with open(zip_tmp, "wb") as f_out:
                while True:
                    if cancel_event and cancel_event.is_set():
                        f_out.close()
                        if zip_tmp.exists():
                            zip_tmp.unlink()
                        return False, "Descarga cancelada por el usuario."

                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break

                    f_out.write(chunk)
                    bytes_descargados += len(chunk)

                    if total_bytes > 0:
                        progreso = min(0.85, 0.05 + 0.80 * (bytes_descargados / total_bytes))
                        mb_desc = bytes_descargados / (1024 * 1024)
                        mb_tot = total_bytes / (1024 * 1024)
                        notificar(progreso, f"Descargando {nombre_addon}: {mb_desc:.1f} MB / {mb_tot:.1f} MB ({int(progreso * 100)}%)")
                    else:
                        mb_desc = bytes_descargados / (1024 * 1024)
                        notificar(0.50, f"Descargando {nombre_addon}: {mb_desc:.1f} MB transferidos...")

        notificar(0.88, f"Descomprimiendo archivos de {nombre_addon} en {target_dir.name}/...")

        # Descomprimir en el directorio destino
        with zipfile.ZipFile(zip_tmp, "r") as zf:
            zf.extractall(target_dir)

        # Limpiar archivo temporal
        if zip_tmp.exists():
            zip_tmp.unlink()

        # Guardar como nuevo modo preferido
        modo_guardar = "cuda" if tipo == "nvidia" else "directml"
        guardar_modo_guardado(modo_guardar)

        # Actualizar rutas del proceso actual
        inicializar_rutas_addons()

        notificar(1.0, f"¡Módulo {nombre_addon} instalado exitosamente!")
        return True, f"El acelerador {nombre_addon} fue instalado correctamente. Reiniciá la aplicación para comenzar a utilizarlo."

    except urllib.error.HTTPError as e:
        if zip_tmp.exists():
            try:
                zip_tmp.unlink()
            except Exception:
                pass
        return False, f"El paquete de aceleración aún no está publicado en el servidor (HTTP {e.code}). Podés continuar utilizando el motor universal CPU INT8 sin limitaciones."
    except Exception as e:
        if zip_tmp.exists():
            try:
                zip_tmp.unlink()
            except Exception:
                pass
        return False, f"Error durante la instalación de {nombre_addon}: {e}"
