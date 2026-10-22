#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Componentes opcionales que se descargan desde la propia aplicación.

La versión estándar trae Whisper large-v3-turbo para CPU. Desde la pestaña Configuración (o con
`python -m src.componentes` si se usa el código fuente) se pueden sumar:

- Whisper small:     más rápido y liviano, para equipos con poca RAM.
- Whisper large-v3:  máxima precisión, más lento.
- Aceleración NVIDIA: cuBLAS para CUDA 12, para transcribir con la placa de video.

Cada archivo tiene la dirección, el tamaño y la huella SHA-256 fijados acá: si lo que llega no
coincide, no se instala. Las descargas cortadas se retoman desde donde quedaron (.part).
Todo se guarda dentro de models/, que el desinstalador ya borra.

Los cambios de modelo o de placa se aplican al reiniciar la aplicación: el modelo se carga una
sola vez por proceso y las librerías de NVIDIA se registran al arrancar.
"""

import hashlib
import http.client
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from src.config import BASE_DIR, MODELS_DIR

AJUSTES_PATH = BASE_DIR / "ajustes.json"
MARCA_INSTALADO = "instalado.json"
MODELO_ESTANDAR = "large-v3-turbo"
CTRANSLATE2_MINIMO_GPU = (4, 6, 3)  # desde 4.6.3 la versión oficial ya no necesita cuDNN, solo cuBLAS
BLOQUE = 1024 * 1024
REINTENTOS = 3


class ErrorDescarga(Exception):
    """La descarga o la instalación falló. El mensaje está pensado para mostrárselo al usuario."""


class DescargaCancelada(Exception):
    """El usuario canceló. Lo descargado queda en .part para retomar la próxima vez."""


@dataclass(frozen=True)
class Archivo:
    url: str
    tamano: int
    sha256: str
    nombre: str
    # Si el archivo es un paquete .whl/.zip, qué miembros extraer (se guardan sin carpetas).
    extraer: tuple = ()


@dataclass(frozen=True)
class Componente:
    id: str
    nombre: str
    descripcion: str
    tipo: str  # "modelo" o "aceleracion"
    archivos: tuple
    modelo: str = ""  # para tipo "modelo": el nombre con el que se elige en Configuración

    @property
    def carpeta(self) -> Path:
        return MODELS_DIR / self.id

    @property
    def tamano_descarga(self) -> int:
        return sum(a.tamano for a in self.archivos)


def _hf(repo: str, revision: str, nombre: str, tamano: int, sha256: str) -> Archivo:
    # Revisión fijada (commit), no "main": el archivo no puede cambiar debajo de la huella.
    return Archivo(f"https://huggingface.co/{repo}/resolve/{revision}/{nombre}", tamano, sha256, nombre)


_SMALL = ("Systran/faster-whisper-small", "536b0662742c02347bc0e980a01041f333bce120")
_LV3 = ("Systran/faster-whisper-large-v3", "edaa852ec7e145841d8ffdb056a99866b5f0a478")
_CUBLAS_VERSION = "12.8.4.1"

CATALOGO = (
    Componente(
        id="whisper-small",
        nombre="Whisper small",
        descripcion="Más rápido y liviano. Para equipos con 8 GB de RAM o audios largos.",
        tipo="modelo",
        modelo="small",
        archivos=(
            _hf(*_SMALL, "config.json", 2370, "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828"),
            _hf(*_SMALL, "model.bin", 483546902, "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"),
            _hf(*_SMALL, "tokenizer.json", 2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
            _hf(*_SMALL, "vocabulary.txt", 459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
        ),
    ),
    Componente(
        id="whisper-large-v3",
        nombre="Whisper large-v3",
        descripcion="Máxima precisión. Bastante más lento y pide más memoria que el estándar.",
        tipo="modelo",
        modelo="large-v3",
        archivos=(
            _hf(*_LV3, "config.json", 2394, "a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9"),
            _hf(*_LV3, "model.bin", 3087284237, "69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1"),
            _hf(*_LV3, "preprocessor_config.json", 340, "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"),
            _hf(*_LV3, "tokenizer.json", 2480617, "6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca"),
            _hf(*_LV3, "vocabulary.json", 1068114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
        ),
    ),
    Componente(
        id="nvidia-cuda12",
        nombre="Aceleración NVIDIA",
        descripcion="Transcribe con la placa de video (GeForce GTX 16xx / RTX). Requiere driver de NVIDIA actualizado.",
        tipo="aceleracion",
        archivos=(
            Archivo(
                url="https://files.pythonhosted.org/packages/70/61/7d7b3c70186fb651d0fbd35b01dbfc8e755f69fd58f817f3d0f642df20c3/"
                f"nvidia_cublas_cu12-{_CUBLAS_VERSION}-py3-none-win_amd64.whl",
                tamano=567544208,
                sha256="47e9b82132fa8d2b4944e708049229601448aaad7e6f296f630f2d1a32de35af",
                nombre="cublas.whl",
                extraer=(
                    "nvidia/cublas/bin/cublas64_12.dll",
                    "nvidia/cublas/bin/cublasLt64_12.dll",
                    f"nvidia_cublas_cu12-{_CUBLAS_VERSION}.dist-info/License.txt",
                ),
            ),
        ),
    ),
)

_POR_ID = {c.id: c for c in CATALOGO}
NVIDIA = _POR_ID["nvidia-cuda12"]


def componente(id_componente: str) -> Componente:
    try:
        return _POR_ID[id_componente]
    except KeyError:
        raise ErrorDescarga(f"No existe el componente '{id_componente}'. Opciones: {', '.join(_POR_ID)}") from None


# -----------------------------------------------------------------------------
# Estado de instalación
# -----------------------------------------------------------------------------
def _archivos_finales(c: Componente) -> list:
    nombres = []
    for a in c.archivos:
        nombres += [Path(m).name for m in a.extraer] if a.extraer else [a.nombre]
    return nombres


def esta_instalado(c: Componente) -> bool:
    """Instalado = la marca existe y están todos los archivos (las huellas se verificaron al descargar)."""
    if not (c.carpeta / MARCA_INSTALADO).exists():
        return False
    return all((c.carpeta / n).is_file() for n in _archivos_finales(c))


def bajado_a_medias(c: Componente) -> int:
    """Bytes ya descargados de una instalación que quedó en pausa (0 si no hay nada pendiente)."""
    temporal = _carpeta_temporal(c)
    if esta_instalado(c) or not temporal.is_dir():
        return 0
    return sum(p.stat().st_size for p in temporal.iterdir() if p.is_file())


def modelos_disponibles() -> list:
    """Modelos de Whisper que se pueden elegir ahora: el estándar siempre, los otros si están instalados."""
    return [MODELO_ESTANDAR] + [c.modelo for c in CATALOGO if c.tipo == "modelo" and esta_instalado(c)]


def eliminar(c: Componente) -> None:
    """
    Borra el componente. Primero la marca: así, aunque Windows no deje borrar una DLL que la app tiene
    abierta (el paquete NVIDIA en uso), la app ya no lo usa y los restos se limpian al próximo inicio.
    """
    (c.carpeta / MARCA_INSTALADO).unlink(missing_ok=True)
    shutil.rmtree(c.carpeta, ignore_errors=True)
    shutil.rmtree(_carpeta_temporal(c), ignore_errors=True)


def limpiar_restos() -> None:
    """Borra carpetas de componentes sin marca de instalado (quedan si se eliminó algo que estaba en uso).
    Las descargas a medias viven en <id>.descarga y no se tocan: se retoman."""
    for c in CATALOGO:
        if c.carpeta.exists() and not (c.carpeta / MARCA_INSTALADO).exists():
            shutil.rmtree(c.carpeta, ignore_errors=True)


# -----------------------------------------------------------------------------
# Descarga e instalación
# -----------------------------------------------------------------------------
def _carpeta_temporal(c: Componente) -> Path:
    return MODELS_DIR / f"{c.id}.descarga"


def _espacio_necesario(c: Componente) -> int:
    # Un paquete se descarga entero y después se extrae: hace falta lugar para las dos cosas.
    extra = sum(a.tamano * 2 for a in c.archivos if a.extraer)
    return int((c.tamano_descarga + extra) * 1.05)


def _descargar_archivo(
    a: Archivo,
    destino: Path,
    avance: Callable[[int], None],
    cancelar: Optional[threading.Event],
) -> None:
    """Baja `a` a `destino`, retomando un .part previo. Llama a avance(bytes_nuevos) por cada bloque."""
    parcial = destino.with_name(destino.name + ".part")
    huella = hashlib.sha256()
    hecho = 0
    if parcial.exists():
        if parcial.stat().st_size > a.tamano:
            parcial.unlink()
        else:
            with open(parcial, "rb") as f:
                for bloque in iter(lambda: f.read(BLOQUE), b""):
                    huella.update(bloque)
            hecho = parcial.stat().st_size
            avance(hecho)

    intentos = 0
    while hecho < a.tamano:
        pedido = urllib.request.Request(a.url, headers={"User-Agent": "TranscriptorLocal/1.0"})
        if hecho:
            pedido.add_header("Range", f"bytes={hecho}-")
        try:
            with urllib.request.urlopen(pedido, timeout=30) as resp:
                if hecho and resp.status != 206:
                    # El servidor no respetó el pedido parcial: se empieza de cero.
                    avance(-hecho)
                    huella, hecho = hashlib.sha256(), 0
                    parcial.unlink(missing_ok=True)
                with open(parcial, "ab") as f:
                    for bloque in iter(lambda: resp.read(BLOQUE), b""):
                        if cancelar is not None and cancelar.is_set():
                            raise DescargaCancelada()
                        f.write(bloque)
                        huella.update(bloque)
                        hecho += len(bloque)
                        avance(len(bloque))
                        if hecho > a.tamano:
                            break
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError, OSError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code not in (408, 429, 500, 502, 503, 504):
                raise ErrorDescarga(f"El servidor respondió {e.code} al bajar {a.nombre}.") from e
            intentos += 1
            if intentos > REINTENTOS:
                raise ErrorDescarga(
                    f"Se cortó la conexión bajando {a.nombre}. Revisá internet y tocá Descargar de nuevo: "
                    "sigue desde donde quedó."
                ) from e
            time.sleep(2 * intentos)
            continue
        if hecho < a.tamano:  # la respuesta terminó antes de tiempo: se pide lo que falta
            intentos += 1
            if intentos > REINTENTOS:
                raise ErrorDescarga(f"La descarga de {a.nombre} quedó incompleta. Tocá Descargar de nuevo.")

    if hecho != a.tamano or huella.hexdigest() != a.sha256:
        parcial.unlink(missing_ok=True)
        raise ErrorDescarga(f"{a.nombre} llegó dañado (no coincide su huella SHA-256). Tocá Descargar de nuevo.")
    os.replace(parcial, destino)


def instalar(
    c: Componente,
    progreso: Optional[Callable[[int, int], None]] = None,
    cancelar: Optional[threading.Event] = None,
) -> None:
    """
    Descarga, verifica e instala `c` en models/<id>/.
    progreso(bytes_hechos, bytes_totales) se llama desde este mismo hilo, varias veces por segundo como mucho.
    """
    if esta_instalado(c):
        return
    libre = shutil.disk_usage(MODELS_DIR).free
    if libre < _espacio_necesario(c):
        falta = (_espacio_necesario(c) - libre) / 1e9
        raise ErrorDescarga(f"No hay lugar en el disco: liberá unos {falta:.1f} GB y probá de nuevo.")

    temporal = _carpeta_temporal(c)
    temporal.mkdir(parents=True, exist_ok=True)
    total = c.tamano_descarga
    estado = {"hecho": 0, "ultimo": 0.0}

    def avance(n: int) -> None:
        estado["hecho"] += n
        ahora = time.monotonic()
        if progreso and (ahora - estado["ultimo"] > 0.2 or estado["hecho"] >= total):
            estado["ultimo"] = ahora
            progreso(estado["hecho"], total)

    for a in c.archivos:
        destino = temporal / a.nombre
        if destino.exists() and destino.stat().st_size == a.tamano:
            avance(a.tamano)  # ya bajado y verificado en un intento anterior
            continue
        _descargar_archivo(a, destino, avance, cancelar)

    for a in c.archivos:
        if a.extraer:
            _extraer(temporal / a.nombre, a.extraer, temporal)
            (temporal / a.nombre).unlink()

    marca = {"id": c.id, "archivos": _archivos_finales(c), "instalado": time.strftime("%Y-%m-%d %H:%M:%S")}
    (temporal / MARCA_INSTALADO).write_text(json.dumps(marca, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(c.carpeta, ignore_errors=True)
    try:
        os.replace(temporal, c.carpeta)
    except OSError as e:
        raise ErrorDescarga(
            f"No se pudo terminar de instalar {c.nombre} ({e}). Reiniciá la aplicación y tocá Descargar de nuevo: "
            "no vuelve a bajar lo que ya está."
        ) from e
    if progreso:
        progreso(total, total)


def _extraer(paquete: Path, miembros: tuple, destino: Path) -> None:
    try:
        with zipfile.ZipFile(paquete) as z:
            for m in miembros:
                with z.open(m) as origen, open(destino / Path(m).name, "wb") as salida:
                    shutil.copyfileobj(origen, salida, BLOQUE)
    except (zipfile.BadZipFile, KeyError) as e:
        raise ErrorDescarga(f"El paquete {paquete.name} no tiene lo esperado ({e}). Tocá Descargar de nuevo.") from e


# -----------------------------------------------------------------------------
# Ajustes del usuario (ajustes.json junto al .exe)
# -----------------------------------------------------------------------------
AJUSTES_POR_DEFECTO = {"modelo_whisper": MODELO_ESTANDAR, "usar_gpu": True}


def leer_ajustes() -> dict:
    try:
        datos = json.loads(AJUSTES_PATH.read_text(encoding="utf-8"))
        return {**AJUSTES_POR_DEFECTO, **{k: v for k, v in datos.items() if k in AJUSTES_POR_DEFECTO}}
    except (OSError, ValueError):
        return dict(AJUSTES_POR_DEFECTO)


def guardar_ajustes(**cambios) -> dict:
    ajustes = {**leer_ajustes(), **cambios}
    AJUSTES_PATH.write_text(json.dumps(ajustes, ensure_ascii=False, indent=2), encoding="utf-8")
    return ajustes


# -----------------------------------------------------------------------------
# Placa NVIDIA y elección del motor
# -----------------------------------------------------------------------------
_dll_handles = []  # os.add_dll_directory devuelve un objeto que hay que mantener vivo
_error_carga_nvidia = ""  # por qué no cargaron las DLL de NVIDIA ("" si cargaron o no se probó)


def activar_aceleracion() -> bool:
    """Registra las DLL de cuBLAS si el paquete NVIDIA está instalado. Va antes de crear el modelo."""
    limpiar_restos()
    if not esta_instalado(NVIDIA):
        return False
    carpeta = str(NVIDIA.carpeta)
    if carpeta not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = carpeta + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory") and not _dll_handles:
        try:
            _dll_handles.append(os.add_dll_directory(carpeta))
        except OSError:
            pass
    if sys.platform == "win32" and leer_ajustes()["usar_gpu"]:
        # Se cargan ahora para detectar un paquete roto o un driver viejo antes de transcribir.
        global _error_carga_nvidia
        import ctypes

        try:
            for dll in ("cublasLt64_12.dll", "cublas64_12.dll"):
                ctypes.WinDLL(str(NVIDIA.carpeta / dll))
        except OSError as e:
            _error_carga_nvidia = str(e)
    return True


def _version_ctranslate2() -> tuple:
    import ctranslate2

    return tuple(int(x) for x in ctranslate2.__version__.split(".")[:3] if x.isdigit())


def placas_nvidia() -> int:
    """Cantidad de placas NVIDIA que ve CTranslate2 (solo necesita el driver, no cuBLAS)."""
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count()
    except Exception:
        return 0


def motivo_sin_gpu() -> str:
    """Por qué no se puede usar la placa ("" si se puede)."""
    if placas_nvidia() == 0:
        return "No se detectó una placa NVIDIA (o falta actualizar su driver)."
    if _error_carga_nvidia:
        return f"Las librerías de NVIDIA no cargan ({_error_carga_nvidia}). Eliminá el paquete y descargalo de nuevo."
    try:
        if _version_ctranslate2() < CTRANSLATE2_MINIMO_GPU:
            return "Esta versión del programa no admite la aceleración NVIDIA: actualizá el Transcriptor."
    except Exception:
        return "No se pudo verificar el motor de transcripción."
    return ""


@dataclass(frozen=True)
class Motor:
    modelo: str  # small | large-v3 | large-v3-turbo
    ruta: str  # nombre que entiende faster-whisper o carpeta del modelo
    dispositivo: str  # cpu | cuda
    tipo_calculo: str  # int8 | float16

    @property
    def descripcion(self) -> str:
        placa = "placa NVIDIA" if self.dispositivo == "cuda" else "CPU"
        return f"{self.modelo} · {placa} · {self.tipo_calculo}"


def motor_cpu(modelo: str = MODELO_ESTANDAR) -> Motor:
    return Motor(modelo, _ruta_modelo(modelo), "cpu", "int8")


def _ruta_modelo(modelo: str) -> str:
    for c in CATALOGO:
        if c.modelo == modelo:
            return str(c.carpeta)
    return MODELO_ESTANDAR  # faster-whisper lo resuelve dentro de models/ (viene con el instalador)


def elegir_motor() -> Motor:
    """El modelo y la placa según los ajustes, sin elegir nada que no esté instalado o no funcione."""
    ajustes = leer_ajustes()
    modelo = ajustes["modelo_whisper"] if ajustes["modelo_whisper"] in modelos_disponibles() else MODELO_ESTANDAR
    if ajustes["usar_gpu"] and esta_instalado(NVIDIA) and not motivo_sin_gpu():
        return Motor(modelo, _ruta_modelo(modelo), "cuda", "float16")
    return motor_cpu(modelo)


# -----------------------------------------------------------------------------
# Reinicio
# -----------------------------------------------------------------------------
def comando_reinicio() -> list:
    """Cómo volver a abrir la aplicación: el .exe si está compilada, o python main.py desde el código."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(BASE_DIR / "main.py")]


def entorno_reinicio() -> dict:
    """Variables para la instancia nueva. PYINSTALLER_RESET_ENVIRONMENT (PyInstaller 6.9+) evita que el .exe
    relanzado se crea hijo de este proceso y reutilice su entorno de arranque."""
    return {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}


# -----------------------------------------------------------------------------
# Línea de comandos (para quien usa el código fuente)
# -----------------------------------------------------------------------------
def _mb(n: int) -> str:
    return f"{n / 1e6:,.0f} MB".replace(",", ".")


def _cli(argv: list) -> int:
    uso = "Uso: python -m src.componentes [listar | instalar <id> | eliminar <id> | usar <modelo> | gpu si|no]"
    if not argv or argv[0] == "listar":
        print(f"  {MODELO_ESTANDAR:<18} incluido (estándar)")
        for c in CATALOGO:
            estado = "instalado" if esta_instalado(c) else f"disponible · {_mb(c.tamano_descarga)}"
            print(f"  {c.id:<18} {estado:<24} {c.descripcion}")
        print(f"\nEn uso al abrir: {elegir_motor().descripcion}")
        return 0
    if argv[0] in ("instalar", "eliminar") and len(argv) == 2:
        c = componente(argv[1])
        if argv[0] == "eliminar":
            eliminar(c)
            print(f"Eliminado: {c.nombre}")
            return 0

        def progreso(hecho: int, total: int) -> None:
            print(f"\r  {c.nombre}: {_mb(hecho)} / {_mb(total)} ({hecho * 100 // total} %)", end="", flush=True)

        try:
            instalar(c, progreso)
        except KeyboardInterrupt:
            print("\nCancelado. La próxima vez sigue desde donde quedó.")
            return 1
        print(f"\nListo: {c.nombre} instalado en {c.carpeta}")
        return 0
    if argv[0] == "usar" and len(argv) == 2:
        if argv[1] not in modelos_disponibles():
            print(f"El modelo '{argv[1]}' no está instalado. Instalados: {', '.join(modelos_disponibles())}")
            return 1
        guardar_ajustes(modelo_whisper=argv[1])
        print(f"Listo: se usa {argv[1]} desde la próxima transcripción.")
        return 0
    if argv[0] == "gpu" and len(argv) == 2 and argv[1] in ("si", "no"):
        guardar_ajustes(usar_gpu=argv[1] == "si")
        print(f"En uso al abrir: {elegir_motor().descripcion}")
        return 0
    print(uso)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_cli(sys.argv[1:]))
    except ErrorDescarga as e:
        print(f"\nError: {e}")
        sys.exit(1)
