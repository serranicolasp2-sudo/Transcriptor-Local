"""Tests del descargador de componentes (src/componentes.py) contra un servidor HTTP local."""

import hashlib
import http.server
import io
import json
import sys
import threading
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import componentes as comp  # noqa: E402


class Servidor(http.server.BaseHTTPRequestHandler):
    """Sirve ARCHIVOS respetando Range. Las perillas de clase simulan servidores problemáticos."""

    ARCHIVOS: dict = {}
    ignorar_range = False
    cortar_en = None  # corta la conexión después de N bytes (una sola vez)
    pedidos: list = []

    def do_GET(self):
        rango = self.headers.get("Range")
        Servidor.pedidos.append((self.path, rango))
        datos = self.ARCHIVOS.get(self.path)
        if datos is None:
            self.send_error(404)
            return
        inicio = 0
        if rango and not self.ignorar_range:
            inicio = int(rango.split("=")[1].rstrip("-"))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {inicio}-{len(datos) - 1}/{len(datos)}")
        else:
            self.send_response(200)
        cuerpo = datos[inicio:]
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        if Servidor.cortar_en is not None:
            corte, Servidor.cortar_en = Servidor.cortar_en, None
            self.wfile.write(cuerpo[:corte])
            self.wfile.flush()
            self.connection.close()
            return
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor():
    Servidor.ARCHIVOS, Servidor.ignorar_range, Servidor.cortar_en, Servidor.pedidos = {}, False, None, []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Servidor)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(autouse=True)
def carpetas(tmp_path, monkeypatch):
    monkeypatch.setattr(comp, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(comp, "AJUSTES_PATH", tmp_path / "ajustes.json")
    monkeypatch.setattr(comp.time, "sleep", lambda s: None)
    (tmp_path / "models").mkdir()
    return tmp_path


def _archivo(base, nombre, datos, sha=None):
    Servidor.ARCHIVOS[f"/{nombre}"] = datos
    return comp.Archivo(f"{base}/{nombre}", len(datos), sha or hashlib.sha256(datos).hexdigest(), nombre)


def _modelo(base, **datos):
    archivos = tuple(_archivo(base, n, d) for n, d in datos.items())
    return comp.Componente("whisper-prueba", "Prueba", "", "modelo", archivos, modelo="prueba")


def test_descarga_verifica_e_instala(servidor):
    c = _modelo(servidor, **{"model.bin": b"x" * 3_000_000, "config.json": b"{}"})
    avances = []
    comp.instalar(c, lambda h, t: avances.append((h, t)))
    assert comp.esta_instalado(c)
    assert (c.carpeta / "model.bin").read_bytes() == b"x" * 3_000_000
    assert avances[-1] == (3_000_002, 3_000_002)
    assert not (comp.MODELS_DIR / "whisper-prueba.descarga").exists()
    assert json.loads((c.carpeta / comp.MARCA_INSTALADO).read_text())["archivos"] == ["model.bin", "config.json"]


def test_huella_distinta_no_instala_y_borra_lo_bajado(servidor):
    a = _archivo(servidor, "model.bin", b"contenido real", sha="0" * 64)
    c = comp.Componente("whisper-prueba", "Prueba", "", "modelo", (a,), modelo="prueba")
    with pytest.raises(comp.ErrorDescarga, match="llegó dañado"):
        comp.instalar(c)
    assert not comp.esta_instalado(c)
    assert not list((comp.MODELS_DIR / "whisper-prueba.descarga").glob("*.part"))


def test_cancelar_deja_el_parcial_y_despues_retoma_sin_rebajar(servidor):
    datos = bytes(range(256)) * 20_000  # ~5 MB: varios bloques
    c = _modelo(servidor, **{"model.bin": datos})
    cancelar = threading.Event()

    def progreso(hecho, total):
        if hecho >= comp.BLOQUE:
            cancelar.set()

    with pytest.raises(comp.DescargaCancelada):
        comp.instalar(c, progreso, cancelar)
    parcial = comp.MODELS_DIR / "whisper-prueba.descarga" / "model.bin.part"
    ya_bajado = parcial.stat().st_size
    assert 0 < ya_bajado < len(datos)

    assert comp.bajado_a_medias(c) == ya_bajado  # la fila muestra "En pausa · N MB bajados"

    comp.instalar(c)
    assert (c.carpeta / "model.bin").read_bytes() == datos
    assert Servidor.pedidos[-1] == ("/model.bin", f"bytes={ya_bajado}-")
    assert comp.bajado_a_medias(c) == 0


def test_conexion_cortada_se_reintenta_desde_donde_quedo(servidor):
    datos = b"abc" * 1_000_000
    c = _modelo(servidor, **{"model.bin": datos})
    Servidor.cortar_en = 1_000_000
    comp.instalar(c)
    assert (c.carpeta / "model.bin").read_bytes() == datos
    assert Servidor.pedidos == [("/model.bin", None), ("/model.bin", "bytes=1000000-")]


def test_servidor_que_ignora_range_empieza_de_cero_sin_corromper(servidor):
    datos = b"0123456789" * 300_000
    c = _modelo(servidor, **{"model.bin": datos})
    temporal = comp.MODELS_DIR / "whisper-prueba.descarga"
    temporal.mkdir()
    (temporal / "model.bin.part").write_bytes(datos[:1000])
    Servidor.ignorar_range = True
    comp.instalar(c)
    assert (c.carpeta / "model.bin").read_bytes() == datos


def test_error_404_avisa_sin_reintentar(servidor):
    a = comp.Archivo(f"{servidor}/no-existe.bin", 10, "0" * 64, "model.bin")
    c = comp.Componente("whisper-prueba", "Prueba", "", "modelo", (a,), modelo="prueba")
    with pytest.raises(comp.ErrorDescarga, match="respondió 404"):
        comp.instalar(c)
    assert len(Servidor.pedidos) == 1  # un 404 no se reintenta
    assert not comp.esta_instalado(c)


def test_sin_lugar_en_disco_no_empieza(servidor, monkeypatch):
    c = _modelo(servidor, **{"model.bin": b"x" * 100})
    monkeypatch.setattr(comp.shutil, "disk_usage", lambda p: type("U", (), {"free": 10})())
    with pytest.raises(comp.ErrorDescarga, match="No hay lugar en el disco"):
        comp.instalar(c)


def _wheel(miembros: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in miembros.items():
            z.writestr(nombre, datos)
    return buf.getvalue()


def test_paquete_nvidia_extrae_solo_las_dll(servidor):
    rueda = _wheel(
        {
            "nvidia/cublas/bin/cublas64_12.dll": b"dll1",
            "nvidia/cublas/bin/cublasLt64_12.dll": b"dll2",
            "nvidia/cublas/include/cublas.h": b"no hace falta",
        }
    )
    a = _archivo(servidor, "cublas.whl", rueda)
    a = comp.Archivo(a.url, a.tamano, a.sha256, a.nombre, extraer=(
        "nvidia/cublas/bin/cublas64_12.dll", "nvidia/cublas/bin/cublasLt64_12.dll"))
    c = comp.Componente("nvidia-cuda12", "NVIDIA", "", "aceleracion", (a,))
    comp.instalar(c)
    assert sorted(p.name for p in c.carpeta.iterdir()) == ["cublas64_12.dll", "cublasLt64_12.dll", comp.MARCA_INSTALADO]


def test_eliminar_borra_la_marca_primero_y_los_restos_se_limpian_al_iniciar(servidor, monkeypatch):
    c = _modelo(servidor, **{"model.bin": b"x"})
    comp.instalar(c)
    # Simula Windows: la carpeta no se puede borrar porque un archivo está en uso.
    monkeypatch.setattr(comp.shutil, "rmtree", lambda *a, **k: None)
    comp.eliminar(c)
    assert not comp.esta_instalado(c) and c.carpeta.exists()
    monkeypatch.undo()
    monkeypatch.setattr(comp, "MODELS_DIR", c.carpeta.parent)
    monkeypatch.setattr(comp, "CATALOGO", (c,))
    comp.limpiar_restos()
    assert not c.carpeta.exists()


def test_ajustes_y_eleccion_de_motor(monkeypatch):
    # Sin nada instalado: estándar en CPU, aunque los ajustes pidan otra cosa.
    comp.guardar_ajustes(modelo_whisper="large-v3", usar_gpu=True)
    assert comp.elegir_motor() == comp.Motor("large-v3-turbo", "large-v3-turbo", "cpu", "int8")

    # Con large-v3 y el paquete NVIDIA instalados y una placa presente: large-v3 en la placa.
    instalados = {"whisper-large-v3", "nvidia-cuda12"}
    monkeypatch.setattr(comp, "esta_instalado", lambda c: c.id in instalados)
    monkeypatch.setattr(comp, "placas_nvidia", lambda: 1)
    monkeypatch.setattr(comp, "_version_ctranslate2", lambda: (4, 8, 3))
    motor = comp.elegir_motor()
    assert (motor.modelo, motor.dispositivo, motor.tipo_calculo) == ("large-v3", "cuda", "float16")
    assert motor.ruta == str(comp.MODELS_DIR / "whisper-large-v3")

    # Versión vieja de CTranslate2 (necesitaría cuDNN): no se usa la placa.
    monkeypatch.setattr(comp, "_version_ctranslate2", lambda: (4, 5, 0))
    assert comp.elegir_motor().dispositivo == "cpu"
    assert "actualizá" in comp.motivo_sin_gpu()

    # El usuario apagó la placa.
    monkeypatch.setattr(comp, "_version_ctranslate2", lambda: (4, 8, 3))
    comp.guardar_ajustes(usar_gpu=False)
    assert comp.elegir_motor().dispositivo == "cpu"

    # Sin placa NVIDIA.
    comp.guardar_ajustes(usar_gpu=True)
    monkeypatch.setattr(comp, "placas_nvidia", lambda: 0)
    assert "No se detectó" in comp.motivo_sin_gpu() and comp.elegir_motor().dispositivo == "cpu"


def test_ajustes_rotos_vuelven_a_los_valores_por_defecto():
    comp.AJUSTES_PATH.write_text("{no es json", encoding="utf-8")
    assert comp.leer_ajustes() == comp.AJUSTES_POR_DEFECTO


def test_catalogo_fijado_y_completo():
    for c in comp.CATALOGO:
        assert c.archivos
        for a in c.archivos:
            assert a.url.startswith("https://") and len(a.sha256) == 64 and a.tamano > 0
            assert "/resolve/main/" not in a.url  # revisión fijada, no la rama
    modelos = {c.modelo: {a.nombre for a in c.archivos} for c in comp.CATALOGO if c.tipo == "modelo"}
    # Lo que faster-whisper necesita para cargar un modelo desde una carpeta.
    for nombres in modelos.values():
        assert {"config.json", "model.bin", "tokenizer.json"} <= nombres
        assert any(n.startswith("vocabulary.") for n in nombres)
    assert "preprocessor_config.json" in modelos["large-v3"]  # large-v3 usa 128 bandas: sin esto transcribe mal
    assert comp.NVIDIA.archivos[0].extraer[:2] == (
        "nvidia/cublas/bin/cublas64_12.dll",
        "nvidia/cublas/bin/cublasLt64_12.dll",
    )
